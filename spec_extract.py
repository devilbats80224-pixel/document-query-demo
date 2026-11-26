"""Strict offline extraction for the sample's numbered, explicitly labeled product lines."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

import extract


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    page: Annotated[int, Field(ge=1)]
    line: Annotated[int, Field(ge=1)]
    quote: Annotated[str, Field(min_length=1)]


class SpecItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    part_number: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,63}$")]
    category: str | None
    voltage_or_power: str | None
    compliance: list[str]
    notes: str | None
    evidence: Evidence


class DocumentResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    document_title: str | None
    items: list[SpecItem]
    unresolved: list[Evidence]


ITEM = re.compile(r"^\s*\d+[.、)]\s*(?:模組型號|料號|產品型號|Part(?:\s+number)?|Asset)\s*[:：]\s*([a-z0-9][a-z0-9._/-]{0,63})(?=\s|[,，;；]|$)",re.I)
LABEL = re.compile(r"(?:^|[;；，,])\s*(類別|Category|額定輸出|額定|Rating|安規|認證|Compliance|備註|Notes)\s*[:：]?\s*",re.I)
TITLE = re.compile(r"^(?:文件標題|Title)\s*[:：]\s*(.+)$",re.I)


def parse(text_pages: list[str]) -> DocumentResult:
    title=None
    data: dict[str,SpecItem] = {}
    unresolved=[]
    duplicates=set()
    aliases={"類別":"category","額定輸出":"rating","額定":"rating","安規":"compliance","認證":"compliance","備註":"notes"}
    for page,text in enumerate(text_pages,1):
        for i,raw in enumerate(text.splitlines(),1):
            line=raw.strip()
            if match:=TITLE.fullmatch(line):
                if title is None:
                    title=match[1]
                continue
            if not re.match(r"^\d+[.、)]",line):
                continue
            proof=Evidence(page=page,line=i,quote=raw)
            match=ITEM.match(line)
            if not match:
                unresolved.append(proof)
                continue
            key=match[1].casefold()
            if key in duplicates or key in data:
                if key in data:
                    unresolved.append(data.pop(key).evidence)
                duplicates.add(key)
                unresolved.append(proof)
                continue
            tail=line[match.end():]
            matches=list(LABEL.finditer(tail))
            values={}
            for n,m in enumerate(matches):
                field=aliases.get(m[1].casefold(),m[1].casefold())
                value=tail[m.end():matches[n+1].start() if n+1<len(matches) else len(tail)].strip(" ;；,，。")
                if value and field not in values:
                    values[field]=value
                elif value:
                    unresolved.append(proof)
                    break
            else:
                cert=values.get("compliance")
                tokens=[z.strip() for z in re.split(r"[,，、/]",cert) if z.strip()] if cert else []
                data[key]=SpecItem(part_number=match[1],category=values.get("category"),
                                   voltage_or_power=values.get("rating"),compliance=tokens,
                                   notes=values.get("notes"),evidence=proof)
    return DocumentResult(document_title=title,items=list(data.values()),unresolved=unresolved)



def main():
    p=argparse.ArgumentParser(description="取出有明確標籤的多筆產品；保留來源，不擅猜。")
    p.add_argument("document",type=Path)
    a=p.parse_args()
    try:
        result=parse(extract.pages(a.document))
    except (OSError,ValueError) as exc:
        print(f"文件無法解析：{exc}",file=sys.stderr)
        return 2
    print(result.model_dump_json(indent=2))
    return 0 if result.items else 2


if __name__=="__main__":
    raise SystemExit(main())
