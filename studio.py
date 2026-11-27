"""The exam practice studio. All sources are deliberately synthetic."""
from collections import Counter
from decimal import Decimal
from html import escape
from math import hypot, log
from pathlib import Path
from urllib.parse import urlencode
import json
import re

import agent_api
import extract
import retrieval
import spec_extract
import exam_cases
import local_models
import figma_theme

DEMO=Path(__file__).resolve().parent/"demo"
TRACKS=(("/workspace","00","工作台總覽"),("/knowledge","01","文件問答"), ("/","02","製造數據"),
        ("/analysis","03","通用表格分析"), ("/agent","04","Agent 工具"), ("/extract","05","欄位擷取"),
        ("/models","06","本地模型"), ("/integration","07","API 與交付"), ("/guide","08","跟著做"))
FORMATS={
    "/":("CSV","TSV","Excel .xlsx","JSON 表列","JSONL"),
    "/knowledge":("PDF 文字層","Word .docx","TXT","Markdown","HTML"),
    "/extract":("文件：PDF、Word .docx、TXT、Markdown、HTML","表格：Excel .xlsx"),
    "/agent":("文件與表格","可下載 HTML／JSON"),
    "/integration":("JSON","OpenAPI 規格"),
    "/guide":("操作指南","示範案例"),
    "/analysis":("CSV","Excel .xlsx","TSV","JSON／JSONL"),
    "/models":("聊天模型","向量模型"),
}
PROCESS_FLOW={
    "/workspace":("文件切段查原文；表格讀欄位、選條件再算。",
        "文件：PDF（須有文字層）、Word .docx、TXT、Markdown、HTML。表格：CSV、TSV、Excel .xlsx、平面 JSON／JSONL。不是所有格式都支援；掃描 PDF 需要先做 OCR，巢狀 JSON 需要先整理成平面表。"),
    "/knowledge":("讀文字 → 分段並記下來源 → 搜尋 → 顯示原文。",
        "上傳時暫存文字片段與位置（PDF 保留頁碼）；查詢時才按所選模式排名：關鍵字檢索（BM25 排名）比對詞彙；向量檢索比較相似度；混合檢索合併兩種排名。不需要先存成 JSON，也不建立永久索引。"),
    "/":("讀表格 → 檢查欄位和數字 → 查產線 → 計算。",
        "需要產線及不良率，或產線、產量和不良數。可核對有效列、分子分母與排除原因；不做文件索引。Excel 預設讀作用中的工作表。"),
    "/analysis":("讀表格 → 選欄位和公式 → 算出結果。",
        "Excel 是表格格式之一，預設讀作用中的工作表。支援分組，必要時按幣別或單位分開。表格讀成欄與列，不做文件索引；需要交付時才匯出 JSON。"),
    "/extract":("選資料 → 選欄位 → 核對原文或儲存格。",
        "文件按明示的欄名找值，保留頁碼或行號；Excel 可選工作表與欄位，保留儲存格。空白不補值。此頁不建立全文索引，結果可以 JSON 查看或匯出。"),
    "/agent":("輸入問題 → 選工具 → 列出結果與依據。",
        "問文件就找原文，問數字就按表格計算，問欄位就擷取。所選模型只影響文件搜尋；表格運算與欄位擷取由程式執行。結果可查看或下載 JSON，也可下載離線 HTML。"),
    "/integration":("送出查詢 → 執行同一套工具 → 查看或下載 JSON。",
        "這裡用本機資料驗證查詢和回傳格式。下方外部模型 API 設定與本機試跑分開，儲存設定不會連外。"),
    "/models":("選模型 → 儲存設定 → 試跑確認。",
        "文件搜尋可用關鍵字檢索（BM25 排名）、字元向量（TF-IDF）或本機語意向量（Qwen3 Embedding）。BM25 與字元向量不呼叫模型。試聊與文件問答分開，不會自動讀取你上傳的文件。"),
    "/guide":("先選功能 → 跑一次 → 核對來源與結果。",
        "可用內建示範練習，也能上傳支援的檔案。兩種來源分開，不混用。"),
}

def process_flow(path):
    steps,detail=PROCESS_FLOW[path]
    return f'<details class="process-flow"><summary><span>資料怎麼處理</span><b>{escape(steps)}</b></summary><p>{escape(detail)}</p></details>'

CSS="""
:root{color-scheme:light;--ink:#172843;--muted:#536480;--line:#dde6f0;--blue:#176b5a;--panel:#fff}
*{box-sizing:border-box}body{margin:0;background:#f4f7fc;color:var(--ink);font:16px/1.6 system-ui,sans-serif}
a{color:var(--blue)}.shell{display:grid;grid-template-columns:238px minmax(0,1fr);min-height:100vh}
.side{padding:2rem 1.15rem;background:#102d26;color:white;display:flex;flex-direction:column;gap:.5rem}
.side strong{font-size:1.25rem}.side p{margin:0 0 1rem;color:#bacbea}.side a{padding:.65rem .85rem;border-radius:10px;color:#dbe6ff;text-decoration:none}
.side a[aria-current=page]{background:#245648;color:#fff;font-weight:700}.side a span{margin-right:.65em;color:#b3c8ff}
main{width:min(100%,1170px);margin:auto;padding:2.25rem clamp(1rem,4vw,3rem);align-self:start}
.hero{background:linear-gradient(120deg,#143c32,#22695b);color:#fff;border-radius:22px;padding:1.65rem 2rem;box-shadow:0 12px 40px #1b376220}
.hero p{margin:.25rem 0;color:#ecf3ff}.eyebrow{font-size:.8rem;font-weight:700;letter-spacing:.12em}
h1{font-size:clamp(1.55rem,4vw,2.45rem);line-height:1.1;margin:.6rem 0}h2,h3{line-height:1.3}
form{display:flex;flex-wrap:wrap;gap:.65rem;align-items:center;padding:1.05rem 0}input,button,select{font:inherit;padding:.55rem .7rem;border-radius:9px;border:1px solid #9eafcb}input{flex:1;min-width:14rem}
button{background:#176b5a;color:white;font-weight:700;cursor:pointer}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid #62a9ff;outline-offset:3px}
.library-board{margin-top:1rem;border:1px solid #d5e2f6;border-radius:18px;padding:1.25rem;background:#fff;box-shadow:0 7px 18px #162c500d}
.library-board h2{margin:.28em 0}.source-switch{display:flex;gap:.45rem;margin:.5rem 0 .85rem;flex-wrap:wrap}
.source-switch a{padding:.4rem .75rem;border:1px solid var(--line);border-radius:9px;text-decoration:none;font-weight:650}
.source-switch .active{color:#fff;background:#176b5a;border-color:#176b5a}
.drop-zone{background:#f6f9ff;padding:.65rem 1rem;border:1px dashed #88a3df;border-radius:12px}
.drop-zone form{padding:.5rem 0}.drop-zone input{max-width:100%;min-width:0}.drop-zone label{font-weight:700}.drop-active{background:#e1eeff}
.library-list{list-style:none;margin:.7rem 0;padding:0}.library-list li{display:flex;align-items:center;gap:.6rem;padding:.45rem 0;border-top:1px solid var(--line);overflow-wrap:anywhere}
.library-list li button{margin-left:auto}.secondary{background:#f7f9fd;color:#344974;font-size:.84rem}
.stepbar{display:flex;gap:.65rem;flex-wrap:wrap;color:#345075;margin:1rem 0}
.stepbar span{border:1px solid var(--line);background:#fff;padding:.35rem .62rem;border-radius:7px}
.search-board{border:1px solid #d5e2f6;border-radius:17px;padding:0 1.15rem .8rem;background:#fff;box-shadow:0 7px 17px #162c500c;margin:1rem 0}
.search-board fieldset{display:flex;align-items:center;gap:.45rem;flex-wrap:wrap;border:0;padding:0;margin:0;min-width:0}
.search-board legend{float:left;margin-right:.5rem;font-size:.9rem;font-weight:650;color:var(--muted)}
.mode{cursor:pointer;display:flex;align-items:center;gap:.3rem;padding:.4rem .65rem;background:#f5f8fd;border:1px solid #d5e0f3;border-radius:8px}
.mode:has(input:checked){background:#e6efff;border-color:#5b82e0;color:#16377e;font-weight:700}
.mode input{min-width:0;flex:none;accent-color:#2449bd}.search-input{display:flex;align-items:center;gap:.55rem;width:100%}
.search-input input{min-width:0}.readout{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(0,1fr);gap:1rem;margin-top:1rem;align-items:start}
.result-note{font-size:.92rem;color:#465c79}.source-ref{margin:0 0 .6rem;overflow-wrap:anywhere}.source-ref h3{margin:.4rem 0;font-size:1rem}
.cite{border-radius:5px;padding:.15rem .38rem;background:#eaf3ff;color:#154084;font-weight:700;font-size:.78rem}
.guide-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:1rem;margin-top:1rem}
.guide-grid article{border-top:3px solid #4e70d4}.guide-grid h2{font-size:1.13rem}
@media(max-width:830px){.readout{grid-template-columns:1fr}}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:.85rem}.cards strong{display:block;font-size:1.75rem;color:var(--blue)}
article,details,.empty,.answer{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:1rem}.answer{border-left:4px solid var(--blue);margin:.65rem 0}
blockquote{margin:.55em 0;color:#273c62;overflow-wrap:anywhere}details{margin:.8rem 0}summary{cursor:pointer;font-weight:700}.tag{display:inline-block;padding:.22rem .6rem;background:#ecf1ff;color:#203b82;border-radius:999px;font-size:.83rem;font-weight:650}
 .formats{display:flex;gap:.4rem;flex-wrap:wrap;align-items:center;padding:.8rem 0 0}.formats small{margin-right:.3rem}small,.muted{color:var(--muted)}.side small{color:#b7c6e7}.hero small{color:#edf5ff}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#edf2fa;padding:.75rem;border-radius:8px}
table{width:100%;border-collapse:collapse;text-align:left}th,td{padding:.48rem;border-bottom:1px solid var(--line);overflow-wrap:anywhere}
.samples{display:flex;gap:.65rem;flex-wrap:wrap;margin:0 0 1rem}.samples a{text-decoration:none;border:1px solid var(--line);background:white;border-radius:999px;padding:.3rem .7rem}
@media(max-width:730px){.shell{grid-template-columns:1fr}.side{padding:.8rem;flex-flow:row wrap;align-items:center}.side strong,.side p{width:100%}.side a{padding:.4rem}.side a span,.side small{display:none}main{padding:1rem}.hero{padding:1rem 1.15rem}}
"""

CLEAR_UPLOADS_SCRIPT = """<script>
document.addEventListener('click', async event => {
 const row=event.target.closest('[data-delete-table]');
 if(row){
   const name=row.dataset.deleteTable;
   if(!window.confirm('確定移除「'+name+'」？原始檔不會被刪除。'))return;
   row.disabled=true;
   try{
      const response=await fetch('/analysis/file?name='+encodeURIComponent(name),{method:'DELETE',headers:{'X-Demo-Local':'1'}});
      if(!response.ok)throw Error();
      location.assign(location.pathname);
   }catch{row.disabled=false;row.nextElementSibling.textContent='未能移除，請再試一次。';}
   return;
 }
 const button=event.target.closest('[data-clear-uploads]');
 if(!button || !window.confirm('確定清除'+button.dataset.clearLabel+'？只清本機暫存，原始檔不會被刪除。'))return;
 button.disabled=true;
 try{
   const target=button.dataset.clearUploads==='analysis'?'/analysis/file':'/workspace/uploads?scope='+encodeURIComponent(button.dataset.clearUploads);
   const response=await fetch(target,{method:'DELETE',headers:{'X-Demo-Local':'1'}});
   if(!response.ok)throw Error();
   location.assign(location.pathname);
 }catch{
   button.disabled=false;
   button.nextElementSibling.textContent='未能清除，請再試一次。';
 }
});
</script>"""

def clear_uploads_button(scope):
    labels={"workspace":"總覽的暫存文件和一般分析表格","extract":"欄位擷取的暫存文件和 Excel",
            "workbook":"暫存 Excel","agent":"Agent 共用的暫存文件、分析表格、製造表格和 Excel","analysis":"全部通用分析表格"}
    return f'<p><button type="button" class="secondary" data-clear-uploads="{scope}" data-clear-label="{labels[scope]}">清除已上傳檔案</button><span role="status"></span></p>'

def layout(path,title,desc,body):
    formats="".join(f'<span class="tag">{escape(v)}</span>' for v in FORMATS.get(path,()))
    format_row=f'<div class="formats" aria-label="支援格式"><small>支援格式</small>{formats}</div>' if formats else ""
    nav=figma_theme.navigation(TRACKS,path)
    section=next((label for url,_,label in TRACKS if url==path),"工作台")
    return f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}｜文件工作台</title><style>{CSS}{figma_theme.CSS}</style></head><body><div class="shell" data-ui="figma-make">
<nav class="side" aria-label="展示模組">
<a class="brand" href="/workspace" aria-label="回到工作台總覽">{figma_theme.MARK}<div><strong>文件工作台</strong><small>KNOWLEDGE OPS</small></div></a>
<span class="nav-caption">工作區</span>{nav}
<div class="sidebar-note"><span class="environment-dot"></span><div><strong>Mac 本機展示</strong><small>可切換內建練習與上傳資料</small></div></div></nav>
<div class="main-wrap"><header class="topbar"><span><i class="environment-dot"></i>本機展示環境</span><a href="/guide">使用說明</a></header>
<main><header class="hero"><div class="eyebrow">{escape(section)}</div><h1>{escape(title)}</h1><p>{escape(desc)}</p></header>
{figma_theme.rail(path)}{format_row}{process_flow(path)}{body}</main></div></div>{CLEAR_UPLOADS_SCRIPT}</body></html>"""

def workspace(docs=(),table_names=()):
    icon=figma_theme.icon
    loaded=[(d["name"],f'{d["chunks"]} 個片段') for d in docs]
    loaded.extend((name,"已載入表格") for name in table_names)
    ready=f"已就緒 · {len(loaded)} 份" if loaded else "尚未上傳"
    rows=''.join(f'<li>{icon("file")}<b>{escape(n)}</b><small>{escape(status)}</small></li>' for n,status in loaded)
    listed=(f'<ul class="workspace-list">{rows}</ul>'+clear_uploads_button("workspace")) if rows else ""
    body=f"""<div class="work-grid">
    <section class="work-card"><div class="workspace-caption"><div><span class="section-index">01 · 準備資料</span><h2>先準備查詢資料</h2></div><span class="tag"><span class="workspace-readiness">{ready}</span></span></div>
      <p>用內建練習先跑一遍，或直接上傳自己的文件與表格。</p>
      <div id="workspace-upload-list">{listed}</div><div class="work-drop"><div><span class="work-icon" style="margin:auto">{icon('upload',23)}</span>
        {direct_file_picker("workspace",".pdf,.docx,.txt,.md,.html,.htm,.csv,.tsv,.xlsx,.json,.jsonl,.ndjson",multiple=True)}</div></div>
    </section>
    <section class="work-card work-next"><span class="section-index">02 · 開始查詢</span>
      <span class="work-icon">{icon('search',22)}</span><h2>接著，開始查詢</h2>
      <p>查文件時核對原文；分析表格時核對欄位、數值與排除原因。</p>
      <div class="work-actions"><a class="work-button primary" href="/knowledge?source=local">查文件內容</a><a class="work-button" href="/analysis">分析表格</a></div>
      <p><a href="/knowledge?source=demo">使用內建文件示範</a> · <a href="/?sample=csv">使用製造範例</a></p>
    </section>
    <section class="work-card work-more"><span class="section-index">03 · 最後核對</span><h2>從結果走到交付</h2>
      <div class="work-links"><a href="/extract">{icon('file')}查看結構化欄位</a><a href="/agent">{icon('spark')}看 Agent 怎麼算</a><a href="/models">{icon('model')}設定本地模型</a><a href="/integration">{icon('code')}測試 API 與下載</a></div>
    </section></div>"""
    return layout("/workspace","從文件與數據，找到可核對的答案","準備資料、執行查詢、核對來源。練習資料與你上傳的內容分開。",body+DIRECT_UPLOAD_SCRIPT)

def fold(title, body):
    return f"<details><summary>{escape(title)}</summary>{body}</details>"

def components(items, limits="使用合成資料；不傳送外部 API。"):
    return fold("使用的工具與限制", "<ul>"+"".join(f"<li>{escape(t)}</li>" for t in items)+f"</ul><p>{escape(limits)}</p>")

def payload(title,value):
    return fold(title,f"<pre>{escape(json.dumps(value,ensure_ascii=False,indent=2))}</pre>")

def form(path,name,label,value):
    return f'<form action="{path}"><label for="query">{label}</label><input id="query" name="{name}" value="{escape(value,quote=True)}" required maxlength="250"><button>執行</button></form>'

def samples(path,name,items):
    return '<div class="samples">'+"".join(f'<a href="{path}?{urlencode({name:v})}">{escape(label)}</a>' for label,v in items)+"</div>"

def local_hybrid(question,chunks,mode):
    # Local sparse character vectors. A separate count-vector ranking is
    # fused with BM25. Exact device IDs must all exist in a matching chunk.
    def vec(t):
        s=" ".join(retrieval.tokens(t))
        return Counter(s[i:i+2] for i in range(max(0,len(s)-1)) if s[i:i+2].strip())
    def normalize(v,idf):
        v={k:(1+log(n))*idf.get(k,1.) for k,n in v.items()}
        d=hypot(*v.values())
        return {k:x/d for k,x in v.items()} if d else {}
    q=set(retrieval.tokens(question))
    ids={x for x in q if re.search(r"[a-z]",x) and re.search(r"[0-9]",x)}
    eligible=[x for x in chunks if ids.issubset(set(retrieval.tokens(x["text"])))]
    lexical=retrieval.retrieve(eligible,question,k=min(10,len(eligible))) if eligible and mode!="vector" else []
    if mode=="bm25":return [{**x,"channels":["BM25"]} for x in lexical[:3]]
    lexical_ids=[x["chunk_id"] for x in lexical]
    vectors={x["chunk_id"]:vec(x["text"]) for x in eligible}
    df=Counter(k for v in vectors.values() for k in v)
    idf={k:1+log((1+len(eligible))/(1+n)) for k,n in df.items()}
    qv=normalize(vec(question),idf)
    scored=[]
    for x in eligible:
        cid=x["chunk_id"]; doc=normalize(vectors[cid],idf)
        cos=sum(val*doc.get(k,0.) for k,val in qv.items())
        # Short queries with weak incidental overlap don't become answers.
        if cos>=.12:
            scored.append((cid,cos))
    vector_ids=[cid for cid,_ in sorted(scored,key=lambda a:(-a[1],a[0]))]
    totals=Counter()
    for ranking in (lexical_ids,vector_ids):
        for n,cid in enumerate(ranking,1): totals[cid]+=1/(60+n)
    src={x["chunk_id"]:x for x in eligible}
    out=[]
    chosen=vector_ids if mode=="vector" else sorted(totals,key=lambda k:(-totals[k],k))
    for cid in chosen[:3]:
        x=src[cid]
        quote=max(x["text"].splitlines(),key=lambda line:len(q.intersection(retrieval.tokens(line))))
        out.append({**{k:v for k,v in x.items() if k!="text"},"quote":quote,
                    "channels":[name for name,r in (("BM25",lexical_ids),("本機字元向量",vector_ids)) if cid in r]})
    return out

UPLOAD_SCRIPT = """
<script>
const form=document.querySelector('#local-upload'),files=document.querySelector('#doc-files'),zone=document.querySelector('#drop-zone'),out=document.querySelector('#upload-status');
const msg={unsupported_file:'不支援這個檔案類型或檔名。',empty_or_too_large:'檔案是空的或超過上限。',file_over_5mb:'單檔不能超過 5 MB。',duplicate_name:'此檔名已在清單，請先移除舊檔。',library_full:'已到文件或片段上限。',file_could_not_be_parsed:'讀取失敗，請檢查檔案完整性。',ocr_required:'有頁面沒有可靠文字層；本檔未加入查詢。請核對原頁，必要時做 OCR 再上傳。'};
async function send(items){
  if(!items.length)return;
  const button=form.querySelector('button');
  if(button.disabled)return;
  button.disabled=true;
  let ok=0,fail=[];
  try{
    for(const f of items){
      out.textContent='處理中：'+f.name;
      try{
        const r=await fetch('/knowledge/files',{method:'POST',headers:{'X-Demo-Local':'1','X-Demo-Filename':encodeURIComponent(f.name),'Content-Type':'application/octet-stream'},body:f});
        const result=await r.json();
        if(r.ok){ok++;}else{fail.push(f.name+'：'+(result.review_pages?.length?'第 '+result.review_pages.join('、')+' 頁需核對。':'')+(msg[result.detail]||'未能讀取文件。'));}
      }catch{fail.push(f.name+'：目前連不到本機。');}
    }
    if(ok){
      sessionStorage.setItem('doc-upload-message', '已索引 '+ok+' 份。'+fail.join('；'));
      const u=new URL(location.href);u.searchParams.set('source','local');u.searchParams.delete('q');location.assign(u);
    }else{out.textContent=fail.join('；');}
  }finally{button.disabled=false;files.value='';}
}
form.addEventListener('submit',e=>{e.preventDefault();send(Array.from(files.files));});
zone.addEventListener('dragover',e=>{e.preventDefault();zone.classList.add('drop-active');});
zone.addEventListener('dragleave',()=>zone.classList.remove('drop-active'));
zone.addEventListener('drop',e=>{e.preventDefault();zone.classList.remove('drop-active');send(Array.from(e.dataTransfer.files));});
document.querySelectorAll('[data-delete-doc]').forEach(b=>b.addEventListener('click',async()=>{
  const all=!b.dataset.deleteDoc;
  if(!window.confirm(all?'確定清除全部暫存文件？原始檔不會被刪除。':'確定移除此暫存文件？原始檔不會被刪除。'))return;
  b.disabled=true;
  try{
    const uri='/knowledge/files'+(all?'':'?name='+encodeURIComponent(b.dataset.deleteDoc));
    const r=await fetch(uri,{method:'DELETE',headers:{'X-Demo-Local':'1'}});
    if(!r.ok)throw Error();
    location.reload();
  }catch{out.textContent='未能移除，請重新整理再試。';b.disabled=false;}
}));
const saved=sessionStorage.getItem('doc-upload-message');
if(saved){out.textContent=saved;sessionStorage.removeItem('doc-upload-message');}
</script>"""

SEARCH_SCRIPT = """
<script>
const searchForm=document.querySelector('#knowledge-search');
let pendingSearch;
async function showResults(url){
 if(pendingSearch)pendingSearch.abort();
 const control=new AbortController();pendingSearch=control;
 const root=document.querySelector('#search-results');
 root.setAttribute('aria-busy','true');
 try{
   const response=await fetch(url.pathname+url.search,{signal:control.signal,cache:'no-store'});
   if(!response.ok)throw Error('query_failed');
   const doc=new DOMParser().parseFromString(await response.text(),'text/html');
   const next=doc.querySelector('#search-results');
   const nextSources=doc.querySelector('#document-sources');
   if(!next)throw Error('missing_results');
   if(control!==pendingSearch)return;
   const before=window.scrollY;root.replaceWith(next);
   if(nextSources)document.querySelector('#document-sources')?.replaceWith(nextSources);
   const nextTabs=doc.querySelector('.document-case-card');
   if(nextTabs)document.querySelector('.document-case-card')?.replaceWith(nextTabs);
   history.replaceState(null,'',url.pathname+url.search);
   if(window.scrollY!==before)window.scrollTo(0,before);
 }catch(e){
   if(e.name==='AbortError')return;
   const notice=document.createElement('p');notice.textContent='查詢沒有成功，請再試一次。';root.prepend(notice);
 }finally{root.removeAttribute('aria-busy');}
}
searchForm.addEventListener('submit',e=>{
 e.preventDefault();
 const url=new URL('/knowledge',location.origin);
 url.search=new URLSearchParams(new FormData(searchForm));
 showResults(url);
});
document.querySelectorAll('[data-knowledge-example]').forEach(link=>link.addEventListener('click',e=>{
 if(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;
 e.preventDefault();
 const url=new URL(link.href);
 url.searchParams.set('mode',new FormData(searchForm).get('mode'));
 searchForm.elements.q.value=url.searchParams.get('q');
 showResults(url);
}));
</script>"""

def library_panel(docs,source,mode):
    switch="".join(f'<a class="switch'+(' active' if key==source else '')+
                   f'" href="/knowledge?source={key}&amp;mode={mode}">{label}</a>'
                   for key,label in (("demo","內建練習"),("local","我的暫存文件")))
    rows="".join(f'<li><b>{escape(d["name"])}</b><small>{d["chunks"]} 個片段</small>'
                 f'<button type="button" class="secondary" data-delete-doc="{escape(d["name"],quote=True)}">移除</button></li>' for d in docs)
    listed=('<ul class="library-list">'+rows+'</ul>') if rows else '<p class="muted">這個瀏覽器還沒有上傳的文件。</p>'
    clear='<button type="button" class="secondary" data-delete-doc>清除全部已上傳文件</button>' if rows else ""
    return f"""
    <section class="library-board"><div><span class="tag">MAC 本機 · 不連外</span><h2>文件資料庫</h2>
    <p class="muted">可一次上傳多份。切到「我的暫存文件」時會一起搜尋，答案仍標出各自來源；內建練習不混入。</p>
    <div class="source-switch" aria-label="文件來源">{switch}</div></div>
    <div class="drop-zone" id="drop-zone"><form id="local-upload">
      <label for="doc-files">拖曳到這裡，或選擇文件</label>
      <input id="doc-files" type="file" multiple accept=".pdf,.docx,.txt,.md,.html,.htm" required>
      <button type="submit">上傳與建立索引</button></form>
      <small>PDF（文字層）、DOCX、TXT、Markdown、HTML。單檔最多 5 MB，最多 8 份，另有限制解析後文字量。</small></div>
    <p id="upload-status" role="status" aria-live="polite"></p>
    <h3>我的上傳文件 · {len(docs)} 份</h3>{listed}{clear}<details><summary>本機暫存說明</summary>
    <p class="muted">原檔解析後不保留。索引暫存在記憶體，清空、閒置到期或重啟會清除。</p></details></section>
    """

DOCUMENT_CASES=(
    ("answer","找到答案","✓","DEMO-100 E-402 告警後怎麼處理"),
    ("missing","文件沒寫","○","DEMO-100 保固幾年"),
    ("conflict","來源衝突","△","DEMO-100 交接時限"),
)

def document_case_card(source,question,mode):
    tabs=[]
    for key,label,mark,example in DOCUMENT_CASES:
        link="/knowledge?"+urlencode({"q":example,"mode":mode,"source":"demo"})
        current=' aria-current="true"' if source=="demo" and question==example else ''
        tabs.append(f'<a class="case-tab case-{key}" href="{link}"{current}><span aria-hidden="true">{mark}</span>{label}</a>')
    return '<nav class="document-case-card" aria-label="三種示範結果">'+''.join(tabs)+'</nav>'

def knowledge(question,mode,*,source="demo",docs=(),chunks=(),embedding_engine="character"):
    corpus=retrieval.load_docs(DEMO/"docs") if source=="demo" else chunks
    semantic=embedding_engine=="qwen" and mode!="bm25"
    model_error=None
    try:
        hits=(local_models.search(question,corpus,mode) if semantic else local_hybrid(question,corpus,mode)) if question else []
    except ValueError as exc:
        model_error=str(exc);hits=[]
    scenario=exam_cases.intent(question) if source=="demo" and not model_error else None
    outcome,hits=exam_cases.excerpts(scenario,hits,corpus) if scenario else ("answer" if hits else "missing",hits)
    labels={
        "hybrid":("混合搜尋","關鍵字檢索（BM25 排名）＋字元向量（TF-IDF），再用 RRF 合併名次。"),
        "bm25":("關鍵字搜尋（只用 BM25）","關鍵字檢索（BM25 排名）：比對詞彙並依相關性排序，不計算向量。"),
        "vector":(("語意搜尋" if semantic else "字元相似搜尋"),"字元向量（TF-IDF）：用相鄰兩字元為一組，比較餘弦相似度；不跑 BM25，也不呼叫語意模型。"),
    }
    radios="".join(f'<label class="mode"><input type="radio" name="mode" value="{key}"'+
                   (' checked' if key==mode else '')+f'>{title}</label>' for key,(title,_) in labels.items())
    source_label="內建示範文件" if source=="demo" else "我的上傳文件"
    body=f'<details class="upload-management"{" open" if source=="local" and not docs else ""}><summary>管理文件與上傳 · {source_label}</summary>'+library_panel(docs,source,mode)+'</details>'
    body+='<div class="document-layout"><section class="work-card query-card"><small class="section-index">02 · 再查詢</small><h2>查文件內容</h2>'
    body+='<p class="case-caption">查詢情境 · 內建示範</p>'+document_case_card(source,question,mode)
    body+=f'<section class="search-board"><form id="knowledge-search" action="/knowledge#search-results"><input type="hidden" name="source" value="{source}"><fieldset><legend>檢索模式</legend>{radios}</fieldset><div class="search-input"><label for="query">查詢</label><input id="query" name="q" required maxlength="250" placeholder="輸入料號、錯誤碼或想找的內容" value="{escape(question,quote=True)}"><button>查詢</button></div></form>'
    examples=[(title,q) for title,q in exam_cases.CASES if title not in {"文件沒寫","版本互相衝突","告警後怎麼辦"}]
    body+=('<div class="samples">'+"".join(f'<a data-knowledge-example href="/knowledge?{urlencode({"q":q,"mode":mode,"source":"demo"})}#search-results">{title}</a>' for title,q in examples)+'</div>' if source=="demo" else '<p class="muted">現在只查你上傳的文件。想看練習題，切回「內建練習」。</p>')+'</section>'
    mode_label={"hybrid":"混合檢索｜BM25 + 本機字元向量 + RRF","bm25":"關鍵字檢索｜BM25","vector":"向量檢索｜本機字元向量 + cosine"}[mode]
    if semantic:mode_label="混合檢索｜BM25 + Qwen3 Embedding + RRF" if mode=="hybrid" else "向量檢索｜Qwen3 Embedding"
    mode_desc=(("關鍵字檢索（BM25 排名）＋本機語意向量（Qwen3 Embedding），再用 RRF 合併名次。" if mode=="hybrid" else "本機語意向量（Qwen3 Embedding），不跑 BM25。")+"不呼叫外部服務。") if semantic else labels[mode][1]
    body+=f'<div id="search-results" aria-live="polite"><span class="tag">{mode_label}</span> <span class="tag">抽取原文 · 不生成</span><p class="result-note">{mode_desc} 設備編號在三種模式都要求完整對上。<a href="/models">切換本地模型</a></p>'
    title="本地向量模型目前無法完成查詢" if model_error else "來源衝突，暫不給單一答案" if outcome=="conflict" else ("找到可引用片段" if hits else ("請輸入問題" if not question else "查無可引用資料"))
    tone='warning' if model_error or outcome=='conflict' else 'neutral' if not hits else 'success'
    body+=f'<section class="answer {tone} work-card" role="status"><small class="section-index">查詢結果</small><h2>{title}</h2>'
    if model_error:
        body+='<p>確認本地模型已啟動；單次最多 32 個片段。你可以到「本地模型」換回字元向量，或改用純 BM25。沒有偷偷換模型。</p>'
    elif outcome=="conflict":
        body+='<p>兩份同日的紀錄寫法不一致，且都沒有主管覆核。請先確認正式版本，不能挑一個當答案。</p>'
    elif hits:
        body+=f'<blockquote><span class="cite">01</span> {escape(hits[0]["quote"])}</blockquote><p class="muted">摘錄第 1 個來源的原文，不是模型生成答案。</p>'
    elif question:
        body+='<p>試著核對設備編號，不會拿其他設備的內容替代。</p>'
    body+='</section></div></section><section class="work-card source-card" id="document-sources" aria-label="來源"><small class="section-index">03 · 最後核對</small><h2>原文與來源 <span class="tag">'+str(len(hits))+' 筆</span></h2>'
    for n,x in enumerate(hits,1):
        where=f'第 {x["page"]} 頁 · 文字第 {x["start_line"]}–{x["end_line"]} 行' if "page" in x else f'第 {x["start_line"]}–{x["end_line"]} 行'
        how=" / ".join(x.get("channels",[]))
        quote=f'<blockquote>{escape(x["quote"])}</blockquote>'
        body+=f'<details class="source-ref"><summary><span class="cite">{n:02d}</span>{escape(x["source"])}</summary><small>{escape(where)}</small>{quote}<span class="tag">{escape(how)}</span></details>'
    if not hits:body+='<p class="muted">沒有可顯示的來源。</p>'
    elif any("page" in x for x in hits):body+='<p class="result-note">PDF 文字層可能來自 OCR。重要數字、料號和單位請依頁碼核對原頁。</p>'
    body+=payload("展開檢索原始結果",hits)+"</section></div>"
    if scenario:body+='<p class="muted">內建示範案例與上傳資料獨立。上傳文件由所選模式檢索，不套用示範結果。</p>'
    return layout("/knowledge","文件問答","比較三種檢索模式，在同一個畫面核對原文與來源。",body+
                 components(["關鍵字檢索（BM25 排名）","字元向量（TF-IDF）：字元二元組＋餘弦相似度","RRF：只有混合模式才融合排名","pypdf：PDF 原文與頁碼"],
                            "本機字元向量不等於語意 Embedding。選「Qwen3 Embedding」才會用本地模型。本頁不連 RAGFlow 或外部 API。")+
                 UPLOAD_SCRIPT+SEARCH_SCRIPT)


FIELD_EXAMPLES={"text":"form.txt","pdf":"docs/PDF-200.pdf","docx":"docs/WORD-210.docx"}

def extraction_document(file,source,doc_name,doc):
    path=FIELD_EXAMPLES.get(file) if source=="demo" else None
    if path:return Path(path).name,extract.pages(DEMO/path)
    if source=="local" and doc and doc[0]==file:return doc_name,doc[1]
    return None,None

def structured_document(name,pages,fields):
    result={"source":name,**extract.extract(pages,[x.strip() for x in fields.split(",") if x.strip()])}
    if name.lower().endswith(".pdf"):
        result["review"]={"status":"original_not_verified",
                          "cited_pages":sorted({hit["page"] for hits in result["evidence"].values() for hit in hits})}
    return result

def fields_page(file, fields, *, source="local", doc_name=None, doc=None, book_name=None,
                sheets=None, selected=None, chosen=(), table_result=None):
    labels={"text":"TXT","pdf":"PDF","docx":"Word (.docx)","md":"Markdown","html":"HTML","xlsx":"Excel (.xlsx)"}
    opts=''.join(f'<option value="{kind}"{" selected" if kind==file else ""}>{name}</option>' for kind,name in labels.items())
    body=direct_file_picker("extract",".pdf,.docx,.txt,.md,.html,.htm,.xlsx",multiple=False)
    body+='<section id="extract-work-area" class="work-card">'
    body+=f'<form action="/extract"><input type="hidden" name="source" value="{source}"><label for="file">來源格式</label><select name="file" id="file" onchange="this.form.requestSubmit()">{opts}</select><button type="submit">切換</button></form>'
    body+='<div class="samples"><a href="/extract?file=pdf&amp;source=demo&amp;fields=Asset,Status,Owner">PDF 範例</a><a href="/extract/specs">多產品規格 PDF</a><a href="/extract?file=docx&amp;source=demo">Word 範例</a><a href="/extract?file=text&amp;source=demo">TXT 範例</a>'
    if doc_name and doc:
        body+=f'<a href="/extract?source=local&amp;file={doc[0]}">最近上傳的文件</a>'
    if book_name:
        body+='<a href="/extract?source=local&amp;file=xlsx">最近上傳的 Excel</a>'
    body+='</div>'
    if doc_name or book_name:body+=clear_uploads_button("extract")
    if file=="xlsx":
        body+=inline_excel_fields(book_name,sheets or {},selected,chosen,table_result)
    else:
        active_name,pages=extraction_document(file,source,doc_name,doc)
        if pages is not None:
            current=fields if fields is not None else ("設備,狀態,負責人" if source=="demo" else "")
            body+=f'<p class="data-source-note">{"內建範例" if source=="demo" else "已上傳"} · {escape(active_name)}</p><form action="/extract"><input type="hidden" name="file" value="{file}"><input type="hidden" name="source" value="{source}"><label for="fields">欄位</label><input id="fields" name="fields" value="{escape(current,quote=True)}" placeholder="例如：設備,狀態" required maxlength="250"><button>擷取</button></form>'
            if current:
                value=structured_document(active_name,pages,current)
                cards=[]
                for name,val in value["fields"].items():
                    ref=value["evidence"][name]
                    where="、".join((f'第 {x["page"]} 頁' if file=="pdf" else "")+f'第 {x["line"]} 行' for x in ref)
                    fallback="來源有衝突" if name in value["ambiguous"] else "文件未提供"
                    cards.append(f'<article><small>{escape(name)}</small><strong>{escape(val or fallback)}</strong><p>{escape(where or "不自行補值")}</p></article>')
                if file=="pdf":
                    body+='<p class="result-note">待核對原頁：料號、數字與單位請對照下面的頁碼。若 PDF 的文字層來自 OCR，辨識值不等於已確認。</p>'
                params=urlencode({"file":file,"source":source,"fields":current,"download":"true"})
                body+='<section class="cards" role="status">'+''.join(cards)+'</section>'
                body+=f'<p><a class="work-button" href="/extract?{escape(params,quote=True)}">下載結構化 JSON</a></p>'+payload("展開可交付 JSON",value)
        else:
            body+='<p class="empty">請使用上方「上傳檔案」選擇這種格式的檔案。</p>'
    return layout("/extract","欄位擷取","上傳檔案後，在同一頁選擇要擷取的欄位。",body+'</section>'+DIRECT_UPLOAD_SCRIPT)

def specs_page():
    result=spec_extract.parse(extract.pages(DEMO/"specs"/"products.pdf"))
    cards=[]
    for item in result.items:
        cards.append(f'<article><small>第 {item.evidence.page} 頁 · 第 {item.evidence.line} 行</small>'
                     f'<strong>{escape(item.part_number)}</strong><p>{escape(item.category or "未提供類別")} · '
                     f'{escape(item.voltage_or_power or "未提供額定值")}</p><p>{escape("、".join(item.compliance) or "未提供認證")}</p>'
                     f'<small>{escape(item.notes or "未提供備註")}</small></article>')
    body=f'<section class="answer" role="status"><h2>{escape(result.document_title or "多產品規格")}</h2><p>成功擷取 {len(result.items)} 筆；{len(result.unresolved)} 筆待人工核對。</p><a href="/extract">返回單欄位擷取</a></section>'
    body+='<section class="cards">'+''.join(cards)+'</section>'
    return layout("/extract","多產品規格擷取","從同一份文字型 PDF 讀取多個產品，保留出處和待核對列。",body+
                  payload("展開 Pydantic 驗證後的 JSON",result.model_dump())+
                  components(["pypdf：讀取原文","Pydantic：驗證多產品資料結構","本機規則：辨識編號、標籤與缺值"],
                             "此範例支援格式可讀且欄位明示的編號條列；掃描件、無標籤的自由文句與跨頁複雜表格仍須另作處理。"))

def agent_page(line,table,report):
    calls=[]
    def fake_chat(messages):
        if messages[-1]["role"]=="tool":
            calls.append({"stage":"tool_result","message":json.loads(messages[-1]["content"])})
            return {"content":"done"}
        calls.append({"stage":"tool_request","name":"production_report","arguments":{"line":line}})
        return {"tool_calls":[{"id":"demo-report-1","type":"function","function":{
            "name":"production_report","arguments":json.dumps({"line":line})}}]}
    result=agent_api.run(f"查 {line} 產線的不良率",table,report,chat=fake_chat)
    body='<div class="agent-layout"><section class="work-card"><span class="section-index">製造資料助理</span><h2>查一條產線的不良率</h2>'
    body+=form("/agent","line","產線",line)+samples("/agent","line",[("正常 L1","L1"),("查無資料 L9","L9")])
    body+=f'<p class="chat-question">查 {escape(line)} 產線的不良率</p>'
    body+=('<div class="plain-step"><span>1</span><div><small>你問什麼</small><p>查指定產線的不良率。</p></div></div>'
           '<div class="plain-step"><span>2</span><div><small>程式查了什麼</small><p>只讀這條產線的有效生產資料，排除無法計算的列。</p></div></div>'
           '<div class="plain-step"><span>3</span><div><small>算出什麼</small>')
    if result["status"]=="ok":
        metric=result["overall"]; rate=metric["weighted_defect_rate"]
        body+=f'<p role="status"><b>{f"{rate:.2%}" if rate is not None else "資料不足"}</b> · {metric["defect_count"]} 不良 ÷ {metric["output_qty"]} 產量 · 工具已執行 {result["tool_calls_verified"]} 次</p>'
    else:
        body+='<p role="status">工具已執行，查無有效資料；不回傳 0%。</p>'
    body+='</div></div></section><aside class="work-card"><span class="section-index">回答可核對</span><h2>計算與驗證</h2><p>加權不良率等於有效不良數除以有效產量。查無有效資料時不回傳 0%。</p><p>用模擬方式選工具，數字由程式現算。</p><a class="work-button" href="/">看數據和排除明細</a></aside></div>'
    body+=payload("工程細節：展開工具請求與原始回傳",calls)
    return layout("/agent","Agent 工具流程","展示選工具、驗證參數、計算與回傳，數字全由程式產生。",body+
                  components(["唯讀工具白名單","限制回合及工具呼叫","數字由 Python 計算"],"模型回應為固定模擬資料；實際執行了同一條工具流程，未呼叫任何模型。"))

def integration():
    return layout("/integration","API 與交付","示範檢驗程式是否可用，以及如何交付給其他系統。",'''
    <div class="cards" style="margin-top:1rem">
      <article><h3>API 交付</h3><p>同一計算引擎以 JSON 交付。</p><a href="/report.json?line=L1">L1 回傳</a> · <a href="/openapi.json">本機 OpenAPI 規格</a></article>
      <article><h3>服務健康</h3><p>本機就緒狀態與執行模式。</p><a href="/health">檢查 /health</a></article>
      <article><h3>輸出格式</h3><p>核對報表欄位、資料來源與 JSON 結構。</p></article>
    </div>'''+components(["FastAPI：路由與互動文件","Pydantic：驗證 JSON 輸入","Uvicorn：僅 Mac 本機提供 Web 服務","Python：運算、檢索、擷取和測試"]))

def guide():
    return layout("/guide","跟著做","依功能查看操作步驟、核對資料來源與下載結果。", """
    <div class="stepbar"><span>01 選功能</span><span>02 跑結果</span><span>03 展開可核對證據</span></div>
    <div class="guide-grid">
      <article id="documents"><small>約 60 秒</small><h2>文件問答｜比較三種模式</h2><ol>
       <li><a href="/knowledge?source=demo&amp;q=PDF-200+ALARM-931">打開 PDF 範例</a>：看原句和第 2 頁。</li>
       <li>改選「字元相似搜尋」或「語意搜尋」，按查詢；再改選「關鍵字搜尋」，同一題直接比較。不要求這個範例的排名一定不同。</li>
       <li>點「文件沒寫」，確認沒有拿別的設備當答案。</li><li>用「我的暫存文件」上傳允許測試的文件，查它的專用關鍵字。</li></ol></article>
      <article><small>約 45 秒</small><h2>製造數據｜核對分母和例外</h2><ol>
       <li><a href="/?line=L1&sample=xlsx">查 Excel 的 L1</a>，看 102 ÷ 3,000 得 3.40%。</li>
       <li>展開「資料品質」，指出被排除的是 L2 第 6 列。</li>
       <li>改查 L9，確認「查無有效資料」不是 0%。</li></ol></article>
      <article><small>約 45 秒</small><h2>欄位擷取｜保留缺漏</h2><ol>
       <li><a href="/extract/specs">打開多產品 PDF</a>，看兩筆成功、一筆待核。</li>
       <li>展開 JSON，看未提供的欄位保留 null。</li>
       <li><a href="/extract?file=docx">換 Word 範例</a>，看它能讀簡單表格。</li></ol></article>
      <article><small>約 30 秒</small><h2>Agent／API｜工具與回傳</h2><ol>
       <li><a href="/agent?line=L1">跑 Agent</a>，展開工具請求和結果。</li>
       <li>核對工具選擇為模擬，統計由 Python 計算。</li>
       <li>查看 <a href="/report.json?line=L1">報表 JSON</a>。</li></ol></article>
    </div>
    """)

def table_upload(filename,*,generic=False):
    listed=('<p>已載入：<b>'+escape(filename)+'</b> <button id="table-clear" type="button" class="secondary">清除已上傳表格</button></p>') if filename else ""
    panel='''<section class="library-board"><h2>先放入資料表</h2><p>不用轉成 CSV。上傳後選產線，下面就會顯示計算結果。</p>
    <form id="table-upload"><label for="table-file">檔案</label><input type="file" id="table-file" accept=".csv,.tsv,.xlsx,.json,.jsonl,.ndjson" required><button>上傳並分析</button></form>
    <small>文字 CSV／TSV、Excel、表列 JSON／JSONL，單檔 5 MB；只作本機暫存。</small>'''+listed+'''
    <p id="table-message" role="status"></p></section>
<script>
const upForm=document.querySelector('#table-upload'),tableMsg=document.querySelector('#table-message');
upForm.onsubmit=async e=>{
 e.preventDefault();const f=document.querySelector('#table-file').files[0],b=upForm.querySelector('button');
 if(!f)return;b.disabled=true;tableMsg.textContent='正在讀取表格…';
 const messages={file_over_5mb:'檔案超過 5 MB',need_line_and_output_plus_defects_or_rate:'找不到產線欄，或缺少產量加不良數／不良率欄',unsupported_table:'不支援這個格式',nested_json_requires_explicit_mapping:'巢狀 JSON 請先轉成平面表格'};
 try{const r=await fetch('/manufacturing/file',{method:'POST',headers:{'X-Demo-Local':'1','X-Demo-Filename':encodeURIComponent(f.name),'Content-Type':'application/octet-stream'},body:f});
 const j=await r.json();if(r.ok){location.assign('/?sample=local#table-results');return;}
 tableMsg.textContent=messages[j.detail]||'這個檔案讀不到。請確認欄名、檔案是否完整。';
 }catch{tableMsg.textContent='目前連不到本機。';}finally{b.disabled=false;}
};
const tc=document.querySelector('#table-clear');
if(tc)tc.onclick=async()=>{if(!window.confirm('確定清除這個分頁的暫存表格？原始檔不會被刪除。'))return;tc.disabled=true;try{const r=await fetch('/manufacturing/file',{method:'DELETE',headers:{'X-Demo-Local':'1'}});if(r.ok){location.assign('/');return;}}catch{}tableMsg.textContent='無法移除，請再試一次。';tc.disabled=false;};
</script>'''
    if generic:
        return panel.replace("/manufacturing/file","/analysis/file").replace("/?sample=local#table-results","/analysis?sample=local").replace("location.assign('/')","location.assign('/analysis')").replace("上傳後選產線，下面就會顯示計算結果。","上傳後，可自己選要算哪一欄、怎麼分組。")
    return panel

def analysis_table_library(files,active):
    rendered=''.join(f'<li><label><input type="checkbox" name="file" value="{escape(n,quote=True)}"{" checked" if n in active else ""}> {escape(n)}</label> '
                     f'<button type="button" class="secondary" data-delete-table="{escape(n,quote=True)}">移除</button><span role="status"></span></li>' for n in files)
    picker=(f'<h3>我的上傳表格 · {len(files)} 份</h3><form action="/analysis" id="choose-tables">'
            f'<input type="hidden" name="sample" value="local"><ul class="library-list">{rendered}</ul>'
            '<button>使用勾選的表格</button></form>'+clear_uploads_button("analysis")) if files else ""
    return (f'<section class="library-board"><h2>表格資料庫</h2><p>可上傳多份，再選一份切換或勾多份上下疊加。同欄名才合併，不會改原始檔。</p>'
            '<form id="table-bulk-upload"><label for="bulk-table-file">選擇表格</label><input id="bulk-table-file" type="file" '
            'accept=".csv,.tsv,.xlsx,.json,.jsonl,.ndjson" multiple required><button>上傳表格</button></form>'
            '<small>CSV、TSV、Excel、表列 JSON／JSONL；單檔 5 MB，最多 8 份且共 20,000 列。Excel 取活頁簿作用中的工作表。</small>'
            f'<p id="bulk-table-status" role="status"></p>{picker}</section>'+BULK_TABLE_SCRIPT)


BULK_TABLE_SCRIPT = """<script>
(() => {
 const form=document.querySelector('#table-bulk-upload'), status=document.querySelector('#bulk-table-status');
 const chooser=document.querySelector('#choose-tables');
 chooser?.addEventListener('submit',e=>{
   if(!chooser.querySelector('input[type=checkbox]:checked')){
      e.preventDefault();status.textContent='請至少勾選一份表格。';
   }
 });
 const previous=sessionStorage.getItem('analysis-upload-status');
 if(previous){status.textContent=previous;sessionStorage.removeItem('analysis-upload-status');}
 form.addEventListener('submit',async event=>{
   event.preventDefault();
   const button=form.querySelector('button'), selected=[...form.querySelector('input').files];
   if(!selected.length)return;
   const failures=[];let count=0;
   button.disabled=true;status.textContent='正在上傳…';
   const errors={duplicate_name:'已有同名檔案，沒有覆蓋',table_library_full:'已達份數或筆數上限',file_over_5mb:'超過 5 MB'};
   for(const file of selected){
     try{
       const response=await fetch('/analysis/file',{method:'POST',headers:{'X-Demo-Local':'1','X-Demo-Filename':encodeURIComponent(file.name),'Content-Type':'application/octet-stream'},body:file});
       const data=await response.json();
       if(response.ok)count++;
       else failures.push(file.name+'：'+(errors[data.detail]||'檔案無法讀取'));
     }catch{failures.push(file.name+'：無法連上本機');}
   }
   const report=[count?'已上傳 '+count+' 份。':'',...failures].filter(Boolean).join('；');
   if(count){sessionStorage.setItem('analysis-upload-status',report);location.assign('/analysis');}
   else{status.textContent=report;button.disabled=false;}
 });
})();
</script>"""


def quality_panel(a):
    if a is None:
        stats=("上傳後檢查各欄空白","比對整列內容是否重複","檢查數字、日期及極端值","識別混用幣別和單位")
        steps=("預覽來源欄位及前幾列。","空白不補零；先分開顯示錯誤和疑似異常。","明確勾選才排除重複，原資料不改。","核對有效筆數、排除及結果。")
        sample=""
    else:
        units="；".join(f"{k}：{'、'.join(v)}" for k,v in a["unit_values"].items() if v) or "未辨識出專用單位欄"
        stats=(f"{sum(a['missing'].values())} 格空白",
               f"{a['duplicate_rows']} 筆整列重複",
               f"{a['unusual']} 筆疑似異常 · {a['invalid_numeric']} 格數值格式錯誤",
               f'{("日期格式錯誤 "+str(a["invalid_dates"])+" 筆") if a["inspected_date"] else "日期未指定檢查"}；{units}')
        steps=(f"{a['rows']} 筆能讀取、{a['columns']} 欄；下方預覽最多前五筆。",
               f"空白不補零；數值檢查欄：{a['inspected_numeric'] or '未選'}。極端值按單位分開，以四分位距標示，只當作提示（每組至少 8 筆）。",
               "只在勾選時排除整列重複或疑似異常。匯入時已去除文字前後空白；不同單位不相加、不自行換算。",
               f"可讀列數 {a['rows']} → {a['remaining']}（排除 {a['removed']} 筆）；空白格數 {sum(a['missing'].values())} → {sum(a['missing'].values())-a['removed_missing_cells']}。另有 {a['malformed_rows']} 筆原本就無法讀取。每次重算會重新檢查，不是常駐監控。")
        sample=('<div style="overflow:auto"><table><thead><tr>'+''.join(f'<th>{escape(k)}</th>' for k in a["sample_columns"])+'</tr></thead><tbody>'
                +''.join('<tr>'+''.join(f'<td>{escape(str(v))}</td>' for v in r)+'</tr>' for r in a["sample_rows"])+'</tbody></table></div>') if a["sample_rows"] else ""
    titles=("缺失值","重複資料","異常值與錯誤資料","格式與單位不一致")
    cards=''.join(f'<article><h3>{title}</h3><p>{escape(stat)}</p></article>' for title,stat in zip(titles,stats))
    names=("檢視與探索","處理缺失與異常","去重與標準化","驗證與監控")
    missing="" if not a or not a["missing"] else '<p>有空白的欄位：'+escape("、".join(f"{k}（{n}）" for k,n in a["missing"].items()))+'</p>'
    actions=[]
    if a:
        if a["invalid_numeric"] or a["invalid_dates"]:actions.append("回原表核對格式錯誤，別用零代替。")
        if a["duplicate_rows"]:actions.append("確認重複不是不同事件，再勾選排除整列重複。")
        if a["unusual"]:actions.append("先核對疑似異常值；有效極端值可以保留。")
        if any(len(v)>1 for v in a["unit_values"].values()):actions.append("選擇單位欄分組，不直接加總。")
    suggestion='<p><strong>建議先做：</strong>'+escape(" ".join(actions))+'</p>' if actions else ""
    affected=""
    if a:
        affected="；".join(f"{label}：{', '.join(map(str,a[key]))}" for label,key in
                           (("重複","duplicate_preview"),("疑似異常","unusual_preview")) if a[key])
        affected=f'<p>可讀資料列序號（每項最多 10 筆，不含欄名）：{escape(affected)}</p>' if affected else ""
    details=''.join(f'<details><summary>{i+1} · {name}</summary><p>{escape(step)}</p>{sample if i==0 else missing+affected if i==1 else ""}</details>' for i,(name,step) in enumerate(zip(names,steps)))
    return '<section class="work-card quality-workflow" aria-labelledby="quality-heading"><span class="section-index">先看問題，再選處理</span><h2 id="quality-heading">資料品質總覽</h2><p>掃描不會改原表；資料可能重複或異常，不代表一定該刪。</p><div class="cards quality-cards">'+cards+'</div>'+suggestion+'<div class="quality-steps">'+details+'</div></section>'

def universal_analysis(sample,filename,fields,selection,result,error,download_url,*,numeric_columns=(),quality=None,aliases=None,files=(),active_files=(),source_error=None):
    from decimal import Decimal
    nav='<div class="samples"><a href="/analysis?sample=finance">金融：收支明細</a><a href="/analysis?sample=operations">營運：工單時效</a><a href="/analysis?sample=retail">零售：通路銷售</a><a href="/analysis?sample=inventory">庫存：異動</a><a href="/analysis?sample=survey">問卷：評分</a>'+('<a href="/analysis?sample=local">我的表格</a>' if filename else '')+'</div>'
    formulas={"sum":("加總","把有效數值加在一起"),
              "average":("平均","加總 ÷ 有效數值筆數"),
              "count":("有效筆數","只計入可計算的數值列"),
              "minimum":("最小值","最小的有效數值"),
              "maximum":("最大值","最大的有效數值")}
    if len(numeric_columns)>=2:
        formulas["ratio"]=("比率","分子合計 ÷ 分母合計")
    if numeric_columns:formulas["custom"]=("自訂計算","用欄位代號和四則運算組合算式")
    active=selection.get("metric","")
    if active not in formulas:active=""
    options_html=''.join(f'<label class="formula-tab"><input type="radio" name="metric" value="{key}"'
        f'{" checked" if key==active else ""}{" disabled" if not numeric_columns else ""}>'
        f'<span title="{escape(desc,quote=True)}">{title}</span></label>' for key,(title,desc) in formulas.items())
    tabs=f'<fieldset class="formula-picker"><legend>可用公式</legend><div class="formula-tabs">{options_html}</div></fieldset>'
    fields_html=[]
    for key,label in (("value","數值欄／分子"),("denominator","分母欄"),("group","依哪一欄分類"),("day","按月（日期欄）"),("unit","依幣別／單位分開")):
        cols=numeric_columns if key in ("value","denominator") else fields
        options='<option value="">'+('請選數值欄' if key=="value" else '請選分母欄' if key=="denominator" else "不指定")+'</option>'
        options+="".join(f'<option value="{escape(col,quote=True)}"'+(" selected" if selection.get(key)==col else "")+f'>{escape(col)}</option>' for col in cols)
        cls=' class="formula-denominator"' if key=="denominator" else ""
        fields_html.append(f'<label{cls}>{label}<select name="{key}">{options}</select></label>')
    if numeric_columns:
        alias_text="、".join(f"{k}＝{v}" for k,v in (aliases or {}).items())
        formula_value=escape(selection.get("formula",""),quote=True)
        checked=lambda key: " checked" if selection.get(key) else ""
        custom=f'<div class="custom-metric"><label for="custom-analysis-formula">輸入算式</label><input id="custom-analysis-formula" name="formula" maxlength="180" value="{formula_value}" placeholder="SUM(A*B)/SUM(B)"><p>欄位代號：{escape(alias_text)}。可用 SUM、AVG、COUNT、MIN、MAX 和加減乘除。</p><label class="mode"><input type="checkbox" name="percent" value="true"{checked("percent")}>以百分比顯示</label></div>'
        cleaning=f'<details{" open" if selection.get("drop_dupes") or selection.get("drop_outliers") else ""}><summary>選擇清洗規則（選填）</summary><p>以下只改這次計算，不改原表。</p><label class="mode"><input type="checkbox" name="drop_dupes" value="true"{checked("drop_dupes")}>排除整列重複</label><label class="mode"><input type="checkbox" name="drop_outliers" value="true"{checked("drop_outliers")}>排除檢查欄位的疑似異常（依單位比較）</label></details>'
        reset_url=escape("/analysis?"+urlencode({"sample":sample,"reset":"true","file":list(active_files)},doseq=True)+"#analysis-formulas",quote=True)
        pinned=''.join(f'<input type="hidden" name="file" value="{escape(n,quote=True)}">' for n in active_files)
        control=f'<section class="search-board" id="analysis-formulas"><form class="formula-form" action="/analysis#universal-result"><input type="hidden" name="sample" value="{sample}">{pinned}{tabs}<div class="formula-controls">{"".join(fields_html)}</div>{custom}{cleaning}<div class="work-actions"><button>開始計算</button><a class="work-button" href="{reset_url}">清除公式與結果</a></div></form></section>'
    else:
        explanation="資料中沒有可計算的數值欄。" if fields else "先上傳表格或選擇示範，再選公式與欄位。"
        control=f'<section class="search-board">{tabs}<p class="muted">{explanation}</p></section>'
    msg={"choose_currency_column":"這份表有不同幣別或單位。請選對應的分組欄，不會把 USD 和 TWD 直接相加。","column_not_found":"找不到所選欄位，請重新選擇。","empty_table":"目前沒有可分析的上傳表格。"}
    msg["choose_two_numeric_columns"]="比率需要兩個不同的數值欄，請選分子與分母。"
    titles={"finance":"金融收支","operations":"營運工單","retail":"零售銷售","inventory":"庫存異動","survey":"問卷評分"}
    banner=(f'<p class="data-source-note">內建示範 · {titles[sample]}</p>' if sample in titles else
            f'<p class="data-source-note">我的表格 · {escape(filename)}</p>' if filename else '<p class="data-source-note">尚未選擇資料</p>')
    body=analysis_table_library(files,active_files)+banner
    if source_error:body+=f'<p class="empty" role="status">{escape(source_error)}</p>'
    body+='<details'+(' open' if not fields else '')+'><summary>內建示範（選用）</summary>'+nav+'</details>'+quality_panel(quality)+control+'<div id="universal-result">'
    if error and not source_error:
        body+='<p class="empty" role="status">'+escape(msg.get(error,error if active=="custom" else "欄位或格式不符，請重新核對。"))+'</p>'
    elif result:
        r=result["results"]
        body+=f'<div class="data-layout"><section class="work-card" role="status"><h2>分析結果</h2><p>{len(r)} 組。依所選公式計算；不同幣別或單位保持分開。</p>'
        if r:
            ratio=active=="ratio"
            custom=active=="custom"
            if custom:body+=f'<p>算式：<code>{escape(result["formula"])}</code></p>'
            header=('<th>分子合計</th><th>分母合計</th>' if ratio else "")+f'<th>{formulas[active][0]}</th>'
            body+=f'<p><a href="{escape(download_url,quote=True)}">下載分析 JSON</a></p><div style="overflow:auto"><table><thead><tr><th>幣別／單位</th><th>月份</th><th>分組</th>{header}</tr></thead><tbody>'
            for row in r[:50]:
                prefix=''.join(f'<td>{escape(str(row.get(k,"")) or "—")}</td>' for k in ("unit","month","group"))
                if ratio:
                    ratio_label=format(Decimal(row["ratio"]),".2%") if row["ratio"] is not None else "分母為 0"
                    value_html=''.join(f'<td>{escape(str(row[k]))}</td>' for k in ("numerator_sum","denominator_sum"))+f'<td>{escape(ratio_label)}</td>'
                elif custom:
                    v=row["ratio"]
                    label=row["note"] if v is None else format(Decimal(v),".2%" if result["percent"] else ".8g")
                    value_html=f'<td>{escape(label)}</td>'
                else:
                    value_html=f'<td>{escape(str(row[active]))}</td>'
                body+='<tr>'+prefix+value_html+'</tr>'
            body+='</tbody></table></div>'
        else:
            body+='<p>找不到可計算的數值。請換欄位，或先查原檔格式。</p>'
        names={"bad_rows":"欄位不符／空白列","non_numeric":"不是數字","invalid_date":"日期無法解析","missing_unit":"缺幣別或單位","invalid_numeric":"未通過算式數值檢查","malformed_rows":"無法讀取的列"}
        exclusions=''.join(f'<li>{escape(names.get(k,k))}：{v} 筆</li>' for k,v in result["excluded"].items())
        body+='</section><aside class="work-card metric-quality"><span class="section-index">計算透明度</span><h2>排除明細</h2><ul>'+exclusions+'</ul>'+payload("展開欄位對照",{k:v for k,v in result.items() if k!="results"})+"</aside></div>"
    body+='</div>'
    return layout("/analysis","通用表格分析","金融收支、部門工單或其他題目都能選欄分析，不必有產線或不良率欄。",body+
                  components(["依所選欄位做加總、平均、筆數及高低值","依分類、月份及幣別分組","保留無法解析的資料筆數與可下載 JSON"],"這是描述性分析，不含匯率換算或投資建議。題目指定公式時，以題目口徑為準。"))

SETTINGS_SCRIPT="""
<script>
const pf=document.querySelector('#api-prefs'),configStatus=document.querySelector('#config-status');
pf.onsubmit=async e=>{
 e.preventDefault();const b=pf.querySelector('button');b.disabled=true;configStatus.textContent='儲存中…';
 try{const r=await fetch('/integration/settings',{method:'POST',headers:{'Content-Type':'application/json','X-Demo-Local':'1'},body:JSON.stringify(Object.fromEntries(new FormData(pf)))});
  const v=await r.json();
  if(r.ok){configStatus.textContent='已儲存在這台 Mac。沒有呼叫模型。';return;}
  const explain={invalid_embedding_url:'向量網址請用 HTTPS，結尾為 /embeddings。',invalid_chat_url:'聊天網址請用 HTTPS，結尾為 /chat/completions。',url_and_model_required:'每組的網址和模型名稱要一起填，或一起留空。',settings_not_saved:'寫入失敗，請檢查本機權限。'};
  configStatus.textContent=explain[v.detail]||'沒有儲存；請重看網址和模型名稱。';
 }catch{configStatus.textContent='無法連到本機。';}finally{b.disabled=false;}
};
</script>"""

def model_preferences_panel(prefs):
    fields=[]
    titles={"embedding_url":"向量服務網址","embedding_model":"向量模型名稱","chat_url":"聊天／工具服務網址","chat_model":"聊天／工具模型名稱"}
    for k,t in titles.items():
        fields.append(f'<label class="api-setting-field" for="api-{k}"><span>{t}</span><input id="api-{k}" name="{k}" value="{escape(prefs.get(k,""),quote=True)}" maxlength="400" autocomplete="off"></label>')
    setting='<section class="library-board"><h2>模型 API 設定</h2><p>向量模型負責索引和搜尋；聊天模型可整理答案或選工具。兩個不必填同一個。</p><form id="api-prefs">'+"".join(fields)+'<button>儲存 API 設定</button></form><p id="config-status" role="status"></p><small>只儲存網址與模型名稱，不呼叫外部服務、不把金鑰寫進網頁或交件檔。CLI 以明確開啟 API 的方式讀取設定；金鑰在終端無回顯輸入。</small></section>'
    return setting

def integration(line,source,filename,code,data,prefs):
    demo_selected=" selected" if source=="demo" else ""
    own=('<option value="local"'+(' selected' if source=="local" else '')+'>'+escape(filename)+'</option>') if filename else ""
    controls=f'<form action="/integration#api-output"><label for="line">產線</label><input id="line" name="line" value="{escape(line,quote=True)}" maxlength="64" required><label for="source">資料</label><select id="source" name="source"><option value="demo"{demo_selected}>內建練習</option>{own}</select><button>送出查詢</button></form>'
    q=urlencode({"line":line,"source":source})
    result=f'<section id="api-output" class="answer" role="status"><h2>{"有結果" if code==200 else "找不到資料"}</h2><p>狀態碼 {code} · {"另一個系統可讀取這份標準 JSON。" if code==200 else escape(data["detail"])}</p>'
    if code==200:result+=f'<a href="/report.json?{q}&amp;download=true">下載報表 JSON</a>'
    result+="</section>"+payload("展開實際 JSON",data)
    setting=model_preferences_panel(prefs)
    return layout("/integration","API 試跑與模型設定","先試問一次本機報表，再按需要設定外部模型。這是兩件不同的事。",
                  '<div class="stepbar"><span>01 選產線</span><span>02 送出</span><span>03 看回傳、下載</span></div>'+controls+result+setting+
                  components(["FastAPI：接收查詢","Pydantic：檢查輸入格式","本機 OpenAPI：API 規格"],"不提供批次外部呼叫；目前報表端點依產線回傳統計與例外。")+
                  '<p><a href="/openapi.json">本機 OpenAPI 規格</a></p>'+SETTINGS_SCRIPT)

LOCAL_MODELS_SCRIPT="""
<script>
const lf=document.querySelector('#local-model-picker'),lm=document.querySelector('#local-model-msg'),tf=document.querySelector('#local-model-check'),tm=document.querySelector('#local-chat-result');
lf.onsubmit=async e=>{e.preventDefault();const b=lf.querySelector('button');b.disabled=true;lm.textContent='儲存中…';
try{const r=await fetch('/models/settings',{method:'POST',headers:{'X-Demo-Local':'1','Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(lf)))});lm.textContent=r.ok?'已儲存。文件問答下次查詢會用這個選擇。':'沒有儲存，請重試。';}catch{lm.textContent='沒有連上本機。';}finally{b.disabled=false;}};
tf.onsubmit=async e=>{e.preventDefault();const b=tf.querySelector('button');b.disabled=true;tm.textContent='本地模型正在回答…';
try{const r=await fetch('/models/chat',{method:'POST',headers:{'X-Demo-Local':'1','Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(tf)))});const j=await r.json();tm.textContent=r.ok?j.answer:(j.detail==='chat_model_not_selected'?'請先選聊天模型後按儲存。':'暫時沒有收到本地模型回答。請先雙擊「啟動本地模型.command」。');}catch{tm.textContent='無法連到本機。';}finally{b.disabled=false;}};
</script>"""

def model_picker(settings):
    def options(name,choices):
        return ''.join(f'<option value="{k}"'+(" selected" if settings[name]==k else "")+f'>{label}</option>' for k,label in choices)
    chat=options("chat",[("off","不使用聊天模型"),("qwen","Qwen2.5-Coder 1.5B（本機）")])
    embed=options("embedding",[("character","本機字元向量（免模型，隨時可用）"),("qwen","Qwen3 Embedding 0.6B（本機語意模型）")])
    return layout("/models","本地模型","離線也能分別決定誰找文件、誰回答。外部 API 另外設定。",f"""
    <div class="stepbar"><span>01 雙擊「啟動本地模型.command」</span><span>02 選模型</span><span>03 儲存或試聊</span></div>
    <section class="library-board"><h2>選擇並儲存</h2>
      <form id="local-model-picker"><label>文件檢索 <select name="embedding">{embed}</select></label><label>聊天 <select name="chat">{chat}</select></label><button>儲存本地模型</button></form>
      <p id="local-model-msg" role="status"></p><small>選本地語意模型後，在文件頁用「混合搜尋」或「語意搜尋」。關鍵字檢索（BM25 排名）不呼叫模型。字元向量（TF-IDF）以相鄰兩字元為一組並比較餘弦相似度，不是 Qwen3 語意向量。</small>
    </section>
    <section class="library-board"><h2>測試聊天模型</h2><p>只是試聊，不會讀你上傳的附件，也不冒充有來源的回答。</p>
      <form id="local-model-check"><label for="probe">問題</label><input id="probe" name="question" required maxlength="350" value="請只回答：本機模型測試"><button>問本地模型</button></form>
      <pre id="local-chat-result" role="status"></pre>
    </section><p><a href="/integration">外部 API 的設定入口</a></p>"""+LOCAL_MODELS_SCRIPT)


WORKBOOK_SCRIPT="""<script>
const excelForm=document.querySelector('#workbook-upload'), excelStatus=document.querySelector('#workbook-status');
excelForm.onsubmit=async e=>{
  e.preventDefault();
  const file=document.querySelector('#workbook-file').files[0];
  if(!file)return;
  const b=excelForm.querySelector('button');b.disabled=true;
  excelStatus.textContent='正在讀取工作表…';
  try{
    const r=await fetch('/extract/workbook',{method:'POST',headers:{'X-Demo-Local':'1','X-Demo-Filename':encodeURIComponent(file.name),'Content-Type':'application/octet-stream'},body:file});
    if(r.ok){location.assign('/extract/workbook#worksheets');return}
    excelStatus.textContent='無法讀取。請確認是完整的 .xlsx、檔案小於 5 MB，且工作表未超過限制。';
  }catch{excelStatus.textContent='無法連上本機。'}finally{b.disabled=false}
};
</script>"""


def workbook_page(name,sheets,selected,fields,result):
    body="""<p class="samples"><a href="/extract">查看 PDF／Word／TXT 範例</a></p>
    <section class="library-board"><h2>上傳 Excel 工作簿</h2>
    <form id="workbook-upload"><label for="workbook-file">檔案</label><input id="workbook-file" type="file" accept=".xlsx" required><button>讀取工作表</button></form>
    <p id="workbook-status" role="status"></p><small>第一列當欄名，不重算公式；未快取的公式結果與空白保留空值。原始檔不會保存。</small></section>"""
    if sheets:
        body+=clear_uploads_button("workbook")
        options=''.join(f'<option{" selected" if k==selected else ""}>{escape(k)}</option>' for k in sheets)
        body+=f'<form id="worksheets" action="/extract/workbook"><label for="sheet">工作表</label><select id="sheet" name="sheet">{options}</select><button>切換工作表</button></form><p>來源：{escape(name)} · {escape(selected)}</p>'
        page=sheets[selected]
        if page["columns"]:
            checks=''.join(f'<label class="mode"><input type="checkbox" name="field" value="{escape(k,quote=True)}"{" checked" if k in fields else ""}>{escape(k)}</label>' for k in page["columns"])
            body+=f'<form action="/extract/workbook#workbook-results"><input type="hidden" name="sheet" value="{escape(selected,quote=True)}">{checks}<button>預覽擷取</button></form>'
        else:
            body+=f'<p class="empty">{escape(page["issue"] or "第一列沒有可用欄名。")}</p>'
    if result is not None:
        link="/extract/workbook?"+urlencode([("sheet",selected),*(("field",k) for k in fields),("download","true")])
        keys=result["fields"]
        columns=''.join(f'<th>{escape(k)}</th>' for k in keys)
        rows=''.join('<tr><td>'+str(r["row"])+'</td>'+''.join(
             f'<td>{escape(str(r["cells"][k]["value"]) if r["cells"][k]["value"] is not None else "空白")} <small>{r["cells"][k]["cell"]}</small></td>' for k in keys)+'</tr>' for r in result["rows"][:20])
        body+=f'<section id="workbook-results" class="work-card"><h2>擷取預覽 · {len(result["rows"])} 筆</h2><p>預覽前 20 筆；下載內容包含擷取的全部資料。</p><a class="work-button primary" href="{escape(link,quote=True)}">下載 JSON</a><div style="overflow:auto"><table><thead><tr><th>原列</th>{columns}</tr></thead><tbody>{rows}</tbody></table></div></section>'
    return layout("/extract","Excel 欄位擷取","上傳工作簿，選工作表和欄位。每個值都附原始儲存格。",body+WORKBOOK_SCRIPT)


EXAMPLES=(
    ("文件問答","PDF-200 ALARM-931"),
    ("通用表格","加總 金額"),
    ("資料衝突","DEMO-100 交接時限"),
    ("製造資料","L1 不良率"),
)

AGENT_MODELS={
    "bm25":"關鍵字搜尋（BM25 排名，免模型）",
    "character":"混合搜尋：關鍵字＋字元相似（免模型）",
    "qwen":"混合搜尋：關鍵字＋語意（Qwen3 Embedding 0.6B）",
}

def query_tools(question,source,sheet,work_name,work,tab_name,tab,mfg,docs,report,model="bm25"):
    import generic_analysis
    import workbook_extract
    q=question.strip()
    def resp(tool,status,answer,evidence=None,details=None,used="未使用模型"):
        return {"tool":tool,"status":status,"answer":answer,"evidence":evidence or [],"result":details,"model":used}
    from calculation_plan import needs_plan
    if needs_plan(q):
        return resp("規劃算式","confirm_formula","這個問題需要先核對算式、欄位或篩選條件。請在 Agent 的「規劃算式」確認，不會用其他公式代算。")
    if q.startswith(("擷取","提取")):
        if not work:return resp("Excel 欄位擷取","missing","先到「欄位擷取」上傳 Excel。")
        selected=sheet or next(iter(work))
        names=re.split(r"[,，、]+",q[2:].strip())
        fields=[k.strip() for k in names if k.strip()]
        try:result=workbook_extract.project(work_name,work,selected,fields)
        except (KeyError,ValueError):return resp("Excel 欄位擷取","missing","找不到指定欄名或工作表；請使用原始欄名。")
        first=[f'{k}：{v["value"] if v["value"] is not None else "空白"}（{v["cell"]}）'
               for row in result["rows"][:3] for k,v in row["cells"].items()]
        return resp("Excel 欄位擷取","ok",f'擷取 {len(result["rows"])} 筆。',[f'{work_name} · {selected}',*first],result)
    if any(key in q for key in ("加總","合計","平均","最小","最大","統計")):
        if tab is None:return resp("通用表格分析","missing","先到「通用表格分析」上傳表格。")
        found=sorted((key for key in tab["fields"] if key in q),key=len,reverse=True)
        unit=next((c for c in tab["fields"] if c.casefold() in {"currency","ccy","幣別","貨幣","unit","單位"}),"")
        selected_metric="average" if "平均" in q else "minimum" if "最小" in q else "maximum" if "最大" in q else "sum"
        columns=[k for k in found if k!=unit]
        if len(columns)!=1:return resp("通用表格分析","missing","請輸入一個確切的數值欄名，例如「加總 金額」。",[tab_name])
        value=columns[0]
        # Preserve units. A named category in the request is not silently applied.
        try:
            group="類別" if source=="demo" and "類別" in tab["fields"] else ""
            result=generic_analysis.summarize(tab,value,group=group,unit=unit)
        except ValueError:return resp("通用表格分析","missing","沒有可用的數值欄位。",[tab_name])
        lines=[f'{x["unit"]} {x["group"]}：{x[selected_metric]}（{x["count"]} 筆）' for x in result["results"][:8]]
        status="ok" if lines else "missing"
        return resp("通用表格分析",status,"；".join(lines) if lines else "沒有可計算的數值。",
                    [f'{tab_name} · {value} · {len(result["results"])} 組',f'依 {unit} 分開，不跨單位加總' if unit else "數值依來源欄位計算"],result)
    if "不良率" in q:
        choices={r["line"] for r in mfg["rows"]} if mfg else set()
        selected=[k for k in choices if re.search(r"(?<![A-Za-z0-9_-])"+re.escape(k)+r"(?![A-Za-z0-9_-])",q,re.I)]
        if not selected:
            prefixed=re.search(r"產線[：:\s]*([A-Za-z0-9_.-]+)",q)
            if prefixed:selected=[prefixed.group(1).upper()]
        if len(selected)!=1 or mfg is None:return resp("製造報表","missing","請先選資料並指定一條產線。")
        line=selected[0]
        value=report(mfg,line,0)
        if value["status"]!="ok":return resp("製造報表","missing","查無有效資料，不會回傳 0%。",[line])
        o=value["overall"]
        rate=o["weighted_defect_rate"]
        return resp("製造報表","ok",f'{rate:.2%}' if rate is not None else "無法計算",
                    [f'{line} · {o["defect_count"]} 不良 ÷ {o["output_qty"]} 產量'],o)
    if source=="local" or re.search(r"(?i)[A-Z]{2,}-\d+",q) or q.startswith(("查文件 ","搜尋 ")):
        corpus=retrieval.load_docs(DEMO/"docs") if source=="demo" else docs
        question=q.removeprefix("查文件 ").removeprefix("搜尋 ")
        used="未使用模型"
        tool="文件檢索｜"+{"bm25":"BM25","character":"BM25 + 本機字元向量","qwen":"BM25 + Qwen3 Embedding"}[model]
        if model=="qwen":
            ids={t for t in retrieval.tokens(question) if re.search("[a-z]",t) and re.search("[0-9]",t)}
            eligible=any(ids.issubset(set(retrieval.tokens(x["text"]))) for x in corpus)
            try:
                hits=local_models.search(question,corpus,"hybrid") if eligible else []
            except ValueError:
                return resp(tool,"model_unavailable","未能取得所選本機模型的結果。請確認模型已啟動，或改用免模型模式。",used="Qwen3 Embedding 0.6B（未完成）")
            if eligible:used="Qwen3 Embedding 0.6B"
        else:
            hits=local_hybrid(question,corpus,"hybrid" if model=="character" else "bm25")
        intent=exam_cases.intent(question) if source=="demo" else None
        outcome,hits=exam_cases.excerpts(intent,hits,corpus) if intent else ("answer" if hits else "missing",hits)
        evidence=[f'{x["source"]} · '+(f'第 {x["page"]} 頁 · ' if "page" in x else '')+
                  f'第 {x["start_line"]}–{x["end_line"]} 行 · {x["quote"]}' for x in hits[:5]]
        answer="來源衝突，請核對版本。" if outcome=="conflict" else hits[0]["quote"] if hits else "沒有找到可引用內容。"
        return resp(tool,outcome,answer,evidence,hits,used=used)
    return resp("未選用工具","unsupported","不支援這個問題。可查文件、擷取 Excel 欄位或分析表格。")


def agent_chat(question,source,work,sheet,result,model="bm25",has_upload=False):
    query=escape(question or "",quote=True)
    ex=''.join(f'<a href="/agent?{urlencode({"q":q,"source":"demo","model":model})}">{label}</a>' for label,q in EXAMPLES)
    src=''.join(f'<option value="{k}"{" selected" if k==source else ""}>{label}</option>' for k,label in (("local","我的資料"),("demo","內建示範")))
    ws=''.join(f'<option{" selected" if k==sheet else ""}>{escape(k)}</option>' for k in (work or {}))
    sheet_field=f'<label>Excel 工作表 <select name="sheet">{ws}</select></label>' if ws else ""
    identity=figma_theme.icon("spark")
    model_options=''.join(f'<option value="{k}"{" selected" if k==model else ""}>{label}</option>' for k,label in AGENT_MODELS.items())
    model_select=f'<label for="agent-model">文件檢索方式</label><select id="agent-model" name="model">{model_options}</select>'
    model_note="本次使用："+result["model"] if result else "尚未查詢"
    body=f'<div class="agent-layout"><section class="work-card"><div class="agent-identity"><span>{identity}</span><div><strong>資料助理</strong><small>{"內建合成示範" if source=="demo" else "本機資料 · 不連外"}</small><small class="agent-model-status">{escape(model_note)}</small></div></div>'
    body+='<p><a class="work-button" href="/agent/calc">讓 Agent 先規劃算式</a></p>'
    if result:
        body+=f'<p class="chat-question">{query}</p>'
        body+=f'<div class="plain-step"><div><small>回答</small><p>{escape(result["answer"])}</p></div></div>'
        body+=fold("查看這次使用的工具",f'<p>{escape(result["tool"])}</p>')
    body+=f'<form class="agent-composer" action="/agent"><label for="agent-source">資料來源</label><select id="agent-source" name="source">{src}</select>{model_select}{sheet_field}<small class="agent-tool-note">關鍵字檢索（BM25 排名）比對詞彙；字元向量（TF-IDF）比對字元組；Qwen3 Embedding 比對語意。表格與欄位擷取不使用這些檢索方式。</small><div class="search-input"><label for="agent-q">問題</label><input name="q" id="agent-q" maxlength="250" required value="{query}" placeholder="輸入想查、擷取或計算的內容"><button>送出</button></div></form><details><summary>內建示範（選用）</summary><div class="samples">{ex}</div></details></section>'
    evidence=result["evidence"] if result else []
    refs=''.join('<li>'+escape(x)+'</li>' for x in evidence)
    body+='<aside class="work-card"><span class="section-index">可追溯結果</span><h2>查詢依據</h2>'
    body+=f'<ul class="trace-list">{refs}</ul>' if refs else '<p>找到的文件、儲存格或計算資料會列在這裡。沒有來源就不補答案。</p>'
    if result:
        link="/api/workspace/query?"+urlencode({"q":question,"source":source,"model":model,**({"sheet":sheet} if sheet else {})})
        body+=f'<div class="work-actions"><a class="work-button" id="agent-view-json" target="_blank" rel="noopener" href="{escape(link,quote=True)}">查看本次 JSON</a><a class="work-button" id="agent-download-json" href="{escape(link,quote=True)}&amp;download=true">下載 JSON</a><a class="work-button primary" href="{escape(link.replace("/query?","/report.html?"),quote=True)}">下載單一 HTML</a></div>'
        body+=f'<textarea hidden id="agent-json-content">{escape(json.dumps(result,ensure_ascii=False,indent=2))}</textarea>'
        body+="""<script>
const agentJsonLink=document.querySelector('#agent-download-json');
const agentJson=document.querySelector('#agent-json-content');
if(agentJsonLink&&agentJson&&typeof URL.createObjectURL==='function'){
 const href=URL.createObjectURL(new Blob([agentJson.value],{type:'application/json'}));
 document.querySelector('#agent-view-json').href=href;
 agentJsonLink.href=href;
 agentJsonLink.download='workspace-result.json';
}
</script>"""
    if has_upload:body+=clear_uploads_button("agent")
    body+='<p class="muted">文件會查所有已上傳來源；表格助手預設用最近上傳的一份。需要堆疊多份表格，請到「數據分析」圈選。</p>'
    body+='<p><a href="/knowledge?source=local">上傳文件</a> · <a href="/analysis?sample=local">上傳表格</a> · <a href="/extract">選欄擷取</a></p></aside></div>'
    return layout("/agent","用白話拆解每次回答","看清楚你問什麼、程式查了什麼，以及答案來自哪裡。",body)


def api_playground(prefs,work,has_upload=False):
    samples=''.join(
        f'<a href="/api/workspace/query?{urlencode({"q":q,"source":"demo"})}" target="_blank" rel="noopener">{label} JSON</a>'
        for label,q in EXAMPLES)
    ws=''.join(f'<option>{escape(k)}</option>' for k in (work or {}))
    ws_html=f'<label>Excel 工作表 <select name="sheet">{ws}</select></label>' if ws else ''
    body=f"""<section class="library-board"><h2>本機 API 試跑</h2>
    <p>不預設題型或欄位。先上傳資料、輸入操作，查看工具、結果和可核對的來源。</p>
    <form action="/api/workspace/query" id="workspace-api-form">
      <label>資料來源 <select name="source"><option value="local">我的資料</option><option value="demo">內建示範</option></select></label>
      {ws_html}<label for="api-question">查詢</label><input id="api-question" name="q" maxlength="250" required placeholder="輸入文件問題、統計或擷取欄位"><button>執行 API</button>
    </form><p id="workspace-api-message" role="status"></p><pre id="workspace-api-result" hidden></pre><div id="workspace-api-actions" hidden><div class="work-actions"><a class="work-button" id="workspace-api-open" target="_blank" rel="noopener">查看 JSON</a><a class="work-button" id="workspace-api-download" download="workspace-result.json">下載 JSON</a></div></div>
    <p><a href="/knowledge?source=local">上傳文件</a> · <a href="/analysis?sample=local">上傳表格</a> · <a href="/extract">選欄擷取</a></p>
    <h3>內建示範（選用）</h3><div class="samples">{samples}</div>
    <p><a href="/integration?line=L1&amp;source=demo">製造報表 API 範例</a> · <a href="/openapi.json">OpenAPI 規格</a></p></section>"""
    body+=model_preferences_panel(prefs)
    body+="""<script>
const aform=document.querySelector('#workspace-api-form'), ast=document.querySelector('#workspace-api-message'),
  ao=document.querySelector('#workspace-api-result'), alink=document.querySelector('#workspace-api-open'), adownload=document.querySelector('#workspace-api-download');
const actions=document.querySelector('#workspace-api-actions');
let objectUrl;
aform.onsubmit=async e=>{
 e.preventDefault();const b=aform.querySelector('button'); b.disabled=true;
 const target=aform.getAttribute('action')+'?'+new URLSearchParams(new FormData(aform)).toString();
 ast.textContent='執行中…'; ao.hidden=true; actions.hidden=true;
 if(objectUrl){URL.revokeObjectURL(objectUrl);objectUrl=undefined}
 try{const r=await fetch(target,{cache:'no-store'});const reply=await r.json();
     ast.textContent='HTTP '+r.status+' · '+(reply.status||'輸入未通過驗證');
     ao.textContent=JSON.stringify(reply,null,2);ao.hidden=false;
     if(r.ok){
       objectUrl=URL.createObjectURL(new Blob([JSON.stringify(reply,null,2)],{type:"application/json"}));
       alink.href=objectUrl;adownload.href=objectUrl;actions.hidden=false}
 }catch{ast.textContent='無法連上本機 API。'}finally{b.disabled=false}
};
</script>"""
    if has_upload: body+=clear_uploads_button("agent")
    return layout("/integration","API 試跑與模型設定","使用同一套本機工具取得 JSON；外部模型設定是另一個區塊。",body+SETTINGS_SCRIPT)


def standalone_report(question,result,source):
    refs=''.join('<li>'+escape(x)+'</li>' for x in result["evidence"])
    info="內建合成示範" if source=="demo" else "本機上傳資料"
    return f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>查詢結果</title><style>
body{{margin:0;background:#f3f5f1;color:#18352e;font:16px/1.7 system-ui,sans-serif}}
main{{margin:4rem auto;padding:0 1rem;max-width:800px}}section{{background:#fff;border:1px solid #d9e1dc;border-radius:14px;padding:1.2rem;margin:1rem 0;overflow-wrap:anywhere}}h1,h2{{line-height:1.2}}small{{color:#526a61}}
</style></head><body><main><small>{info} · 靜態結果，不需服務</small><h1>查詢結果</h1>
<section><h2>查詢</h2><p>{escape(question)}</p><small>{escape(result["tool"])} · {escape(result["status"])}</small></section>
<section><h2>結果</h2><p>{escape(result["answer"])}</p></section>
<section><h2>查詢依據</h2>{'<ul>'+refs+'</ul>' if refs else '<p>沒有可列出的來源。</p>'}</section>
</main></body></html>"""

def direct_file_picker(scope, accepts, *, multiple):
    formats="文件：PDF、Word、TXT、Markdown、HTML。表格："+("CSV、TSV、Excel、平面 JSON／JSONL" if multiple else "Excel .xlsx")
    return f'''<form class="direct-upload" data-upload-scope="{scope}"><label class="direct-upload-fallback" for="{scope}-upload-file">選擇檔案</label>
      <input id="{scope}-upload-file" type="file" accept="{accepts}"{" multiple" if multiple else ""} required>
      <button type="button" data-upload-open hidden>上傳檔案</button><button type="submit" class="direct-upload-fallback">上傳</button></form><small>{formats}；單檔上限 5 MB。{"表格每次只保留一份。" if multiple else ""}</small>
      <p id="{scope}-upload-message" role="status" aria-live="polite"></p>'''


def inline_excel_fields(name,sheets,selected,fields,result):
    if not sheets:
        return '<p class="empty">請使用上方「上傳檔案」選擇 Excel (.xlsx)。</p>'
    options=''.join(f'<option value="{escape(k,quote=True)}"{" selected" if k==selected else ""}>{escape(k)}</option>' for k in sheets)
    body=f'''<p class="data-source-note">已上傳 · {escape(name)}</p>
      <form id="worksheets" action="/extract"><input type="hidden" name="file" value="xlsx"><input type="hidden" name="source" value="local">
      <label for="sheet">工作表</label><select id="sheet" name="sheet" onchange="this.form.requestSubmit()">{options}</select><button>切換</button></form>'''
    page=sheets[selected]
    checks=''.join(f'<label class="mode"><input type="checkbox" name="field" value="{escape(k,quote=True)}"{" checked" if k in fields else ""}>{escape(k)}</label>' for k in page["columns"])
    if checks:
        body+=f'''<form action="/extract#workbook-results"><input type="hidden" name="file" value="xlsx"><input type="hidden" name="source" value="local">
          <input type="hidden" name="sheet" value="{escape(selected,quote=True)}">{checks}<button>預覽擷取</button></form>'''
    else:
        body+=f'<p class="empty">{escape(page["issue"] or "第一列沒有可用欄名。")}</p>'
    if result is not None:
        query=urlencode([("file","xlsx"),("source","local"),("sheet",selected),*(("field",k) for k in fields),("download","true")])
        keys=result["fields"]
        columns=''.join(f'<th scope="col">{escape(k)}</th>' for k in keys)
        rows=''.join('<tr><td>'+str(r["row"])+'</td>'+''.join(
            f'<td>{escape(str(r["cells"][k]["value"]) if r["cells"][k]["value"] is not None else "空白")} <small>{escape(r["cells"][k]["cell"])}</small></td>' for k in keys)+'</tr>' for r in result["rows"][:20])
        body+=f'<section id="workbook-results"><h2>擷取預覽 · {len(result["rows"])} 筆</h2><a class="work-button" href="/extract?{escape(query,quote=True)}">下載 JSON</a><div style="overflow:auto"><table><thead><tr><th scope="col">原列</th>{columns}</tr></thead><tbody>{rows}</tbody></table></div></section>'
    return body+'<small>第一列當欄名。不重算公式；未快取的公式與空白保留空值。</small>'


DIRECT_UPLOAD_SCRIPT = """<script>
(() => {
 const picker=document.querySelector('[data-upload-scope]');
 const scope=picker.dataset.uploadScope;
 const input=picker.querySelector('input[type=file]');
 const info=document.getElementById(scope+'-upload-message');
 const button=picker.querySelector('[data-upload-open]');
 button.hidden=false;picker.classList.add('direct-upload-ready');
 button.addEventListener('click',()=>input.click());
 const tableExts=new Set(['csv','tsv','xlsx','json','jsonl','ndjson']);
 const filenames={file_over_5mb:'檔案超過 5 MB',duplicate_name:'已有同名檔案，沒有覆蓋',table_library_full:'表格暫存已達份數或筆數上限',library_full:'文件暫存空間已滿',ocr_required:'未讀到可靠文字層，本檔未接受；請核對原頁後再上傳',unsupported_file:'不支援的檔案格式',invalid_workbook:'Excel 無法讀取'};
 input.addEventListener('change',()=>{if(input.files.length&&!button.disabled)picker.requestSubmit();});
 picker.addEventListener('submit',async e=>{
   e.preventDefault();
   const files=Array.from(input.files);if(!files.length)return;
   button.disabled=true;info.textContent='處理中…';
   const failed=[];let count=0,last=null;
   try {
     for(const file of files){
       const ext=file.name.split('.').pop().toLowerCase();
       const url=scope==='workspace'?(tableExts.has(ext)?'/analysis/file':'/knowledge/files'):(ext==='xlsx'?'/extract/workbook':'/extract/file');
       try{
         const response=await fetch(url,{method:'POST',headers:{'X-Demo-Local':'1','X-Demo-Filename':encodeURIComponent(file.name),'Content-Type':'application/octet-stream'},body:file});
         const data=await response.json();
         if(response.ok){count++;last=ext==='xlsx'?'xlsx':data.format;}
         else failed.push(file.name+'：'+(data.review_pages?.length?'第 '+data.review_pages.join('、')+' 頁需核對。':'')+(filenames[data.detail]||'檔案無法讀取'));
       }catch{failed.push(file.name+'：無法連上本機');}
     }
     if(count){
       const path=scope==='workspace'?'/workspace':'/extract?source=local&file='+encodeURIComponent(last);
       const response=await fetch(path,{cache:'no-store'});
       if(!response.ok)throw Error('readback');
       const doc=new DOMParser().parseFromString(await response.text(),'text/html');
       const selectors=scope==='workspace'?['#workspace-upload-list','.workspace-readiness']:['#extract-work-area'];
       for(const key of selectors){
         const current=document.querySelector(key), after=doc.querySelector(key);
         if(current&&after)current.replaceWith(after);
       }
       if(scope==='extract')history.replaceState(null,'',path);
     }
     info.textContent=[count?'已上傳 '+count+' 份。':'',...failed].filter(Boolean).join('；');
   }catch{info.textContent='已處理檔案，但未能重新讀取畫面。'}
   finally{button.disabled=false;input.value='';}
 });
})();
</script>"""


def calculation_page(question,filename,table,aliases,proposal,note,pin,result,planner):
    question=escape(question or "",quote=True)
    planner_options=''.join(f'<option value="{k}"{" selected" if k==planner else ""}>{v}</option>'
        for k,v in (("rules","自動建議（不使用模型）"),("qwen","規則不夠時試本機模型（Qwen2.5-Coder）")))
    body=f"""<div class="agent-layout"><section class="work-card">
    <span class="section-index">01 · 說明要算什麼</span><h2>讓 Agent 先想算式</h2>
    <form action="/agent/calc"><label for="plan-question">問題</label>
    <input id="plan-question" name="q" maxlength="250" required value="{question}" placeholder="例如：各產品毛利率是多少？">
    <label for="plan-method">建議方式</label><select id="plan-method" name="planner">{planner_options}</select><button>提出算式</button></form>
    <p><a href="/analysis?sample=local">上傳表格</a> · <a href="/agent">回到資料助理</a></p>
    <p>提出算式不會先算出數字。模型只看問題和欄名，不讀取資料列、不連外。</p>
    </section><aside class="work-card"><span class="section-index">來源資料</span><h2>可用欄位</h2>"""
    if table is None:
        body+='<p>還沒有上傳表格。</p>'
    else:
        body+='<p>最近上傳的表格：'+escape(filename)+'</p>'
        body+=clear_uploads_button("analysis")
        if aliases:body+='<ul class="trace-list">'+''.join(f'<li><b>{key}</b> · {escape(name)}</li>' for key,name in aliases.items())+'</ul>'
        else:body+='<p>找不到可計算的數值欄。</p>'
    body+='</aside></div>'
    if note:body+=f'<p class="empty" role="status">{escape(note)}</p>'
    if aliases:
        formula=escape(proposal.get("formula",""),quote=True)
        params=escape(pin,quote=True)
        from calculation_plan import human_formula
        try:plain=human_formula(proposal.get("formula",""),aliases)
        except ValueError:plain=""
        explanation=f'<p class="data-source-note">{escape(plain)}</p>' if plain else ""
        def columns(key,label):
            opts='<option value="">不指定</option>'+''.join(
                f'<option value="{escape(k,quote=True)}"{" selected" if k==proposal.get(key) else ""}>{escape(k)}</option>' for k in table["fields"])
            return f'<label>{label}<select name="{key}">{opts}</select></label>'
        body+=f"""<section class="work-card" style="margin-top:1rem">
        <span class="section-index">02 · 核對再計算</span><h2>確認或修改算式</h2>{explanation}
        <p>可用 SUM（合計）、AVG（平均）、COUNT（有效筆數）、MIN（最小）、MAX（最大），以及加減乘除。例：SUM(A*B)/SUM(B)。</p>
        <form action="/agent/calc#planned-output">
        <input type="hidden" name="sheet_pin" value="{params}"><input type="hidden" name="q" value="{question}"><input type="hidden" name="planner" value="{planner}">
        <input type="hidden" name="run" value="true"><label for="planned-formula">算式</label><input id="planned-formula" name="formula" value="{formula}" maxlength="180" required placeholder="SUM(A)">
        {columns("group","分組欄")}{columns("unit","幣別／單位欄")}
        <label class="mode"><input type="checkbox" name="percent" value="true"{(" checked" if proposal.get("percent") else "")}>以百分比呈現</label>
        <button>確認並計算</button></form>
        <p>所有參與算式的欄位都要有有效數字，否則整列排除。分母為零不回傳 0。若題目要求特定篩選，請先整理來源資料。</p></section>"""
    if result is not None:
        values=result["results"]
        rows=[]
        for x in values[:50]:
            v=x["ratio"]
            val="無法計算" if v is None else format(Decimal(v),".2%") if result["percent"] else format(Decimal(v),".8g")
            sums="；".join(f"{a} = {b}" for a,b in x["aggregates"].items())
            rows.append("<tr>"+''.join(f'<td>{escape(str(cell))}</td>' for cell in (x["group"],x["unit"] or "—",x["count"],val,x["note"] or sums))+"</tr>")
        dl=urlencode({"run":"true","download":"true","q":proposal.get("question",""),"sheet_pin":pin,
                      "formula":result["formula"],"group":result["group"],"unit":result["unit"],"percent":str(result["percent"]).lower()})
        body+=f"""<section class="work-card" style="margin-top:1rem" id="planned-output"><h2>計算結果</h2>
        <p>無效數值 {result["excluded"]["invalid_numeric"]} 筆；缺單位 {result["excluded"]["missing_unit"]} 筆；無法讀取的列 {result["excluded"]["malformed_rows"]} 筆。</p>
        <a class="work-button" href="/agent/calc?{escape(dl,quote=True)}">下載 JSON</a> <a class="work-button" href="/agent/calc?{escape(dl,quote=True)}&amp;format=html">下載 HTML</a>
        <div style="overflow:auto"><table><thead><tr><th>分組</th><th>單位</th><th>有效筆數</th><th>結果</th><th>計算依據</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></section>"""
    return layout("/agent","規劃算式","先核對算式和欄位，再用你上傳的整張表計算。",body)
