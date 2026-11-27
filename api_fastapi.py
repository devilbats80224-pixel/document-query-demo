"""Optional FastAPI demo; launch on loopback and use only if requested."""
from pathlib import Path
from html import escape
from typing import Literal
import studio
import cloud_sessions
import workbook_extract
import calculation_plan
from extract import PdfTextReviewRequired
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from urllib.parse import unquote, urlencode
from pypdf.errors import PyPdfError
import local_library
import local_table
import generic_analysis
import table_quality
import local_models
import model_settings
from zipfile import BadZipFile
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from main import clean,report
app=FastAPI(title="Offline Practice API")
@app.exception_handler(cloud_sessions.CloudStorageError)
async def storage_error(_request:Request,_error:cloud_sessions.CloudStorageError):
    if str(_error) in {"cloud_store_session_reset","cloud_store_write_conflict"}:
        return JSONResponse({"detail":"工作台已在另一個分頁更新或清除。請重新整理後再試。"},status_code=409,
                            headers={"Cache-Control":"no-store"})
    return JSONResponse({"detail":"雲端儲存暫時無法使用；未變更既有的資料。"},status_code=503,
                        headers={"Cache-Control":"no-store"})

demo_dir=Path(__file__).parent/"demo"
sample_files={"csv":"CSV","tsv":"TSV","xlsx":"Excel .xlsx","jsonl":"JSONL"}
default_table=clean(demo_dir/"production.csv")
class ReportQuery(BaseModel):
    model_config=ConfigDict(extra="forbid")
    line: str|None=Field(default=None,min_length=1,max_length=64)
@app.get("/health")
def health():
    if cloud_sessions.request_mode.get():
        return {"status":"ok","mode":"vercel_cloud","uploads":cloud_sessions.backend() is not None,"local_models":False}
    return {"status":"ok","mode":"local_offline"}
@app.post("/report")
def make_report(q:ReportQuery):
    r=report(default_table,q.line,0)
    r.get("data_quality",{}).pop("source",None)
    if r["status"]!="ok":raise HTTPException(status_code=404,detail=r["status"])
    return r

REASONS = {
    "defects_exceed_output": "不良數大於產量",
    "blank": "空白列",
    "wrong_number_of_columns": "欄位數量不符",
    "missing_line": "缺少產線",
    "zero_output": "產量為零",
    "missing_rate": "無法計算不良率",
    "invalid_number": "數字格式無效",
    "bad_number_grouping": "千分位格式無效",
    "count_must_be_nonnegative_integer": "數量須為有效的非負整數",
    "rate_outside_0_to_1": "不良率超出 0% 至 100%",
}

def uploaded_tables(request):
    return local_table.tables(request.cookies.get(generic_analysis.COOKIE))

def latest_analysis_table(request):
    items=uploaded_tables(request)
    name=next(reversed(items),None)
    return name,items.get(name)


@app.get("/workspace",response_class=HTMLResponse)
def show_workspace(request:Request):
    docs,_=local_library.snapshot(request.cookies.get(local_library.COOKIE))
    return HTMLResponse(studio.workspace(docs,tuple(uploaded_tables(request))),headers={"Cache-Control":"no-store"})

@app.get("/",response_class=HTMLResponse)
def demo_page(request:Request,line: str|None = Query(default=None,max_length=64),
              sample: Literal["csv","tsv","xlsx","jsonl","local"]="local"):
    filename,own=local_table.get(request.cookies.get(local_table.COOKIE))
    upload=studio.table_upload(filename).replace("上傳並分析","上傳表格")
    options={"local":"我的表格",**{key:f"內建示範 · {label}" for key,label in sample_files.items()}}
    if sample=="local" and own is None:
        choices="".join(f'<option value="{key}">{label}</option>' for key,label in options.items())
        body=upload+f"""<section class="work-card mfg-search"><h2>查詢產線</h2>
        <form method="get" action="/#table-results"><label for="line">產線名稱或代號</label>
        <input id="line" name="line" maxlength="64" placeholder="例如：A01" value="{escape(line or '',quote=True)}">
        <label for="sample">資料來源</label><select id="sample" name="sample">{choices}</select><button>查詢</button></form>
        <p class="empty" id="table-results" role="status">尚未上傳表格。請先上傳，或切換為內建示範。</p></section>"""
        return HTMLResponse(studio.layout("/","製造資料分析","輸入產線名稱或代號，核對計算與排除明細。",body),headers={"Cache-Control":"no-store"})
    table=own if sample=="local" else (clean(demo_dir/("production."+sample)) if sample!="csv" else default_table)
    choices="".join(f'<option value="{key}"'+(' selected' if key==sample else '')+
                    f'>{value}</option>' for key,value in options.items())
    selected=(line or (next((r["line"] for r in table["rows"]),"L1") if sample!="local" else "")).strip().upper()
    r=report(table,selected,0) if selected else {"status":"empty"}
    reason_list=table["skipped"]
    rows=[]
    for item in table["skipped_examples"]:
        numbers=(f'產量 {item["output_qty"]:,} ／不良數 {item["defect_count"]:,}'
                 if "output_qty" in item else "—")
        rows.append(f'<tr><td>{item["row"]}</td><td>{escape(item.get("line","—"))}</td>'
                    f'<td>{numbers}</td><td>{escape(REASONS.get(item["reason"],"格式未通過檢查"))}</td></tr>')
    summary="；".join(f'{REASONS.get(reason,"格式未通過檢查")}（{n} 筆）' for reason,n in reason_list.items())
    row_table=('''<table><thead><tr><th>原檔列號</th><th>產線</th><th>原始數值</th><th>排除原因</th></tr></thead><tbody>'''+
               "".join(rows)+"</tbody></table>") if rows else "<p>沒有可顯示的異常列明細。</p>"
    result="<p class='empty' role='status'>選擇產線再開始查詢。</p>" if not selected else "<p class='empty' role='status'>查無有效資料。不回傳 0% 以免誤判。</p>"
    if r["status"]=="ok":
        o=r["overall"]
        rate=lambda v: f"{v:.2%}" if v is not None else "資料不足"
        formula=(f'{o["defect_count"]:,} 不良 ÷ {o["output_qty"]:,} 產量'
                 if o["defect_count"] is not None and o["output_qty"] is not None else "缺少產量或不良數")
        result=f"""<div class="cards" role="status">
        <article><small>加權不良率</small><strong>{rate(o['weighted_defect_rate'])}</strong><p>{formula}</p></article>
        <article><small>逐列平均不良率</small><strong>{rate(o['mean_row_defect_rate'])}</strong><p>每列比率直接平均</p></article>
        <article><small>選定產線的有效資料</small><strong>{o['n']} 筆</strong><p>只計算 {escape(selected)} 的有效列</p></article></div>"""
        if o["defect_count"] is not None and o["output_qty"] is not None:
            result+=f"""<section class="formula-card"><small>指標怎麼算 · {escape(selected)}</small><h3>加權不良率</h3>
             <div class="fraction-visual"><b>{o['defect_count']:,} 不良</b><span>÷</span><b>{o['output_qty']:,} 產量</b><span>=</span><strong>{rate(o['weighted_defect_rate'])}</strong></div></section>"""
    roster="".join(f'<option value="{escape(v,quote=True)}">' for v in sorted({row["line"] for row in table["rows"]})[:80])
    body=upload+f"""<section class="work-card mfg-search"><h2>查詢產線</h2><form method="get" action="/#table-results"><label for="line">產線名稱或代號</label><input id="line" list="table-lines" name="line" maxlength="64" placeholder="輸入或從清單選擇" value="{escape(selected,quote=True)}"><datalist id="table-lines">{roster}</datalist><label for="sample">資料來源</label><select id="sample" name="sample">{choices}</select><button>查詢</button></form></section>
<div class="data-layout"><section class="work-card mfg-overview" id="table-results"><span class="section-index">指標與計算</span><h2>計算結果</h2>{result}</section>
<section class="work-card metric-quality"><span class="section-index">計算透明度</span><h2>排除明細</h2><details><summary>資料品質（全檔）・排除 {sum(reason_list.values())} 筆</summary>
<p>排除列不參與不良率計算；此處列全檔異常，不代表都來自目前產線。</p>
<p>{escape(summary or "沒有排除資料。")}</p>{row_table}<small>明細最多顯示前 10 筆。</small></details></section></div>"""
    body+=studio.components(["Python：清洗、排除異常、加權統計","openpyxl：解析本機 Excel 範例","FastAPI + Pydantic：可獨立呼叫 JSON 報表"])
    return HTMLResponse(studio.layout("/","製造資料分析","先選表格，再查產線。結果會顯示原始分子和分母。",body),headers={"Cache-Control":"no-store"})

@app.post("/manufacturing/file")
async def upload_table(request:Request):
    if request.headers.get("x-demo-local")!="1":raise HTTPException(403,"local_action_required")
    name=unquote(request.headers.get("x-demo-filename",""))
    data=bytearray()
    async for chunk in request.stream():
        if len(data)+len(chunk)>local_library.FILE_LIMIT:raise HTTPException(413,"file_over_5mb")
        data.extend(chunk)
    try:
        table=await run_in_threadpool(local_table.parse,name,bytes(data))
    except (ValueError,OSError,BadZipFile) as exc:
        code=str(exc)
        if code not in {"unsupported_table","empty_file","too_many_rows","excel_expands_too_large","need_line_and_output_plus_defects_or_rate","blank_or_duplicate_column","nested_json_requires_explicit_mapping"}:code="invalid_table"
        raise HTTPException(422,code) from exc
    sid=await run_in_threadpool(local_table.put,request.cookies.get(local_table.COOKIE),name,table)
    response=JSONResponse({"status":"ready","valid_rows":len(table["rows"])})
    response.set_cookie(local_table.COOKIE,sid,max_age=local_table.TTL,httponly=True,samesite="strict",secure=cloud_sessions.request_mode.get())
    return response

@app.delete("/manufacturing/file")
def clear_table(request:Request):
    if request.headers.get("x-demo-local")!="1":raise HTTPException(403,"local_action_required")
    local_table.clear(request.cookies.get(local_table.COOKIE))
    r=JSONResponse({"status":"cleared"});r.delete_cookie(local_table.COOKIE)
    return r

@app.get("/knowledge",response_class=HTMLResponse)
def show_knowledge(request: Request,q: str|None=Query(default=None,min_length=1,max_length=250),
                   mode: Literal["hybrid","bm25","vector"]="hybrid",source: Literal["demo","local"]="local"):
    if q is not None and not q.strip(): raise HTTPException(422,"question_required")
    q=q or ("DEMO-100 E-402" if source=="demo" else "")
    docs,chunks=local_library.snapshot(request.cookies.get(local_library.COOKIE))
    engine="character" if cloud_sessions.request_mode.get() else model_settings.local_load()["embedding"]
    embedding_ready=engine!="qwen" or local_models.available("embedding")
    return HTMLResponse(studio.knowledge(q,mode,source=source,docs=docs,chunks=chunks,embedding_engine=engine,embedding_ready=embedding_ready),headers={"Cache-Control":"no-store","Referrer-Policy":"no-referrer"})

@app.post("/knowledge/files")
async def upload_knowledge(request:Request):
    if request.headers.get("x-demo-local")!="1":raise HTTPException(403,"local_action_required")
    name=unquote(request.headers.get("x-demo-filename",""))
    content=bytearray()
    async for chunk in request.stream():
        if len(content)+len(chunk)>local_library.FILE_LIMIT:raise HTTPException(413,"file_over_5mb")
        content.extend(chunk)
    try:
        chunks=await run_in_threadpool(local_library.parse_file,name,bytes(content))
        sid=await run_in_threadpool(local_library.add,request.cookies.get(local_library.COOKIE),name,chunks)
    except PdfTextReviewRequired as exc:
        return JSONResponse({"detail":"ocr_required","review_pages":exc.page_numbers,"accepted":False},status_code=422)
    except ValueError as exc:
        code=str(exc)
        if "ocr" in code:code="ocr_required"
        elif code not in {"unsupported_file","empty_or_too_large","duplicate_name","library_full","no_extractable_content","cloud_workspace_capacity"}:
            code="file_could_not_be_parsed"
        raise HTTPException(422,code) from exc
    except cloud_sessions.CloudStorageError:
        raise
    except (OSError,RuntimeError,PyPdfError) as exc:
        raise HTTPException(422,"file_could_not_be_parsed") from exc
    response=JSONResponse({"name":name,"chunks":len(chunks),"status":"indexed"})
    response.set_cookie(local_library.COOKIE,sid,max_age=local_library.TTL,httponly=True,samesite="strict",secure=cloud_sessions.request_mode.get())
    return response

@app.delete("/knowledge/files")
def clear_knowledge(request:Request,name:str|None=Query(default=None,max_length=130)):
    if request.headers.get("x-demo-local")!="1":raise HTTPException(403,"local_action_required")
    sid=request.cookies.get(local_library.COOKIE)
    if name is not None:
        if not local_library.remove(sid,name):raise HTTPException(404,"file_not_found")
        return {"status":"removed"}
    local_library.clear(sid)
    response=JSONResponse({"status":"cleared"})
    response.delete_cookie(local_library.COOKIE)
    return response

FIELD_SESSION = "demo_field_document"
@app.delete("/workspace/uploads")
def clear_workspace_uploads(request:Request,scope:Literal["workspace","extract","workbook","agent"]):
    if request.headers.get("x-demo-local")!="1":raise HTTPException(403,"local_action_required")
    scopes={
        "workspace":(local_library.COOKIE,generic_analysis.COOKIE),
        "extract":(FIELD_SESSION,workbook_extract.COOKIE),
        "workbook":(workbook_extract.COOKIE,),
        "agent":(local_library.COOKIE,generic_analysis.COOKIE,local_table.COOKIE,workbook_extract.COOKIE),
    }
    response=JSONResponse({"status":"cleared"})
    for key in scopes[scope]:
        (local_library if key==local_library.COOKIE else local_table).clear(request.cookies.get(key))
        response.delete_cookie(key)
    return response

FIELD_FORMATS = {".pdf":"pdf",".docx":"docx",".txt":"text",".md":"md",".html":"html",".htm":"html"}

def _parse_field_document(suffix, data):
    from tempfile import TemporaryDirectory
    from extract import pages
    if not data:
        raise ValueError("empty_file")
    with TemporaryDirectory(prefix="demo-field-") as folder:
        path=Path(folder)/("source"+suffix)
        path.write_bytes(data)
        content=pages(path)
    if sum(len(page) for page in content)>2*1024*1024:
        raise ValueError("document_too_large")
    return content

@app.post("/extract/file")
async def upload_extraction_file(request:Request):
    if request.headers.get("x-demo-local")!="1":
        raise HTTPException(403,"local_action_required")
    import re
    name=unquote(request.headers.get("x-demo-filename",""))
    suffix=Path(name).suffix.lower()
    if not name or len(name)>130 or re.search(r"[/\\\x00-\x1f\x7f]",name) or suffix not in FIELD_FORMATS:
        raise HTTPException(422,"unsupported_file")
    data=bytearray()
    async for chunk in request.stream():
        if len(data)+len(chunk)>local_library.FILE_LIMIT:
            raise HTTPException(413,"file_over_5mb")
        data.extend(chunk)
    try:
        pages=await run_in_threadpool(_parse_field_document,suffix,bytes(data))
    except PdfTextReviewRequired as exc:
        return JSONResponse({"detail":"ocr_required","review_pages":exc.page_numbers,"accepted":False},status_code=422)
    except (ValueError,OSError,RuntimeError,PyPdfError) as exc:
        reason="ocr_required" if "ocr_required" in str(exc) else "unsupported_or_unreadable"
        raise HTTPException(422,reason) from exc
    sid=await run_in_threadpool(local_table.put,request.cookies.get(FIELD_SESSION),name,(FIELD_FORMATS[suffix],pages))
    response=JSONResponse({"status":"ready","name":name,"format":FIELD_FORMATS[suffix]})
    response.set_cookie(FIELD_SESSION,sid,max_age=local_table.TTL,httponly=True,samesite="strict",secure=cloud_sessions.request_mode.get())
    return response

@app.get("/extract",response_class=HTMLResponse)
def show_fields(request:Request,file: Literal["text","pdf","docx","md","html","xlsx"]|None=None,
                fields: str|None=Query(default=None,min_length=1,max_length=250),
                source: Literal["demo","local"]|None=None,sheet:str|None=Query(default=None,max_length=64),
                field:list[str]=Query(default=[]),download:bool=False):
    source=source or ("demo" if file in {"text","pdf","docx"} else "local")
    file=file or "text"
    doc_name,doc=local_table.get(request.cookies.get(FIELD_SESSION))
    book_name,sheets=local_table.get(request.cookies.get(workbook_extract.COOKIE))
    try:
        result=None
        selected=None
        if file=="xlsx" and sheets:
            selected=sheet if sheet is not None else next(iter(sheets),"")
            if selected not in sheets or len(field)>100:
                raise ValueError("invalid_sheet")
            if field:
                result=workbook_extract.project(book_name,sheets,selected,field)
        if download:
            filename="workbook-columns.json"
            if file!="xlsx":
                document,pages=studio.extraction_document(file,source,doc_name,doc)
                requested=fields or ("設備,狀態,負責人" if source=="demo" else "")
                if pages is not None and requested:
                    result=studio.structured_document(document,pages,requested)
                filename="document-fields.json"
            if result is None:raise ValueError("no_result")
            return JSONResponse(result,headers={"Cache-Control":"no-store","Content-Disposition":f'attachment; filename="{filename}"'})
        return HTMLResponse(studio.fields_page(file,fields,source=source,doc_name=doc_name,doc=doc,
                            book_name=book_name,sheets=sheets or {},selected=selected,chosen=field,table_result=result),
                            headers={"Cache-Control":"no-store"})
    except ValueError as exc:
        raise HTTPException(422,"invalid_fields") from exc

@app.get("/extract/specs",response_class=HTMLResponse)
def show_specs():
    return studio.specs_page()

@app.post("/extract/workbook")
async def upload_workbook(request:Request):
    if request.headers.get("x-demo-local")!="1":
        raise HTTPException(403,"local_action_required")
    name=unquote(request.headers.get("x-demo-filename",""))
    data=bytearray()
    async for chunk in request.stream():
        if len(data)+len(chunk)>local_library.FILE_LIMIT:
            raise HTTPException(413,"file_over_5mb")
        data.extend(chunk)
    try:
        sheets=await run_in_threadpool(workbook_extract.parse,name,bytes(data))
    except (OSError,ValueError,KeyError,BadZipFile,SyntaxError,TypeError) as exc:
        raise HTTPException(422,"invalid_workbook") from exc
    sid=await run_in_threadpool(local_table.put,request.cookies.get(workbook_extract.COOKIE),name,sheets)
    response=JSONResponse({"status":"ready","sheets":list(sheets)})
    response.set_cookie(workbook_extract.COOKIE,sid,max_age=local_table.TTL,httponly=True,samesite="strict",secure=cloud_sessions.request_mode.get())
    return response

@app.get("/extract/workbook",response_class=HTMLResponse)
def show_workbook(request:Request,sheet:str|None=Query(default=None,max_length=64),
                  field:list[str]=Query(default=[]),download:bool=False):
    name,sheets=local_table.get(request.cookies.get(workbook_extract.COOKIE))
    selected=sheet if sheet is not None else next(iter(sheets or {}),"")
    result=None
    if field:
        if not sheets or selected not in sheets or len(field)>100:
            raise HTTPException(422,"select_sheet_and_columns")
        try:result=workbook_extract.project(name,sheets,selected,field)
        except ValueError as exc:raise HTTPException(422,"select_sheet_and_columns") from exc
    if download:
        if result is None:raise HTTPException(422,"select_sheet_and_columns")
        return JSONResponse(result,headers={"Cache-Control":"no-store",
                           "Content-Disposition":'attachment; filename="workbook-columns.json"'})
    if sheets and selected not in sheets:
        raise HTTPException(422,"select_sheet_and_columns")
    return HTMLResponse(studio.workbook_page(name,sheets or {},selected,field,result),headers={"Cache-Control":"no-store"})

def workspace_query(request,q,source,sheet,model="bm25",*,embedding_ready=None):
    if cloud_sessions.request_mode.get():embedding_ready=False
    work_name,work=local_table.get(request.cookies.get(workbook_extract.COOKIE))
    tab_name,tab=latest_analysis_table(request)
    _,mfg=local_table.get(request.cookies.get(local_table.COOKIE))
    _,docs=local_library.snapshot(request.cookies.get(local_library.COOKIE))
    if source=="demo":
        work_name,work=None,None
    if q is not None and source=="demo":
        tab_name="finance.csv（示範）"
        tab=generic_analysis.read(demo_dir/"finance.csv")
    result=studio.query_tools(q,source,sheet,work_name,work,tab_name,tab,
                       mfg if source=="local" else default_table,docs,report,model=model,embedding_ready=embedding_ready) if q else None
    return work,result

@app.get("/agent",response_class=HTMLResponse)
def show_agent(request:Request,line: str|None=Query(default=None,pattern=r"^[\w.-]{1,64}$"),
               q:str|None=Query(default=None,min_length=1,max_length=250),
               source:Literal["demo","local"]|None=None,sheet:str|None=Query(default=None,max_length=64),
               model:Literal["bm25","character","qwen"]="bm25"):
    if q is None and line is not None:
        return studio.agent_page(line,default_table,report)
    source=source or "local"
    if q and source=="local" and calculation_plan.needs_plan(q):
        return RedirectResponse("/agent/calc?"+urlencode({"q":q}),status_code=303)
    embedding_ready=not cloud_sessions.request_mode.get() and local_models.available("embedding")
    work,result=workspace_query(request,q,source,sheet,model,embedding_ready=embedding_ready)
    return HTMLResponse(studio.agent_chat(q,source,work,sheet,result,model=model,embedding_ready=embedding_ready,chat_options=chat_options(request=request),selected_chat=selected_chat_model(),has_upload=any(request.cookies.get(k) for k in (local_library.COOKIE,generic_analysis.COOKIE,local_table.COOKIE,workbook_extract.COOKIE))),headers={"Cache-Control":"no-store"})

@app.get("/agent/calc",response_class=HTMLResponse)
def agent_calculation(request:Request,q:str=Query(default="",max_length=250),
                      planner:Literal["rules","qwen"]="rules",
                      formula:str=Query(default="",max_length=180),
                      group:str=Query(default="",max_length=250),unit:str=Query(default="",max_length=250),
                      sheet_pin:str=Query(default="",max_length=64),percent:bool=False,
                      run:bool=False,download:bool=False,format:Literal["json","html"]="json"):
    chat_ready=not cloud_sessions.request_mode.get() and local_models.available("chat")
    name,table=latest_analysis_table(request)
    aliases=calculation_plan.map_columns(table) if table else {}
    pin=calculation_plan.pin(table) if table else ""
    proposal,note,result={}, "",None
    try:
        if run:
            if not table or not sheet_pin or sheet_pin!=pin:
                raise ValueError("來源表格已變更或失效，請再確認一次算式。")
            proposal={"formula":formula,"group":group,"unit":unit,"percent":percent,"question":q}
            result=calculation_plan.compute(table,aliases,formula,group,unit,percent)
            result["source"]=name
            if download:
                if format=="html":
                    from decimal import Decimal
                    groups=[]
                    for row in result["results"][:50]:
                        value=row["ratio"]
                        shown="無法計算" if value is None else f"{Decimal(value):.2%}" if percent else value
                        groups.append(f'{row["group"]} {row["unit"]}：{shown}（{row["count"]} 筆） · '+
                                      "；".join(f"{name} = {val}" for name,val in row["aggregates"].items()))
                    view={"tool":"表格計算","status":"ok",
                          "answer":f'{len(result["results"])} 組；保留前 50 組供檢視，完整結果可下載 JSON。',
                          "evidence":[result["source"],calculation_plan.human_formula(formula,aliases),
                                      "排除無效數值 "+str(result["excluded"]["invalid_numeric"])+" 筆",*groups]}
                    return HTMLResponse(studio.standalone_report(q or formula,view,"local"),headers={"Cache-Control":"no-store",
                        "Content-Disposition":'attachment; filename="calculation-result.html"'})
                return JSONResponse(result,headers={"Cache-Control":"no-store","Content-Disposition":
                    'attachment; filename="calculation-result.json"'})
        elif download:
            raise ValueError("請先確認並計算。")
        elif q and table:
            proposal,note=calculation_plan.propose(q,table,aliases)
            if planner=="qwen" and not proposal and "篩選條件" not in note and "不唯一" not in note:
                try:
                    if not chat_ready:raise ValueError("local_model_unavailable")
                    group_fields=[k for k in table["fields"] if k not in aliases.values()]
                    unit_fields=[k for k in table["fields"] if k.casefold() in calculation_plan.UNIT_NAMES]
                    d=local_models.calculation_proposal(q,aliases,group_fields,unit_fields)
                    if not d["formula"]:
                        note="本機模型無法提出唯一算式，請手動指定。"
                    else:
                        calculation_plan.parse_formula(d["formula"],aliases)
                        if d["group"] and d["group"] not in group_fields or d["unit"] and d["unit"] not in unit_fields:
                            raise ValueError("invalid_group")
                        d["unit"]=d["unit"] or calculation_plan.unique_unit(table)
                        d["percent"]=any(term in q for term in ("百分比","占比","比率","成長率","變動率","毛利率","%"))
                        proposal=d
                        note="這是本機模型的草案，尚未計算。請核對有沒有漏掉題目條件。"
                except ValueError:
                    note="本機模型未能提供可驗證的算式。可以手動輸入；沒有執行模型回傳的內容。"
    except ValueError as e:
        if download:raise HTTPException(422,str(e)) from e
        note=str(e)
    return HTMLResponse(studio.calculation_page(q,name,table,aliases,proposal,note,pin,result,planner,chat_ready=chat_ready),
                        headers={"Cache-Control":"no-store"})

@app.get("/api/workspace/query")
def workspace_api(request:Request,q:str=Query(min_length=1,max_length=250),
                  source:Literal["demo","local"]="local",sheet:str|None=Query(default=None,max_length=64),
                  model:Literal["bm25","character","qwen"]="bm25",download:bool=False):
    _,result=workspace_query(request,q,source,sheet,model)
    headers={"Cache-Control":"no-store"}
    if download:
        headers["Content-Disposition"]='attachment; filename="workspace-result.json"'
    return JSONResponse(result,headers=headers)

@app.get("/api/workspace/report.html",response_class=HTMLResponse)
def workspace_report(request:Request,q:str=Query(min_length=1,max_length=250),
                     source:Literal["demo","local"]="local",sheet:str|None=Query(default=None,max_length=64),
                  model:Literal["bm25","character","qwen"]="bm25"):
    _,result=workspace_query(request,q,source,sheet,model)
    return HTMLResponse(studio.standalone_report(q,result,source),headers={
        "Cache-Control":"no-store","Content-Disposition": "attachment; filename=result.html; filename*=UTF-8''%E7%B5%90%E6%9E%9C.html"
    })

def api_result(request:Request,line:str,source:str):
    _,local=local_table.get(request.cookies.get(local_table.COOKIE))
    if source=="local" and local is None:return 404,{"status":"empty","detail":"沒有已上傳的表格"}
    r=report(local if source=="local" else default_table,line,0)
    r.get("data_quality",{}).pop("source",None)
    return (200,r) if r["status"]=="ok" else (404,{"status":"empty","detail":"找不到這條產線的有效資料"})

@app.get("/report.json")
def browser_report(request:Request,line: str=Query(default="L1",min_length=1,max_length=64),
                   source: Literal["demo","local"]="demo",download:bool=False):
    code,data=api_result(request,line,source)
    headers={"Cache-Control":"no-store"}
    if download and code==200:headers["Content-Disposition"]='attachment; filename="report.json"'
    return JSONResponse(data,status_code=code,headers=headers)

class ModelPrefs(BaseModel):
    model_config=ConfigDict(extra="forbid",str_max_length=410)
    embedding_url:str=""
    embedding_model:str=""
    chat_url:str=""
    chat_model:str=""

@app.post("/integration/settings")
def save_model_prefs(request: Request, body:ModelPrefs):
    if request.headers.get("x-demo-local")!="1":raise HTTPException(403,"local_action_required")
    try:model_settings.save(body.model_dump())
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    except OSError as exc:raise HTTPException(500,"settings_not_saved") from exc
    provider=local_models.provider_id(body.chat_url.strip())
    if provider:
        return {"status":"saved","provider_called":local_models.provider_configured(provider),
                "chat_models":local_models.provider_chat_models(provider)}
    return {"status":"saved","provider_called":False}

@app.get("/integration",response_class=HTMLResponse)
def show_integration(request:Request,line: str|None=Query(default=None,min_length=1,max_length=64),source: Literal["demo","local"]="demo"):
    prefs={} if cloud_sessions.request_mode.get() else model_settings.load()
    if line is None:
        _,work=local_table.get(request.cookies.get(workbook_extract.COOKIE))
        return HTMLResponse(studio.api_playground(prefs,work,has_upload=bool(uploaded_tables(request) or work or local_library.snapshot(request.cookies.get(local_library.COOKIE))[0] or local_table.get(request.cookies.get(local_table.COOKIE))[0])),headers={"Cache-Control":"no-store"})
    name,own=local_table.get(request.cookies.get(local_table.COOKIE))
    code,data=api_result(request,line,source)
    return HTMLResponse(studio.integration(line,source,name,code,data,prefs),headers={"Cache-Control":"no-store"})

@app.get("/guide",response_class=HTMLResponse)
def show_guide():
    return studio.guide()

TableExample = Literal["finance","operations","retail","inventory","survey","local"]
PRESETS={"finance":("金額","類別","日期","幣別"),"operations":("處理分鐘","部門","日期",""),
         "retail":("銷售額","通路","日期",""),"inventory":("增減量","倉庫","日期","單位"),
         "survey":("滿意度","問卷渠道","日期","")}

@app.post("/analysis/file")
async def upload_generic_table(request:Request):
    if request.headers.get("x-demo-local")!="1":raise HTTPException(403,"local_action_required")
    filename=unquote(request.headers.get("x-demo-filename",""))
    content=bytearray()
    async for chunk in request.stream():
        if len(content)+len(chunk)>local_library.FILE_LIMIT:raise HTTPException(413,"file_over_5mb")
        content.extend(chunk)
    try:
        data=await run_in_threadpool(generic_analysis.uploaded,filename,bytes(content))
    except (ValueError,OSError,BadZipFile,KeyError) as exc:
        code=str(exc)
        if code not in {"unsupported_table","empty_file","invalid_header","too_many_rows","excel_expands_too_large"}:code="invalid_table"
        raise HTTPException(422,code) from exc
    try: sid=await run_in_threadpool(local_table.add_table,request.cookies.get(generic_analysis.COOKIE),filename,data)
    except ValueError as exc:raise HTTPException(409,str(exc)) from exc
    response=JSONResponse({"status":"ready","valid_rows":len(data["rows"]),"columns":data["fields"]})
    response.set_cookie(generic_analysis.COOKIE,sid,max_age=local_table.TTL,httponly=True,samesite="strict",secure=cloud_sessions.request_mode.get())
    return response

@app.delete("/analysis/file")
def clear_generic_table(request:Request,name:str|None=Query(default=None,max_length=130)):
    if request.headers.get("x-demo-local")!="1":raise HTTPException(403,"local_action_required")
    sid=request.cookies.get(generic_analysis.COOKIE)
    if name is not None:
        if not local_table.remove_table(sid,name):raise HTTPException(404,"file_not_found")
        response=JSONResponse({"status":"removed"})
        if not local_table.tables(sid):response.delete_cookie(generic_analysis.COOKIE)
        return response
    local_table.clear(sid)
    r=JSONResponse({"status":"cleared"});r.delete_cookie(generic_analysis.COOKIE)
    return r

@app.get("/analysis",response_class=HTMLResponse)
def general_analysis(request:Request,sample:TableExample="local",
                     value:str|None=Query(default=None,max_length=250),group:str=Query(default="",max_length=250),
                     day:str=Query(default="",max_length=250),unit:str=Query(default="",max_length=250),
                     metric:Literal["sum","average","count","minimum","maximum","ratio","custom"]|None=None,
                     denominator:str=Query(default="",max_length=250),download:bool=False,reset:bool=False,
                     formula:str=Query(default="",max_length=180),percent:bool=False,
                     drop_dupes:bool=False,drop_outliers:bool=False,
                     file:list[str]=Query(default=[])):
    items=uploaded_tables(request)
    active=list(dict.fromkeys(file)) if file and sample=="local" else (
        [next(reversed(items))] if sample=="local" and items else [])
    filename=None
    source_error=None
    if sample=="local":
        table=None
        if active and (len(file)>8 or any(n not in items for n in active)):
            source_error="找不到所選表格，可能已移除或到期。請重新選擇。"
        elif active:
            chosen=[items[n] for n in active]
            fields=chosen[0]["fields"]
            if any(set(it["fields"])!=set(fields) for it in chosen):
                source_error="這些表格的欄名不一致，未合併。請改選同欄位的報表，或分開分析。"
            else:
                filename="、".join(active)
                table={"fields":fields,"rows":[r for it in chosen for r in it["rows"]],
                       "excluded":sum(it["excluded"] for it in chosen)}
    else:
        table=generic_analysis.read(demo_dir/(sample+".csv"))
    if table is None:
        if download:raise HTTPException(422,"select_table_first")
        return HTMLResponse(studio.universal_analysis(sample,filename,[],{},None,source_error or "empty_table","", files=tuple(items), active_files=active, source_error=source_error),headers={"Cache-Control":"no-store"})
    if reset:
        value=metric=None
        group=day=unit=denominator=formula=""
        percent=drop_dupes=drop_outliers=False
    elif value is None and metric!="custom" and sample in PRESETS:
        value,group,day,unit=PRESETS[sample]
    if value and metric is None:metric="sum"
    numeric=generic_analysis.numeric_fields(table)
    selected={"value":value or "","group":group,"day":day,"unit":unit,"metric":metric or "",
              "denominator":denominator,"formula":formula,"percent":percent,
              "drop_dupes":drop_dupes,"drop_outliers":drop_outliers}
    error=None
    quality=result=None
    try:
        table_used,quality=table_quality.profile(table,value or "",day,unit,deduplicate=drop_dupes,exclude_outliers=drop_outliers)
        if metric=="custom":
            if not formula.strip():raise ValueError("請先輸入自訂算式。")
            if day:raise ValueError("自訂計算不直接按月，請使用表內的月份欄分組。")
            result=calculation_plan.compute(table_used,calculation_plan.map_columns(table),formula.strip().upper(),group,unit,percent)
            result["metric"]="custom"
        elif value and metric=="ratio":
            result=generic_analysis.summarize_ratio(table_used,value,denominator,group,day,unit)
        elif value and metric not in (None,"custom"):
            result=generic_analysis.summarize(table_used,value,group,day,unit)
            result["metric"]=metric
        if result is not None:
            result["sources"]=active
            result["cleaning"]={k:quality[k] for k in ("removed","remaining","deduplicate","exclude_outliers","inspected_numeric")}
    except ValueError as exc:error=str(exc);result=None
    if download:
        if error or result is None:raise HTTPException(422,error or "select_columns_first")
        return JSONResponse(result,headers={"Cache-Control":"no-store","Content-Disposition":'attachment; filename="analysis.json"'})
    params=urlencode({"sample":sample,**{k:str(v).lower() if type(v) is bool else v for k,v in selected.items()},"download":"true","file":active},doseq=True)
    output=studio.universal_analysis(sample,filename,table["fields"],selected,result,error,"/analysis?"+params,
                                   numeric_columns=numeric,quality=quality,aliases=calculation_plan.map_columns(table),files=tuple(items),active_files=active)
    return HTMLResponse(output,headers={"Cache-Control":"no-store"})

class LocalModelPrefs(BaseModel):
    model_config=ConfigDict(extra="forbid")
    chat:Literal["off","qwen"]
    embedding:Literal["character","qwen"]

class LocalChatRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    question:str=Field(min_length=1,max_length=350)
    model:str|None=Field(default=None,max_length=110)

@app.get("/models",response_class=HTMLResponse)
def get_local_models(request:Request):
    status=model_status()
    prefs={"chat":"off","embedding":"character"} if cloud_sessions.request_mode.get() else model_settings.local_load()
    return HTMLResponse(studio.model_picker(prefs,status,chat_options(status["chat"],request=request),selected_chat_model()),headers={"Cache-Control":"no-store"})

@app.get("/models/status")
def get_model_status():
    return JSONResponse(model_status(),headers={"Cache-Control":"no-store"})

def model_status():
    return {kind:not cloud_sessions.request_mode.get() and local_models.available(kind) for kind in local_models.MODELS}

def selected_chat_model():
    if cloud_sessions.request_mode.get():return ""
    prefs=model_settings.load()
    hosted=prefs["chat_model"]
    provider=local_models.provider_id(prefs["chat_url"])
    if hosted and provider:
        return provider+":"+hosted
    return "local:qwen" if model_settings.local_load()["chat"]=="qwen" else ""


def chat_options(local_ready=None,*,request=None):
    cloud=cloud_sessions.request_mode.get()
    if cloud and not (request and getattr(request.state,"cloud_owner",False)):
        return []
    offline=[] if cloud else [{"id":"local:qwen","label":"Qwen2.5-Coder 1.5B（本機）",
                              "ready":local_models.available("chat") if local_ready is None else local_ready}]
    return offline+[
        {"id":provider+":"+model,"label":model+"（"+label+" · 已列出，尚未試跑）","ready":True}
        for provider,(_,label) in local_models.HOSTED_MODELS.items()
        for model in local_models.provider_chat_models(provider)]


@app.post("/models/settings")
def save_local_models(request:Request,body:LocalModelPrefs):
    if request.headers.get("x-demo-local")!="1":raise HTTPException(403,"local_action_required")
    prefs=body.model_dump()
    if any(prefs[kind]=="qwen" and not local_models.available(kind) for kind in prefs):
        raise HTTPException(503,"local_model_unavailable")
    model_settings.local_save(prefs)
    return {"status":"saved"}

@app.post("/models/chat")
def try_chat(request:Request,body:LocalChatRequest):
    if request.headers.get("x-demo-local")!="1":raise HTTPException(403,"local_action_required")
    if not body.question.strip():raise HTTPException(422,"question_required")
    requested=body.model
    if cloud_sessions.request_mode.get():
        if not getattr(request.state,"cloud_owner",False):raise HTTPException(401,"cloud_owner_login_required")
        if requested is None or requested=="local:qwen":raise HTTPException(503,"cloud_local_model_unavailable")
    if requested is None and model_settings.local_load()["chat"]!="qwen":
        raise HTTPException(409,"chat_model_not_selected")
    try:
        if requested is None or requested=="local:qwen":
            if not local_models.available("chat"):raise ValueError("local_model_unavailable")
            answer=local_models.chat(body.question)
            label="Qwen2.5-Coder 1.5B"
        elif ":" in requested:
            provider,model=requested.split(":",1)
            if provider not in local_models.HOSTED_MODELS:raise ValueError("unknown_chat_model")
            answer,actual_model=local_models.provider_chat(model,body.question,provider=provider)
            label=actual_model+"（"+local_models.HOSTED_MODELS[provider][1]+"）"
        else:
            raise ValueError("unknown_chat_model")
    except ValueError as exc:raise HTTPException(503,"local_model_unavailable") from exc
    return {"model":label,"answer":answer,"citations":[]}
