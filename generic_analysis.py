"""Schema-neutral local table summaries. Never infer units or financial advice."""
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import re
from main import load_table
from local_table import SUFFIXES

COOKIE="demo_generic_table"

def read(path):
    fields, pairs=load_table(path)
    fields=[x.strip() for x in fields]
    if len(fields)>100 or not fields or any(not x for x in fields) or len(set(fields))!=len(fields):
        raise ValueError("invalid_header")
    if len(pairs)>20000:raise ValueError("too_many_rows")
    rows=[];excluded=0
    for _,cells in pairs:
        if len(cells)!=len(fields) or not any(c.strip() for c in cells):
            excluded+=1;continue
        rows.append(dict(zip(fields,map(str.strip,cells))))
    return {"fields":fields,"rows":rows,"excluded":excluded}

def uploaded(name,data):
    if not name or len(name)>130 or re.search(r"[/\\\x00-\x1f\x7f]",name) or Path(name).suffix.lower() not in SUFFIXES:
        raise ValueError("unsupported_table")
    if not data:raise ValueError("empty_file")
    with TemporaryDirectory(prefix="demo-generic-") as d:
        f=Path(d)/name;f.write_bytes(data)
        if f.suffix.lower()==".xlsx":
            with ZipFile(f) as z:
                parts=z.infolist()
                if len(parts)>1200 or sum(x.file_size for x in parts)>24*1024*1024:raise ValueError("excel_expands_too_large")
        return read(f)

def number(s):
    s=s.strip()
    if s.startswith("(") and s.endswith(")"):s="-"+s[1:-1].strip()
    if "," in s:
        if not re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?",s):return None
        s=s.replace(",","")
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)",s) or len(s)>36:return None
    try:return Decimal(s)
    except InvalidOperation:return None

def summarize(table,value,group="",day="",unit=""):
    cols=table["fields"]
    if value not in cols or any(c and c not in cols for c in (group,day,unit)):
        raise ValueError("column_not_found")
    if not unit:
        guess=next((c for c in cols if c.casefold() in {"currency","ccy","幣別","貨幣","unit","單位"}),None)
        if guess and len({r[guess] for r in table["rows"] if r[guess]})>1:raise ValueError("choose_currency_column")
    buckets=defaultdict(list)
    bad_num=bad_date=bad_unit=0
    for r in table["rows"]:
        n=number(r[value])
        if n is None:bad_num+=1;continue
        mon=""
        if day:
            try:mon=date.fromisoformat(r[day][:10]).isoformat()[:7]
            except ValueError:bad_date+=1;continue
        if unit and not r[unit]:bad_unit+=1;continue
        label=(r[group] or "未分類") if group else "全部"
        buckets[(r[unit] if unit else "",mon,label)].append(n)
    results=[]
    for (u,m,g),items in sorted(buckets.items()):
        total=sum(items,Decimal(0))
        results.append({"unit":u,"month":m,"group":g,"count":len(items),"sum":format(total,"f"),
                        "average":format(total/len(items),".4f"),"minimum":format(min(items),"f"),"maximum":format(max(items),"f")})
    return {"value_column":value,"group_column":group,"date_column":day,"unit_column":unit,
            "results":results,"excluded":{"bad_rows":table["excluded"],"non_numeric":bad_num,"invalid_date":bad_date,"missing_unit":bad_unit}}


def numeric_fields(table):
    """A column only offers arithmetic if at least one cell parses numerically."""
    remaining=set(table["fields"])
    for row in table["rows"]:
        remaining.difference_update(col for col in tuple(remaining) if number(row[col]) is not None)
        if not remaining:
            break
    return [col for col in table["fields"] if col not in remaining]


def summarize_ratio(table,value,denominator,group="",day="",unit=""):
    numeric=numeric_fields(table)
    if not denominator or denominator==value or value not in numeric or denominator not in numeric:
        raise ValueError("choose_two_numeric_columns")
    cols=table["fields"]
    if any(c and c not in cols for c in (group,day,unit)):
        raise ValueError("column_not_found")
    if not unit:
        guess=next((c for c in cols if c.casefold() in {"currency","ccy","幣別","貨幣","unit","單位"}),None)
        if guess and len({r[guess] for r in table["rows"] if r[guess]})>1:
            raise ValueError("choose_currency_column")
    buckets=defaultdict(lambda:[Decimal(0),Decimal(0),0])
    bad_num=bad_date=bad_unit=0
    for r in table["rows"]:
        numerator,denom=number(r[value]),number(r[denominator])
        if numerator is None or denom is None:
            bad_num+=1;continue
        month=""
        if day:
            try:month=date.fromisoformat(r[day][:10]).isoformat()[:7]
            except ValueError:bad_date+=1;continue
        if unit and not r[unit]:bad_unit+=1;continue
        label=(r[group] or "未分類") if group else "全部"
        sums=buckets[(r[unit] if unit else "",month,label)]
        sums[0]+=numerator;sums[1]+=denom;sums[2]+=1
    result=[]
    for (u,m,g),(n,d,count) in sorted(buckets.items()):
        result.append({"unit":u,"month":m,"group":g,"count":count,"numerator_sum":format(n,"f"),
                       "denominator_sum":format(d,"f"),"ratio":format(n/d,".6f") if d else None})
    return {"metric":"ratio","value_column":value,"denominator_column":denominator,"group_column":group,
            "date_column":day,"unit_column":unit,"results":result,
            "excluded":{"bad_rows":table["excluded"],"non_numeric":bad_num,"invalid_date":bad_date,"missing_unit":bad_unit}}
