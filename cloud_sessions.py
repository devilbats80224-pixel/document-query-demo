"""Short-lived parsed workspace state shared by Vercel function instances."""
from contextvars import ContextVar
from datetime import date, datetime, time
from decimal import Decimal
from math import isfinite
import os
from secrets import token_urlsafe
from typing import Any
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, ProxyHandler, build_opener
import json
import re

request_mode=ContextVar("demo_cloud_request",default=False)
TTL=7200
MAX_STATE_BYTES=3_500_000
SID=re.compile(r"[A-Za-z0-9_-]{32}")
UPSTASH_HOST=re.compile(r"[a-z0-9-]+\.upstash\.io")
TAG="_cloud_type"
CAS="""local now = redis.call('GET',KEYS[1])
local revision = now and string.sub(now,1,32) or ''
if revision ~= ARGV[1] then return 0 end
redis.call('SET',KEYS[1],ARGV[2],'EX',ARGV[3]); return 1"""


class CloudStorageError(RuntimeError):
    """Unavailable services and concurrent updates never look like empty data."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise CloudStorageError("cloud_store_redirect_refused")


def _safe(value):
    if isinstance(value,dict):
        result={k:_safe(v) for k,v in value.items()}
        return {TAG:["mapping",result]} if TAG in result else result
    if isinstance(value,(list,tuple)):
        return [_safe(v) for v in value]
    if isinstance(value,Decimal):
        return {TAG:["decimal",str(value)]}
    if isinstance(value,(datetime,date,time)):
        return {TAG:[type(value).__name__,value.isoformat()]}
    if isinstance(value,float) and not isfinite(value):
        return None
    return value


def _unsafe(value):
    if isinstance(value,list):
        return [_unsafe(v) for v in value]
    if not isinstance(value,dict):
        return value
    if set(value)=={TAG}:
        kind,body=value[TAG]
        if kind=="mapping":return {k:_unsafe(v) for k,v in body.items()}
        reader={"decimal":Decimal,"date":date.fromisoformat,"datetime":datetime.fromisoformat,
                "time":time.fromisoformat}.get(kind)
        if reader is None:raise CloudStorageError("cloud_store_invalid_state")
        return reader(body)
    return {k:_unsafe(v) for k,v in value.items()}


class RedisSessionBackend:
    def __init__(self,url,token):
        self.url=url
        self.token=token

    @staticmethod
    def new_id():
        return token_urlsafe(24)

    @staticmethod
    def key(bucket,sid):
        if bucket not in {"documents","table"} or not isinstance(sid,str) or SID.fullmatch(sid) is None:
            return None
        return f"document-demo-session-v1:{bucket}:{sid}"

    def command(self,*items):
        req=Request(self.url,data=json.dumps(items,ensure_ascii=False,separators=(",",":")).encode("utf-8"),
                    headers={"Authorization":"Bearer "+self.token,"Content-Type":"application/json"})
        try:
            with build_opener(ProxyHandler({}),NoRedirect()).open(req,timeout=4) as rsp:
                body=rsp.read(MAX_STATE_BYTES*2+65_537)
            if len(body)>MAX_STATE_BYTES*2+65_536:raise CloudStorageError("cloud_store_response_too_large")
            res=json.loads(body)
            if not isinstance(res,dict) or "error" in res or "result" not in res:
                raise CloudStorageError("cloud_store_unavailable")
            return res["result"]
        except (OSError,ValueError,UnicodeError,TypeError) as exc:
            raise CloudStorageError("cloud_store_unavailable") from exc

    def read(self,bucket,sid) -> dict[str,Any] | None:
        key=self.key(bucket,sid)
        if key is None:return None
        _,data=self.decode(self.command("GET",key))
        return data

    def decode(self,body) -> tuple[str,dict[str,Any] | None]:
        if body is None:return "",None
        if (not isinstance(body,str) or len(body)<34 or len(body.encode("utf-8"))>MAX_STATE_BYTES+33
                or body[32]!=":" or SID.fullmatch(body[:32]) is None):
            raise CloudStorageError("cloud_store_invalid_state")
        try:
            value=_unsafe(json.loads(body[33:]))
            if not isinstance(value,dict):raise CloudStorageError("cloud_store_invalid_state")
            return body[:32],value
        except (ValueError,TypeError,KeyError) as exc:
            raise CloudStorageError("cloud_store_invalid_state") from exc

    def update(self,bucket,sid,change,*,allow_create=True):
        key=self.key(bucket,sid)
        if key is None:raise CloudStorageError("cloud_store_bad_session")
        for _ in range(4):
            revision,old=self.decode(self.command("GET",key))
            if old is None and not allow_create:
                raise CloudStorageError("cloud_store_session_reset")
            if old is not None:allow_create=False
            value=change(old)
            encoded=json.dumps(_safe(value),ensure_ascii=False,separators=(",",":"),allow_nan=False)
            if len(encoded.encode("utf-8"))>MAX_STATE_BYTES:
                raise ValueError("cloud_workspace_capacity")
            # The previous revision is fixed-size regardless of workspace size.
            if self.command("EVAL",CAS,1,key,revision,self.new_id()+":"+encoded,TTL)==1:
                return value
        raise CloudStorageError("cloud_store_write_conflict")

    def delete(self,bucket,sid):
        key=self.key(bucket,sid)
        if key is None:return False
        return self.command("DEL",key)==1


def backend():
    primary=(os.getenv("UPSTASH_REDIS_REST_URL","").strip(),os.getenv("UPSTASH_REDIS_REST_TOKEN","").strip())
    linked=(os.getenv("KV_REST_API_URL","").strip(),os.getenv("KV_REST_API_TOKEN","").strip())
    value,token=primary if any(primary) else linked
    value=value.rstrip("/")
    try:
        url=urlsplit(value)
        if (url.scheme!="https" or not UPSTASH_HOST.fullmatch(url.hostname or "") or
                url.netloc!=url.hostname or url.path or url.query or url.fragment or not token):
            return None
    except ValueError:
        return None
    return RedisSessionBackend(value,token)


def active():
    if not request_mode.get():
        return None
    target=backend()
    if target is None:
        raise CloudStorageError("cloud_store_unconfigured")
    return target
