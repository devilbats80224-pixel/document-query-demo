"""Bounded, non-executable extraction of explicit Excel cells."""
from datetime import date, time
from io import BytesIO
from math import isfinite
from pathlib import Path
from zipfile import ZipFile
import re

from openpyxl import load_workbook
from openpyxl.utils.cell import get_column_letter

COOKIE="demo_extract_workbook"

def parse(name,data):
    if len(name)>130 or re.search(r"[/\\\x00-\x1f\x7f]",name) or Path(name).suffix.lower()!=".xlsx" or not data:
        raise ValueError("unsupported_workbook")
    with ZipFile(BytesIO(data)) as z:
        parts=z.infolist()
        if len(parts)>1200 or sum(x.file_size for x in parts)>24*1024*1024:
            raise ValueError("workbook_limit")
    workbook=load_workbook(BytesIO(data),read_only=True,data_only=True,keep_links=False)
    try:
        if len(workbook.worksheets)>12:
            raise ValueError("workbook_limit")
        result={}
        count=0
        for sheet in workbook:
            # Business tables have a header on physical row 1. Do not infer it.
            if sheet.max_column and sheet.max_column>100 or sheet.max_row and sheet.max_row>5001:
                raise ValueError("workbook_limit")
            it=sheet.iter_rows(max_col=sheet.max_column or 101,values_only=True)
            first=next(it,())
            header={str(v).strip():i for i,v in enumerate(first,1) if v is not None and str(v).strip()}
            if len(header)!=sum(v is not None and bool(str(v).strip()) for v in first):
                result[sheet.title]={"columns":{},"rows":[],"issue":"標題重複，請修正第一列。"}
                continue
            rows=[]
            for ridx,raw in enumerate(it,2):
                count+=len(raw)
                if ridx>5001 or count>250000:
                    raise ValueError("workbook_limit")
                if any(v is not None for v in raw):rows.append((ridx,raw))
            result[sheet.title]={"columns":header,"rows":rows,"issue":""}
        if not result:
            raise ValueError("unsupported_workbook")
        return result
    finally:
        workbook.close()

def json_value(val):
    if isinstance(val,(date,time)):return val.isoformat()
    if isinstance(val,float) and not isfinite(val):return None
    return val

def project(filename,sheets,sheet,fields):
    s=sheets[sheet]
    fields=list(dict.fromkeys(fields))
    if not fields or any(k not in s["columns"] for k in fields):
        raise ValueError("column_not_found")
    rows=[]
    for ridx,raw in s["rows"]:
        values={}
        for key in fields:
            idx=s["columns"][key]
            values[key]={"value":json_value(raw[idx-1] if idx<=len(raw) else None),"cell":get_column_letter(idx)+str(ridx)}
        rows.append({"row":ridx,"cells":values})
    return {"file":filename,"sheet":sheet,"fields":fields,"rows":rows}
