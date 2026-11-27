"""Publish the original FastAPI workbench with a cloud-only security boundary."""
from hashlib import sha256
from hmac import compare_digest, new as hmac_new
import os
import re
from time import time

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.types import ASGIApp, Receive, Scope, Send

import api_fastapi
import cloud_sessions
import local_models

OWNER_COOKIE = "__Host-demo_cloud_owner"
SESSION_SECONDS = 4 * 60 * 60
NO_STORE = {"Cache-Control": "no-store"}
LOCAL_WRITES = frozenset({
    "/knowledge/files", "/analysis/file", "/manufacturing/file",
    "/extract/file", "/extract/workbook", "/workspace/uploads",
})
UPLOAD_LIMIT = 4_000_000
MODEL_SETTINGS = frozenset({"/integration/settings", "/models/settings"})
auth = HTTPBasic(auto_error=False)


def owner_secret():
    secret = os.getenv("DEMO_CLOUD_OWNER_PASSWORD", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", secret):
        return ""
    if any(compare_digest(secret.encode(), os.getenv(env, "").strip().encode())
           for env,_ in local_models.HOSTED_MODELS.values()):
        return ""
    return secret


def signature(secret, expiry):
    return hmac_new(secret.encode(), f"document-demo-owner-v1:{expiry}".encode(), sha256).hexdigest()


def valid_session(value):
    secret = owner_secret()
    expiry, _, mac = value.partition(".")
    if not secret or not re.fullmatch(r"[0-9]{1,12}", expiry) or not re.fullmatch(r"[a-f0-9]{64}", mac):
        return False
    now = int(time())
    return now < int(expiry) <= now + SESSION_SECONDS and compare_digest(mac, signature(secret, expiry))


class CloudBoundary:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        mode = cloud_sessions.request_mode.set(True)
        try:
            request.state.cloud_owner = valid_session(request.cookies.get(OWNER_COOKIE, ""))
            path = request.url.path.rstrip("/")
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                if request.headers.get("sec-fetch-site") == "cross-site":
                    return await JSONResponse({"detail":"same_origin_required"},403,headers=NO_STORE)(scope,receive,send)
                if path in MODEL_SETTINGS:
                    return await JSONResponse({"detail":"configure_through_vercel_environment"},403,headers=NO_STORE)(scope,receive,send)
                if path=="/models/chat" and not request.state.cloud_owner:
                    return await JSONResponse({"detail":"cloud_owner_login_required"},401,headers=NO_STORE)(scope,receive,send)
                if path in LOCAL_WRITES and cloud_sessions.backend() is None:
                    return await JSONResponse({"detail":"雲端上傳目前沒有配置儲存空間，請先使用內建練習。"},503,headers=NO_STORE)(scope,receive,send)
            if request.method=="POST" and path in LOCAL_WRITES:
                size=request.headers.get("content-length","")
                if size and (not re.fullmatch(r"[0-9]{1,10}",size) or int(size)>UPLOAD_LIMIT):
                    return await JSONResponse({"detail":"雲端單檔上限為 4 MB。"},413,headers=NO_STORE)(scope,receive,send)
                received=0
                upstream_receive=receive

                async def bounded_receive():
                    nonlocal received
                    message=await upstream_receive()
                    received+=len(message.get("body",b""))
                    if received>UPLOAD_LIMIT:
                        raise HTTPException(413,"雲端單檔上限為 4 MB。",headers=NO_STORE)
                    return message

                await self.app(scope, bounded_receive, send)
                return
            await self.app(scope, receive, send)
        finally:
            cloud_sessions.request_mode.reset(mode)


app = FastAPI(title="文件工作台 · Vercel", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(CloudBoundary)


@app.get("/owner/")
def owner_login(credentials: HTTPBasicCredentials | None = Depends(auth)):
    secret = owner_secret()
    if not secret:
        raise HTTPException(404, "cloud_owner_chat_disabled", headers=NO_STORE)
    if not credentials or not (compare_digest(credentials.username.encode(), b"owner") and
                               compare_digest(credentials.password.encode(), secret.encode())):
        raise HTTPException(401, "owner_auth_required", headers={**NO_STORE,
                            "WWW-Authenticate":'Basic realm="Demo Owner", charset="UTF-8"'})
    expiry = str(int(time()) + SESSION_SECONDS)
    response = RedirectResponse("/models", 303, headers=NO_STORE)
    response.set_cookie(OWNER_COOKIE, f"{expiry}.{signature(secret, expiry)}",
                        max_age=SESSION_SECONDS, secure=True, httponly=True, samesite="strict", path="/")
    return response


app.mount("/", api_fastapi.app)
