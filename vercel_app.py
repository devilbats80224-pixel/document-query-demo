"""Cloud-only demo. Never mount the Mac app's local-state or model write routes."""
from functools import lru_cache
from hmac import compare_digest
from html import escape
import os
from pathlib import Path
import re

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, ConfigDict, Field

import generic_analysis
import local_models
from main import clean, report
from studio import query_tools

DEMO = Path(__file__).resolve().parent / "demo"
NO_STORE = {"Cache-Control": "no-store"}
PAGE_HEADERS = {**NO_STORE,
                "Referrer-Policy":"no-referrer",
                "X-Content-Type-Options":"nosniff",
                "X-Frame-Options":"DENY"}
app = FastAPI(title="文件查詢 Demo · 雲端版", docs_url=None, redoc_url=None, openapi_url=None)
auth = HTTPBasic(auto_error=False)


def page(title, body):
    return HTMLResponse(f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f4f8fa;color:#17283a;font:16px/1.6 system-ui,sans-serif;overflow-wrap:anywhere}}
main{{max-width:56rem;margin:auto;padding:16px}}section{{background:white;border:1px solid #d6e2e8;border-radius:14px;padding:clamp(12px,4vw,24px);margin:16px 0}}
nav{{display:flex;flex-wrap:wrap;gap:12px}}nav a{{display:inline-flex;align-items:center;min-height:44px}}
form{{display:grid;gap:8px}}a{{color:#165883}}input,select,button{{max-width:100%;min-width:0;font:inherit;padding:.55rem;min-height:44px}}
button{{background:#165883;color:white;border:1px solid transparent;border-radius:8px}}button:disabled{{opacity:.55}}pre{{white-space:pre-wrap}}
</style></head><body><main><nav aria-label="導覽"><a href="/">雲端 Demo</a><a href="/knowledge">文件查詢</a><a href="/owner/">私人模型區</a></nav>
<h1>{escape(title)}</h1>{body}</main></body></html>""", headers=PAGE_HEADERS)


@app.get("/health")
def health():
    return {"status":"ok","mode":"vercel_cloud","uploads":False,"local_models":False}


@app.get("/")
@app.get("/workspace")
def home():
    return page("文件查詢 Demo · Vercel 雲端版", """<section><p>雲端版只使用隨程式附送的內建合成資料，不接收上傳，不保留上傳檔案，也不連本機模型。</p>
<p>想上傳自己的文件、保留本地模型和離線使用，請開 Mac Docker 版。</p>
<p><a href="/knowledge?q=DEMO-100+E-402">試查內建文件</a> · <a href="/agent?q=L1+產線不良率">試查內建製造資料</a></p>
<p>聊天是獨立的功能，只有已登入的擁有者可以使用已設定的雲端模型。不會把文件或資料表附給模型。</p></section>""")


@lru_cache(maxsize=1)
def fixtures():
    return clean(DEMO / "production.csv"), generic_analysis.read(DEMO / "finance.csv")


@app.get("/knowledge")
@app.get("/agent")
def samples(q: str = Query(default="", max_length=250)):
    result_html = ""
    if q.strip():
        manufacturing, table = fixtures()
        result = query_tools(q,"demo",None,None,None,"finance.csv（示範）",table,
                             manufacturing,(),report,model="bm25")
        evidence = "".join(f"<li>{escape(row)}</li>" for row in result["evidence"])
        result_html = f"""<section><h2>查詢結果（非模型生成）</h2><p>{escape(result['answer'])}</p>
<p>{escape(result['tool'])}</p><h3>可引用片段與來源</h3><ul>{evidence}</ul></section>"""
    return page("內建合成文件與資料", f"""<section><p>只查內建示範，不讀取瀏覽器資料或附件。</p>
<form action="/knowledge"><label for="q">查詢</label><input id="q" name="q" value="{escape(q,quote=True)}" maxlength="250" required>
<button>查詢</button></form></section>{result_html}""")


def owner_required(credentials: HTTPBasicCredentials | None = Depends(auth)):
    secret = os.getenv("DEMO_CLOUD_OWNER_PASSWORD", "")
    # A separate, deliberately strong password prevents a billed public proxy;
    # a key without this password never enables generation.
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}",secret) or any(compare_digest(secret.encode(),os.getenv(env,"").strip().encode()) for env,_ in local_models.HOSTED_MODELS.values()):
        raise HTTPException(404,"cloud_owner_chat_disabled",headers=NO_STORE)
    if not credentials:
        raise HTTPException(401,"owner_auth_required",headers={**NO_STORE,"WWW-Authenticate":'Basic realm="Demo Owner", charset="UTF-8"'})
    valid_user = compare_digest(credentials.username.encode(), b"owner")
    valid_secret = compare_digest(credentials.password.encode(), secret.encode())
    if not (valid_user and valid_secret):
        raise HTTPException(401,"owner_auth_required",headers={**NO_STORE,"WWW-Authenticate":'Basic realm="Demo Owner", charset="UTF-8"'})


OWNER_SCRIPT = """<script>
const form=document.querySelector('#cloud-chat');
if(form){
 const model=form.querySelector('select'), prompt=form.querySelector('textarea'), result=document.querySelector('#cloud-reply'),
       selected=document.querySelector('#cloud-current'), actual=document.querySelector('#cloud-used'), button=form.querySelector('button'),
       refresh=()=>{selected.textContent='目前選用：'+(model.value?model.selectedOptions[0].textContent:'未選擇');button.disabled=!model.value||!!model.selectedOptions[0]?.disabled;};
 model.onchange=()=>{refresh();actual.textContent='本次實際使用：尚未生成';result.textContent='';};
 refresh();
 form.onsubmit=async e=>{
  e.preventDefault();if(!model.value||model.selectedOptions[0]?.disabled)return;button.disabled=true;model.disabled=true;actual.textContent='本次實際使用：尚未生成';result.textContent='正在等待模型回答…';
  try{
   const r=await fetch('/owner/chat',{method:'POST',headers:{'Content-Type':'application/json','X-Demo-Cloud-Chat':'1'},body:JSON.stringify({model:model.value,question:prompt.value})});
   if(!r.ok){
    if(r.status===503)model.selectedOptions[0].disabled=true;
    result.textContent='所選模型目前不能生成回答；請改選其他模型或重新檢查。';return;
   }
   const data=await r.json();actual.textContent='本次實際使用：'+data.model+'（'+data.provider+'）';result.textContent=data.answer;
  }catch{result.textContent='連線中斷，沒有生成回答。';}
  finally{model.disabled=false;refresh();}
 };
}
</script>"""


@app.get("/owner/", dependencies=[Depends(owner_required)])
def owner_chat_page():
    models = [(provider,model,label) for provider,(_,label) in local_models.HOSTED_MODELS.items()
              for model in local_models.provider_chat_models(provider)]
    if not models:
        return page("私人模型區", "<section><p>沒有可用模型，無法生成回答。請檢查 Vercel 專案的模型設定。</p></section>")
    options = "".join(f'<option value="{escape(provider+":"+model,quote=True)}">{escape(model)}（{label}）</option>'
                      for provider,model,label in models)
    return page("私人模型區", f"""<section><p>可在已設定的 Gemini 與 OpenAI 模型之間切換。首次生成才會確認該模型能回答。送出只會把你輸入的文字交給所選服務，可能用到 API 額度。</p>
<form id="cloud-chat"><label for="cloud-model">聊天模型</label><select id="cloud-model" required><option value="">請選模型</option>{options}</select>
<p id="cloud-current">目前選用：未選擇</p>
<label for="cloud-prompt">問題</label><textarea id="cloud-prompt" maxlength="350" rows="4" required></textarea>
<button disabled>生成回答</button></form><p id="cloud-used">本次實際使用：尚未生成</p><pre id="cloud-reply" role="status"></pre>
<p><a href="/owner/">重新檢查模型</a></p></section>{OWNER_SCRIPT}""")


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = Field(min_length=1,max_length=110)
    question: str = Field(min_length=1,max_length=350)


@app.post("/owner/chat", dependencies=[Depends(owner_required)])
def owner_chat(request: Request, body: ChatRequest):
    if request.headers.get("x-demo-cloud-chat") != "1" or request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403,"same_origin_required",headers=NO_STORE)
    question = body.question.strip()
    if not question:
        raise HTTPException(422,"question_required",headers=NO_STORE)
    try:
        provider,separator,selected=body.model.partition(":")
        if not separator or provider not in local_models.HOSTED_MODELS:
            raise ValueError("unknown_model_provider")
        answer,model = local_models.provider_chat(selected,question,provider=provider)
    except ValueError as exc:
        raise HTTPException(503,"model_unavailable",headers=NO_STORE) from exc
    return JSONResponse({"provider":local_models.HOSTED_MODELS[provider][1],"model":model,"answer":answer},headers=NO_STORE)
