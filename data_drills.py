"""Rehearsal patterns for grouped metrics and strict table joins."""
from argparse import ArgumentParser
from collections import defaultdict
from datetime import date
from pathlib import Path
import json
from main import clean,load_table,report

def by_day(path,line=None):
    table=clean(path)
    chosen=defaultdict(list); bad=0
    for row in table["rows"]:
        if line and row["line"]!=line.strip().upper():continue
        try:key=date.fromisoformat(row["date"]).isoformat()
        except ValueError:bad+=1;continue
        chosen[key].append(row)
    days=[{"date":k,**report({"rows":v},sample_limit=0)["overall"]} for k,v in sorted(chosen.items())]
    weighted=[r for r in days if r["weighted_defect_rate"] is not None]
    peak=max(weighted,key=lambda r:r["weighted_defect_rate"],default=None)
    return {"days":days,"top_weighted_day":peak,"rows_with_invalid_date":bad,"excluded_from_input":table["skipped"]}

def left_join(left,right,key):
    def records(p):
        cols,data=load_table(p)
        if len(cols)!=len(set(cols)) or key not in cols:raise ValueError("join_key_or_header_invalid")
        if any(len(row)!=len(cols) for _,row in data):raise ValueError("join_row_width")
        return [dict(zip(cols,row)) for _,row in data]
    lhs=records(left);rhs={}
    for r in records(right):
        k=r[key].strip()
        if not k or k in rhs:raise ValueError("lookup_key_missing_or_duplicate")
        rhs[k]={c:v for c,v in r.items() if c!=key}
    out=[];unmatched=0
    for r in lhs:
        k=r[key].strip();match=rhs.get(k)
        if match is None:unmatched+=1
        out.append({"source":r,"lookup":match})
    return {"rows":out,"unmatched":unmatched}

if __name__=="__main__":
    p=ArgumentParser();sub=p.add_subparsers(dest="mode",required=True)
    d=sub.add_parser("daily");d.add_argument("file",type=Path);d.add_argument("--line")
    j=sub.add_parser("join");j.add_argument("left",type=Path);j.add_argument("right",type=Path);j.add_argument("--key",required=True)
    args=p.parse_args()
    print(json.dumps(by_day(args.file,args.line) if args.mode=="daily" else left_join(args.left,args.right,args.key),ensure_ascii=False,indent=2))
