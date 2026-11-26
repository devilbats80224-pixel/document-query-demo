"""Small session-scoped document cache. Original files are never persisted."""
from collections import OrderedDict
from pathlib import Path
from secrets import token_urlsafe
from tempfile import TemporaryDirectory
from threading import Lock
from time import monotonic
import re

from document_io import TEXT_EXTS
from retrieval import load_docs

SUFFIXES=TEXT_EXTS|{".pdf"}
FILE_LIMIT=5*1024*1024
DOC_LIMIT=8
CHUNK_LIMIT=250
SESSION_LIMIT=12
TTL=7200
COOKIE="demo_document_session"
_lock=Lock()
_sessions=OrderedDict()

def parse_file(name, content):
    if not name or len(name)>130 or re.search(r"[/\\\x00-\x1f\x7f]",name) or Path(name).suffix.lower() not in SUFFIXES:
        raise ValueError("unsupported_file")
    if not content or len(content)>FILE_LIMIT:
        raise ValueError("empty_or_too_large")
    with TemporaryDirectory(prefix="demo-parse-") as d:
        p=Path(d)/name
        p.write_bytes(content)
        chunks=load_docs(Path(d))
    if not chunks:raise ValueError("no_extractable_content")
    return chunks

def _prune(now):
    for sid,row in list(_sessions.items()):
        if now-row[0]>=TTL:_sessions.pop(sid,None)

def snapshot(sid):
    now=monotonic()
    with _lock:
        _prune(now)
        if sid not in _sessions:return [],[]
        docs=_sessions[sid][1]
        _sessions[sid]=(now,docs);_sessions.move_to_end(sid)
        return [{"name":name,"chunks":len(chunks)} for name,chunks in docs.items()], [row for chunks in docs.values() for row in chunks]

def add(sid,name,chunks):
    now=monotonic()
    with _lock:
        _prune(now)
        new=sid not in _sessions
        docs={} if new else _sessions[sid][1]
        if name in docs:raise ValueError("duplicate_name")
        if len(docs)>=DOC_LIMIT or sum(map(len,docs.values()))+len(chunks)>CHUNK_LIMIT:
            raise ValueError("library_full")
        if new:
            while len(_sessions)>=SESSION_LIMIT:_sessions.popitem(last=False)
            sid=token_urlsafe(24)
        docs[name]=chunks
        _sessions[sid]=(now,docs);_sessions.move_to_end(sid)
        return sid

def clear(sid):
    with _lock:_sessions.pop(sid,None)

def remove(sid,name):
    with _lock:
        _prune(monotonic())
        row=_sessions.get(sid)
        return row is not None and row[1].pop(name,None) is not None
