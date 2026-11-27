"""Only the parsed table is kept in a short-lived session, no uploaded file persisted."""
from collections import OrderedDict
from pathlib import Path
from secrets import token_urlsafe
from tempfile import TemporaryDirectory
from threading import Lock
from time import monotonic
from zipfile import ZipFile
import re
import cloud_sessions
from main import clean

COOKIE="demo_table_session"
SUFFIXES={".csv",".tsv",".xlsx",".json",".jsonl",".ndjson"}
_lock=Lock()
_rows=OrderedDict()
TTL=7200

def parse(name,contents):
    if len(name)>130 or re.search(r"[/\\\x00-\x1f\x7f]",name) or Path(name).suffix.lower() not in SUFFIXES:
        raise ValueError("unsupported_table")
    if not contents:raise ValueError("empty_file")
    with TemporaryDirectory(prefix="demo-table-") as d:
        p=Path(d)/name;p.write_bytes(contents)
        if p.suffix.lower()==".xlsx":
            with ZipFile(p) as z:
                parts=z.infolist()
                if len(parts)>1200 or sum(x.file_size for x in parts)>24*1024*1024:
                    raise ValueError("excel_expands_too_large")
        result=clean(p)
        if result["input_row_count"]>30000:raise ValueError("too_many_rows")
        result.pop("source",None)
    return result

def _prune(now):
    for key,row in list(_rows.items()):
        if now-row[0]>TTL:_rows.pop(key,None)

def put(sid,name,value):
    store=cloud_sessions.active()
    if store is not None:
        if store.key("table",sid) is None or store.read("table",sid) is None:
            sid=store.new_id()
        store.update("table",sid,lambda _:{"name":name,"value":value})
        return sid
    with _lock:
        now=monotonic();_prune(now)
        if sid not in _rows:sid=token_urlsafe(24)
        _rows[sid]=(now,name,value)
        _rows.move_to_end(sid)
        while len(_rows)>12:_rows.popitem(last=False)
        return sid

def get(sid):
    if cloud_sessions.request_mode.get():
        store=cloud_sessions.backend()
        x=store.read("table",sid) if store else None
        return (x["name"],x["value"]) if x else (None,None)
    with _lock:
        _prune(monotonic())
        x=_rows.get(sid)
        return (x[1],x[2]) if x else (None,None)

def clear(sid):
    store=cloud_sessions.active()
    if store is not None:
        store.delete("table",sid)
        return
    with _lock:_rows.pop(sid,None)


def _collection(entry):
    if not entry:
        return {}
    _, name, value = entry
    return value if name is None else {name: value}


def tables(sid):
    if cloud_sessions.request_mode.get():
        store=cloud_sessions.backend()
        x=store.read("table",sid) if store else None
        return {} if not x else (dict(x["value"]) if x["name"] is None else {x["name"]:x["value"]})
    with _lock:
        _prune(monotonic())
        return dict(_collection(_rows.get(sid)))


def add_table(sid, name, value):
    store=cloud_sessions.active()
    if store is not None:
        if store.key("table",sid) is None or store.read("table",sid) is None:
            sid=store.new_id()
        def change(x):
            items={} if not x else (dict(x["value"]) if x["name"] is None else {x["name"]:x["value"]})
            if name in items:raise ValueError("duplicate_name")
            if len(items)>=8 or sum(len(item["rows"]) for item in items.values())+len(value["rows"])>20000:
                raise ValueError("table_library_full")
            return {"name":None,"value":{**items,name:value}}
        store.update("table",sid,change)
        return sid
    with _lock:
        now=monotonic()
        _prune(now)
        items=dict(_collection(_rows.get(sid)))
        if name in items:
            raise ValueError("duplicate_name")
        if len(items)>=8 or sum(len(item["rows"]) for item in items.values())+len(value["rows"])>20000:
            raise ValueError("table_library_full")
        if sid not in _rows:
            sid=token_urlsafe(24)
        _rows[sid]=(now,None,{**items,name:value})
        _rows.move_to_end(sid)
        while len(_rows)>12:
            _rows.popitem(last=False)
        return sid


def remove_table(sid, name):
    store=cloud_sessions.active()
    if store is not None:
        if store.read("table",sid) is None:return False
        class Missing(Exception):pass
        def change(x):
            items={} if not x else (dict(x["value"]) if x["name"] is None else {x["name"]:x["value"]})
            if name not in items:raise Missing
            items.pop(name)
            return {"name":None,"value":items}
        try:store.update("table",sid,change)
        except Missing:return False
        return True
    with _lock:
        now=monotonic()
        _prune(now)
        items=dict(_collection(_rows.get(sid)))
        if name not in items:
            return False
        items.pop(name)
        if items:
            _rows[sid]=(now,None,items)
        else:
            _rows.pop(sid,None)
        return True
