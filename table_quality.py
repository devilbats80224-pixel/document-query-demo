"""Read-only profiling plus explicitly selected, reversible analysis filters."""
from collections import Counter
from datetime import date
from decimal import Decimal
from generic_analysis import number, numeric_fields

UNITS={"currency","ccy","幣別","貨幣","unit","單位"}

def profile(table, value="", day="", unit="", *, deduplicate=False, exclude_outliers=False):
    fields=table["fields"]
    rows=table["rows"]
    numeric=numeric_fields(table)
    check=value or (numeric[0] if numeric else "")
    if check and check not in fields:
        raise ValueError("column_not_found")
    if day and day not in fields or unit and unit not in fields:
        raise ValueError("column_not_found")
    missing=Counter()
    duplicates=set()
    seen=set()
    for i,r in enumerate(rows):
        missing.update(k for k in fields if not r[k])
        signature=tuple(r[k] for k in fields)
        if signature in seen:duplicates.add(i)
        else:seen.add(signature)
    parsed=[number(r[check]) for r in rows] if check else []
    bad_number=sum(bool(r[check]) and n is None for r,n in zip(rows,parsed))
    bad_dates=0
    if day:
        for r in rows:
            if not r[day]:continue
            try:date.fromisoformat(r[day][:10])
            except ValueError:bad_dates+=1
    units=[unit] if unit else [k for k in fields if k.casefold() in UNITS]
    unit_sets={k:sorted({r[k] for r in rows if r[k]})[:10] for k in units}
    # Compare like with like; if no explicit unit exists, an entire column is
    # one group. Missing labels in a known unit column aren't compared.
    groups={}
    for i,n in enumerate(parsed):
        if n is None or any(not rows[i][k] for k in units):continue
        key=tuple(rows[i][k] for k in units)
        groups.setdefault(key,[]).append((i,n))
    unusual=set();eligible=0
    for population in groups.values():
        if len(population)<8:continue
        a=sorted(n for _,n in population)
        def quartile(k):
            pos=(len(a)-1)*k; i,r=divmod(pos,4)
            return a[i] if r==0 else (a[i]*(4-r)+a[i+1]*r)/4
        q1,q3=quartile(1),quartile(3)
        spread=(q3-q1)*Decimal("1.5")
        eligible+=1
        unusual.update(i for i,n in population if n<q1-spread or n>q3+spread)
    dropped=(duplicates if deduplicate else set()) | (unusual if exclude_outliers else set())
    filtered={**table,"rows":[r for i,r in enumerate(rows) if i not in dropped]} if dropped else table
    return filtered,dict(rows=len(rows),columns=len(fields),malformed_rows=table["excluded"],
        missing=dict(missing),duplicate_rows=len(duplicates),unusual=len(unusual),unusual_groups=eligible,
        duplicate_preview=[i+1 for i in sorted(duplicates)[:10]], unusual_preview=[i+1 for i in sorted(unusual)[:10]],
        removed_missing_cells=sum(not rows[i][key] for i in dropped for key in fields),
        inspected_numeric=check,inspected_date=day,invalid_numeric=bad_number,invalid_dates=bad_dates,unit_values=unit_sets,
        removed=len(dropped),remaining=len(filtered["rows"]),deduplicate=deduplicate,exclude_outliers=exclude_outliers,
        sample_columns=fields[:8],sample_rows=[[r[k] for k in fields[:8]] for r in rows[:5]])
