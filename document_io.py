"""Read local document text only, without executing embedded code or resolving links."""
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as etree
from zipfile import BadZipFile, ZipFile

TEXT_EXTS={".txt",".md",".html",".htm",".docx"}
TEXT_CAP=2*1024*1024
W="{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

class VisibleHTML(HTMLParser):
    BLOCK={"p","br","div","li","tr","section","article","h1","h2","h3","h4","header","footer"}
    HIDDEN={"script","style","head","title","template","noscript","svg"}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden=[]
        self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in self.HIDDEN:self.hidden.append(tag)
        if not self.hidden and tag in self.BLOCK:self.parts.append("\n")
    def handle_endtag(self,tag):
        if self.hidden:
            if tag==self.hidden[-1]:self.hidden.pop()
        elif tag in self.BLOCK:self.parts.append("\n")
        elif tag in {"td","th"}:self.parts.append(" | ")
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)
    def text(self):
        return "\n".join(s.strip(" |\t") for s in "".join(self.parts).splitlines() if s.strip(" |\t"))

def _docx(path):
    try:
        with ZipFile(path) as z:
            if len(z.infolist())>1500:raise ValueError("docx_too_many_parts")
            matches=[x for x in z.infolist() if x.filename=="word/document.xml"]
            if len(matches)!=1:raise ValueError("docx_document_part_missing_or_ambiguous")
            part=matches[0]
            if part.file_size>TEXT_CAP:raise ValueError("docx_text_part_too_large")
            data=z.read(part)
    except (BadZipFile,RuntimeError) as exc:
        raise ValueError("invalid_or_encrypted_docx") from exc
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper() or b'\0' in data:
        raise ValueError("unsupported_docx_xml")
    try: root=etree.fromstring(data)
    except etree.ParseError as exc:raise ValueError("malformed_docx_xml") from exc
    body=root.find(W+"body")
    if body is None:raise ValueError("docx_body_missing")
    def plain(el):
        return "".join(x.text or "" for x in el.iter(W+"t")).strip()
    rows=[]
    for el in body:
        if el.tag==W+"p":
            rows.append(plain(el))
        elif el.tag==W+"tbl":
            for row in el.findall(W+"tr"):
                cells=[plain(c) for c in row.findall(W+"tc")]
                rows.append(" | ".join(cells))
                if len(cells)==2 and cells[0] and cells[1]:
                    rows.append(cells[0]+": "+cells[1])
    return "\n".join(x for x in rows if x)

def read(path:Path):
    ext=path.suffix.lower()
    if ext not in TEXT_EXTS:raise ValueError("unsupported_document_format")
    if ext==".docx":
        result=_docx(path)
    else:
        if path.stat().st_size>TEXT_CAP:raise ValueError("text_document_too_large")
        result=path.read_text(encoding="utf-8-sig")
        if ext in {".html",".htm"}:
            parser=VisibleHTML();parser.feed(result);parser.close()
            result=parser.text()
    if not result.strip():raise ValueError("no_extractable_document_text")
    return result
