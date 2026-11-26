"""Offline field: value extraction. PDF text support is optional and no OCR is implied."""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

class PdfTextReviewRequired(ValueError):
    def __init__(self,numbers):
        super().__init__("no_extractable_pdf_text_ocr_required")
        self.page_numbers=tuple(numbers)

def pages(path):
    if path.stat().st_size>10*1024*1024:raise ValueError("document_too_large")
    if path.suffix.lower()==".pdf":
        try:from pypdf import PdfReader
        except ImportError as e:raise ValueError("pdf_needs_pypdf_or_export_text_offline") from e
        reader=PdfReader(path)
        if len(reader.pages)>50:raise ValueError("too_many_pages")
        values=[p.extract_text() or "" for p in reader.pages]
        bad=[n for n,v in enumerate(values,1) if not v.strip() or "\ufffd" in v or "\x00" in v]
        if bad or not values:raise PdfTextReviewRequired(bad)
        return values
    from document_io import read
    return [read(path)]

def extract(text_pages, fields):
    keys=[f.strip() for f in fields]
    if not keys or any(not k or len(k)>80 for k in keys) or len(set(keys))!=len(keys):
        raise ValueError("invalid_fields")
    hits={k:[] for k in keys}
    for ix,text in enumerate(text_pages,1):
        for line_no,line in enumerate(text.splitlines(),1):
            m=re.match(r"^\s*([^:：]{1,80})[:：]\s*(.*?)\s*$",line)
            if not m or not m.group(2):continue
            k,v=m.groups();k=k.strip()
            if k in hits:hits[k].append({"value":v,"page":ix,"line":line_no})
    return {"fields":{k:h[0]["value"] if len({x["value"] for x in h})==1 else None for k,h in hits.items()},
            "missing":[k for k,h in hits.items() if not h],
            "ambiguous":[k for k,h in hits.items() if len({x["value"] for x in h})>1],
            "evidence":hits}

def main():
    p=argparse.ArgumentParser(description="抽取明示的欄位；找不到或有衝突不補猜。")
    p.add_argument("document",type=Path);p.add_argument("--field",action="append",required=True)
    a=p.parse_args()
    try:
        result=extract(pages(a.document),a.field)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 2 if result["missing"] or result["ambiguous"] else 0
    except (OSError,ValueError) as e:
        print(json.dumps({"status":"error","error":str(e)},ensure_ascii=False),file=sys.stderr)
        return 2
if __name__=="__main__":raise SystemExit(main())
