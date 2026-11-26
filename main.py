"""LITEON practice starter. Replace only what the actual prompt asks for."""
from __future__ import annotations
import argparse, csv, io, json, re, sys
from datetime import date as iso_date
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Any

MAX_BYTES = 10 * 1024 * 1024
ALIASES = {
    "line": {"line", "line_id", "production_line", "產線", "線別"},
    "date": {"date", "work_date", "日期", "生產日期"},
    "output": {"output", "output_qty", "total_qty", "quantity", "產量", "總數"},
    "defects": {"defects", "defect_qty", "defect_count", "ng_qty", "不良數", "不良數量"},
    "rate": {"rate", "defect_rate", "ng_rate", "不良率", "defect_rate_pct"},
}

def finite(v: Any, *, kind: str, bare_rate_unit: str) -> Decimal | None:
    s = str(v).strip()
    if not s or s.lower() in {"na", "n/a", "null", "none", "nan", "-"}:
        return None
    pct = s.endswith("%")
    s = s[:-1].strip() if pct else s
    if "," in s:
        if not re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?", s):
            raise ValueError("bad_number_grouping")
        s = s.replace(",", "")
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d{1,3})?", s):
        raise ValueError("invalid_number")
    n = Decimal(s)
    if not n.is_finite() or n < 0:
        raise ValueError("invalid_number")
    if kind == "rate":
        if pct or bare_rate_unit == "percent":
            n /= 100
        if n > 1:
            raise ValueError("rate_outside_0_to_1")
    elif pct or n != n.to_integral_value() or n > 10**15:
        raise ValueError("count_must_be_nonnegative_integer")
    return n

def load_table(path: Path, sheet: str | None = None) -> tuple[list[str], list[tuple[int, list[str]]]]:
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("data_file_exceeds_10_MiB")
    ext = path.suffix.lower()
    if ext == ".xlsx":
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise ValueError("xlsx_requires_openpyxl_or_export_csv") from exc
        wb = load_workbook(path, read_only=True, data_only=True)
        try:
            if sheet is not None and sheet not in wb.sheetnames:
                raise ValueError("xlsx_sheet_not_found")
            ws = wb[sheet] if sheet is not None else wb.active
            it = ws.iter_rows(values_only=True)
            raw = next(it, ())
            if not raw:
                raise ValueError("empty_sheet")
            return [str(x or "") for x in raw], [
                (i, [str(x) if x is not None else "" for x in row]) for i, row in enumerate(it, 2)
            ]
        finally:
            wb.close()
    if sheet is not None:
        raise ValueError("sheet_only_supported_for_xlsx")
    if ext in {".json",".jsonl",".ndjson"}:
        return load_json_table(path,ext)
    if ext not in {".csv",".tsv"}:
        raise ValueError("expected_csv_tsv_xlsx_json_or_jsonl")
    data = path.read_bytes()
    for codec in ("utf-8-sig", "cp950"):
        try:
            stream = io.StringIO(data.decode(codec), newline="")
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("unsupported_csv_encoding")
    reader = csv.reader(stream, strict=True, delimiter="\t" if ext==".tsv" else ",")
    fields = next(reader, None)
    if not fields:
        raise ValueError("missing_csv_header")
    return fields, [(reader.line_num, row) for row in reader]

def load_json_table(path: Path,ext:str):
    def unique(items):
        out={}
        for k,v in items:
            if k in out:raise ValueError("duplicate_json_key:"+k)
            out[k]=v
        return out
    def rejected(_):
        raise ValueError("non_finite_json_number")
    def parse(text):
        return json.loads(text,object_pairs_hook=unique,parse_float=Decimal,parse_constant=rejected)
    text=path.read_text(encoding="utf-8-sig")
    if ext==".json":
        values=parse(text)
        if not isinstance(values,list):raise ValueError("expected_json_array_of_flat_objects")
        records=list(enumerate(values,1))
    else:
        records=[(n,parse(line)) for n,line in enumerate(text.splitlines(),1) if line.strip()]
    if not records or any(not isinstance(row,dict) or not row for _,row in records):
        raise ValueError("expected_nonempty_json_flat_objects")
    if any(isinstance(v,(list,dict)) for _,row in records for v in row.values()):
        raise ValueError("nested_json_requires_explicit_mapping")
    fields=list(dict.fromkeys(k for _,row in records for k in row))
    return fields,[(n,["" if (v:=row.get(k)) is None else str(v) for k in fields]) for n,row in records]

def clean(path: Path, bare_rate_unit: str = "fraction", sheet: str | None = None) -> dict:
    fields, rows = load_table(path,sheet)
    fs = [re.sub(r"[\s-]+", "_", x.strip().casefold()) for x in fields]
    if any(not x for x in fs) or len(set(fs)) != len(fs):
        raise ValueError("blank_or_duplicate_column")
    pos: dict[str, int] = {}
    for kind, aliases in ALIASES.items():
        hits = [i for i, f in enumerate(fs) if f in aliases]
        if len(hits) > 1:
            raise ValueError(f"ambiguous_{kind}_columns")
        if hits:
            pos[kind] = hits[0]
    if "line" not in pos or not ({"output", "defects"} <= pos.keys() or "rate" in pos):
        raise ValueError("need_line_and_output_plus_defects_or_rate")
    unit = "percent" if "rate" in pos and fs[pos["rate"]] == "defect_rate_pct" else bare_rate_unit
    kept, skipped = [], Counter()
    examples: list[dict] = []
    for rownum, cells in rows:
        if not any(x.strip() for x in cells):
            skipped["blank"] += 1
            continue
        raw: dict[str, str] = {}
        try:
            if len(cells) != len(fields):
                raise ValueError("wrong_number_of_columns")
            raw = {k: cells[i] for k, i in pos.items()}
            line = raw["line"].strip().upper()
            if not line:
                raise ValueError("missing_line")
            vals = {k: finite(raw.get(k, ""), kind=k, bare_rate_unit=unit) for k in ("output", "defects")}
            vals["rate"] = None
            if vals["output"] is not None and vals["defects"] is not None:
                if vals["defects"] > vals["output"]:
                    raise ValueError("defects_exceed_output")
                if vals["output"] > 0:
                    vals["rate"] = vals["defects"] / vals["output"]
                else:
                    raise ValueError("zero_output")
            else:
                vals["rate"] = finite(raw.get("rate", ""), kind="rate", bare_rate_unit=unit)
            if vals["rate"] is None:
                raise ValueError("missing_rate")
            kept.append({"line": line, "date": raw.get("date", "").strip(), "source_row": rownum, **vals})
        except (ValueError, InvalidOperation) as exc:
            skipped[str(exc)] += 1
            if len(examples) < 10:
                example = {"row": rownum, "reason": str(exc)}
                if str(exc) == "defects_exceed_output":
                    example.update(line=line, output_qty=int(vals["output"]), defect_count=int(vals["defects"]))
                examples.append(example)
    return {"rows": kept, "source": str(path), "input_row_count": len(rows),
            "skipped": dict(skipped), "skipped_examples": examples, "resolved_columns": {k: fields[i] for k,i in pos.items()}}

def report(table: dict, line: str | None = None, sample_limit: int = 5) -> dict:
    rows = [r for r in table["rows"] if not line or r["line"] == line.strip().upper()]
    audit = {k:v for k,v in table.items() if k != "rows"}
    audit.update(valid_rows=len(table["rows"]), selected_rows=len(rows))
    if not rows:
        return {"status":"empty", "summary":"沒有符合且可分析的資料", "groups":[], "data_quality":audit}
    groups = defaultdict(list)
    for r in rows:
        groups[r["line"]].append(r)
    def metrics(g):
        with localcontext() as ctx:
            ctx.prec=28
            mean=sum(r["rate"] for r in g)/len(g)
            peak=max(r["rate"] for r in g)
            full=all(r["output"] is not None and r["defects"] is not None for r in g)
            output=sum(r["output"] for r in g) if full else None
            bad=sum(r["defects"] for r in g) if full else None
            weighted=bad/output if full and output else None
        return {"n":len(g),"mean_row_defect_rate":float(mean),"max_row_defect_rate":float(peak),
                "weighted_defect_rate":float(weighted) if weighted is not None else None,
                "output_qty":int(output) if output is not None else None,"defect_count":int(bad) if bad is not None else None}
    sample = [{k:(float(v) if isinstance(v,Decimal) else v) for k,v in r.items()} for r in rows[:sample_limit]]
    return {"status":"ok", "summary":f"已核對 {len(rows)} 筆、{len(groups)} 條產線。比率值使用 0–1。",
            "groups":[{"line": key, **metrics(group)} for key,group in sorted(groups.items())],
            "overall":metrics(rows),"data_quality":audit,"sample":sample,
            "limitations":["未自行刪除重複列；相同列未必是重複事件。",
              "加權不良率＝總不良數／總產量；任一筆缺必要計數則不回傳加權值。列平均不是加權不良率。"]}

def main(argv=None) -> int:
    p=argparse.ArgumentParser(description="可離線執行的製造數據分析練習")
    p.add_argument("--data", type=Path, default=Path(__file__).parent/"demo"/"production.csv")
    p.add_argument("--line")
    p.add_argument("--sheet",help="Excel 指定工作表；未指定則讀作用中工作表")
    p.add_argument("--from-date", type=iso_date.fromisoformat)
    p.add_argument("--to-date", type=iso_date.fromisoformat)
    p.add_argument("--rate-unit", choices=("fraction","percent"), default="fraction")
    p.add_argument("--output",type=Path, help="輸出 JSON；不覆寫既有檔")
    p.add_argument("--question", help="選用 API 工具呼叫；不預設連網")
    p.add_argument("--allow-api", action="store_true", help="僅在考方允許向指定 API 提交相關資料時開啟")
    args=p.parse_args(argv)
    try:
        if args.question and not args.allow_api:
            raise ValueError("question_requires_explicit_allow_api")
        if args.output and args.output.exists():
            raise ValueError("output_exists")
        t=clean(args.data,args.rate_unit,args.sheet)
        if args.from_date or args.to_date:
            if args.from_date and args.to_date and args.from_date>args.to_date:
                raise ValueError("inverted_date_range")
            if "date" not in t["resolved_columns"]:
                raise ValueError("date_filter_needs_date_column")
            filtered, bad= [], 0
            for row in t["rows"]:
                try: d=iso_date.fromisoformat(row["date"][:10])
                except ValueError:
                    bad+=1
                    continue
                if (not args.from_date or d>=args.from_date) and (not args.to_date or d<=args.to_date):filtered.append(row)
            t["date_filter"]={"before":len(t["rows"]),"after":len(filtered),"invalid_or_missing_dates":bad}
            t["rows"]=filtered
        r=report(t,args.line)
        if args.question:
            import agent_api
            r=agent_api.run(args.question,t,report)
        s=json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False)
        if args.output:
            with args.output.open("x",encoding="utf-8") as f: f.write(s+"\n")
        print(s)
        return 0 if r["status"]=="ok" else 2
    except (OSError,ValueError,InvalidOperation,csv.Error) as exc:
        print(json.dumps({"status":"error","error":str(exc)},ensure_ascii=False),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
