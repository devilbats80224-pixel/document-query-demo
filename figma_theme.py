"""Local adaptation of the supplied Figma Make export. No external assets."""
from html import escape

ICONS = {
    "home": '<path d="m3 11 9-8 9 8M5 10v10h14V10M9 20v-6h6v6"/>',
    "file": '<path d="M6 2h8l4 4v16H6zM14 2v5h5M9 12h6M9 16h6"/>',
    "chart": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "spark": '<path d="m12 2 1.7 5.3L19 9l-5.3 1.7L12 16l-1.7-5.3L5 9l5.3-1.7zM19 16l.7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7z"/>',
    "upload": '<path d="M12 16V3M7 8l5-5 5 5M4 15v6h16v-6"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m16 16 5 5"/>',
    "code": '<path d="m8 6-6 6 6 6m8-12 6 6-6 6m-2-14-4 16"/>',
    "model": '<path d="M4 4h16v16H4zM9 9h6v6H9zM8 1v3m8-3v3M8 20v3m8-3v3M1 8h3m-3 8h3m16-8h3m-3 8h3"/>',
}
def icon(name, size=18):
    return f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>'

MARK = '<span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span>'
NAV_ICONS = {"/workspace":"home","/knowledge":"file","/":"chart","/analysis":"chart","/extract":"file","/agent":"spark","/integration":"code","/models":"model","/guide":"file"}

def navigation(tracks, path):
    def link(url, label):
        current=' aria-current="page"' if url==path else ''
        return f'<a class="nav-link" href="{url}"{current}>{icon(NAV_ICONS[url])}<b>{escape(label)}</b></a>'
    primary=(("/workspace","總覽"),("/knowledge","文件檢索"),("/analysis","數據分析"),("/agent","智慧 Agent"))
    shown={url for url,_ in primary}
    extra=[(url,label) for url,_,label in tracks if url not in shown]
    extras=''.join(link(url,label) for url,label in extra)
    expanded=' open' if path in {url for url,_ in extra} else ''
    return ''.join(link(url,label) for url,label in primary)+f'<details class="nav-advanced"{expanded}><summary>其他工具</summary>{extras}</details>'

def rail(path):
    items=(("/workspace","準備資料","選擇文件或表格"),("/knowledge","查詢與分析","問一題、算一筆"),("/guide","核對與交付","確認來源與輸出"))
    stage=0 if path=="/workspace" else 2 if path in ("/agent","/guide","/integration") else 1
    return '<nav class="step-rail" aria-label="操作流程">'+''.join(
        f'<a href="{link}" class="step{" stage" if idx==stage else " previous" if idx<stage else ""}"><span>{("✓" if idx<stage else idx+1)}</span><div><b>{title}</b><small>{sub}</small></div></a>'
        for idx,(link,title,sub) in enumerate(items))+'</nav>'

# Palette, brand mark, side rail, spacing, card geometry and status panels adapted
# from the user's Make export (src/styles.css and src/App.tsx).
CSS = """
:root{--ink:#18352e;--muted:#526a61;--line:#d9e1dc;--blue:#2f6c5c;--forest:#153e34;--deep:#0d2f27;--mint:#dcebe3;--cream:#f3f5f1;--sand:#d8b36c;--panel:#fff}
body{background:var(--cream);font: 15px/1.6 system-ui,"PingFang TC",sans-serif}
.shell{grid-template-columns:246px minmax(0,1fr)}
.side{position:sticky;top:0;height:100dvh;padding:28px 18px 18px;background:var(--deep);overflow-y:auto;gap:3px}
.side .brand{display:flex;align-items:center;gap:12px;padding:0 7px 26px;color:#fff}
.brand strong,.brand small{display:block}.brand strong{font-size:17px;letter-spacing:.04em}.brand small{font-size:9px;letter-spacing:.16em;color:#acc5ba}
.brand-mark{width:34px;height:34px;padding:7px;border-radius:9px;display:inline-flex;align-items:end;justify-content:center;gap:3px;background:#e8a85c;flex:0 0 auto}
.brand-mark i{width:4px;border-radius:2px 2px 0 0;background:var(--deep)}.brand-mark i:nth-child(1){height:9px}.brand-mark i:nth-child(2){height:18px}.brand-mark i:nth-child(3){height:13px}
.nav-caption{padding:0 12px 8px;color:#acc5ba;font-size:11px;font-weight:700;letter-spacing:.14em}
.side .nav-link{display:flex;align-items:center;gap:12px;padding:10px 12px;color:#c7ddd4;text-decoration:none}.nav-link b{font-weight:550}
.side .nav-link:hover{background:#163c32;color:#fff}.side .nav-link[aria-current=page]{background:#295448;box-shadow:inset 3px 0 #e3b665;color:#fff}
.sidebar-note{display:flex;gap:9px;margin:auto 2px 0;padding:12px;border:1px solid #285044;border-radius:10px;background:#12362d}.sidebar-note strong,.sidebar-note small{display:block}.sidebar-note strong{font-size:12px}.sidebar-note small{color:#acc5ba;font-size:11px}
.environment-dot{display:inline-block;flex:0 0 auto;width:7px;height:7px;border-radius:50%;background:#78c59c;margin-top:7px;box-shadow:0 0 0 3px #78c59c28}
.main-wrap{min-width:0}.topbar{height:62px;padding:0 clamp(16px,4vw,42px);display:flex;align-items:center;justify-content:flex-end;gap:16px;border-bottom:1px solid #dfe5e0;background:#f7f8f5;font-size:13px;color:var(--muted)}.topbar a{font-weight:700}.topbar .environment-dot{margin:0 5px 1px 0}
main{width:min(100%,1280px);padding:34px clamp(16px,4vw,42px) 56px}
.hero{background:none;color:var(--ink);padding:0;box-shadow:none;border-radius:0}.hero p{margin:0;color:var(--muted);font-size:15px}.eyebrow,.section-index{color:#526e63;font-size:11px;font-weight:750;letter-spacing:.13em}.hero h1{font-size:clamp(27px,3vw,40px);margin:.17em 0 .26em;letter-spacing:-.03em}
.step-rail{display:flex;max-width:760px;margin:24px 0 18px;border-bottom:1px solid var(--line);padding-bottom:15px;gap:14px}
.step{flex:1;min-width:0;display:flex;align-items:center;gap:10px;color:var(--ink);text-decoration:none}.step>span{flex:0 0 29px;height:29px;display:grid;place-items:center;border:1px solid #afbfb6;border-radius:50%;background:#fff;color:#526b61;font-size:12px;font-weight:700}.step.stage>span{background:var(--blue);color:#fff;border-color:var(--blue);box-shadow:0 0 0 4px var(--mint)}.step small{display:block}.step b{font-size:13px}
article,details,.empty,.answer,.library-board,.search-board,.work-card{border:1px solid var(--line);border-radius:14px;background:#fff;box-shadow:0 8px 22px #11362b09}
.library-board,.search-board{padding:14px 18px}.library-board details{box-shadow:none}.drop-zone{background:#f8faf8;border-color:#a7bbb3}.drop-active{background:#e1efe7}.tag,.cite,.mode,.secondary,pre{background:#edf4ef;color:#234e42}.mode{border-color:var(--line)}.mode:has(input:checked){background:#dcebe3;border-color:#6f998a;color:#173f34}.mode input{accent-color:var(--blue)}
.source-switch .active,button{background:var(--blue);border-color:var(--blue)}.source-switch .active{color:#fff}.secondary{border-color:#9aada3}.secondary:hover{background:#e5efe8}.formats:empty{display:none}.formats{padding:0 0 12px}.formats small{font-weight:650}.samples a:hover{background:#e7f0e9}
.work-grid,.readout,.agent-layout,.data-layout{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(240px,.9fr);gap:18px;align-items:start}.work-card{padding:clamp(14px,2vw,24px);min-width:0}.work-card h2,.work-card h3{margin:.25rem 0 .45rem}.work-card p{color:var(--muted)}
.work-drop{margin-top:15px;min-height:142px;border:1px dashed #a7bbb3;border-radius:11px;background:#f8faf8;display:grid;place-items:center;text-align:center;padding:16px}.work-drop p{margin:.35rem 0}.work-icon{width:44px;height:44px;display:grid;place-items:center;border-radius:50%;background:#e3eee8;color:var(--blue)}
.work-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.work-button{display:inline-flex;align-items:center;gap:7px;justify-content:center;min-height:38px;padding:6px 14px;border:1px solid #a7bbb3;background:#fff;border-radius:8px;text-decoration:none;font-weight:700}.work-button.primary{color:#fff;background:var(--blue);border-color:var(--blue)}.work-button:hover{box-shadow:0 0 0 2px #b8d2c4}
.work-more{grid-column:1/-1}.work-links{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:9px}.work-links a{display:flex;gap:8px;align-items:center;padding:10px;border:1px solid var(--line);border-radius:9px;text-decoration:none;background:#f8faf8;font-weight:650}
.readout .answer{background:#f4faf6;border-color:#9dc3af;margin:0}.readout .answer.warning{background:#fcf8f1;border-color:#bd9869}.readout .answer.neutral{background:#f7f8f6;border-color:#b1bdb8}
.source-ref{padding:10px;background:#fafbfa;box-shadow:none}.source-ref summary{overflow-wrap:anywhere}.source-ref summary .cite{margin-right:8px}
.data-layout details{margin:0}.data-layout .cards article:first-child{background:var(--forest);color:#fff}.data-layout .cards article:first-child strong{color:#f0cd8e}.data-layout .cards article:first-child small,.data-layout .cards article:first-child p{color:#e4f0eb}
.chat-question{width:fit-content;max-width:100%;margin-left:auto;padding:8px 14px;border-radius:11px 11px 2px 11px;background:var(--blue);color:#fff!important;overflow-wrap:anywhere}
.plain-step{display:grid;grid-template-columns:29px 1fr;gap:10px;align-items:start;margin:18px 0}.plain-step>span{display:grid;place-items:center;height:29px;border:1px solid #b8cbc3;border-radius:50%;background:var(--mint);font-weight:700}.plain-step p{margin:0}
.plain-step.agent-result{grid-template-columns:minmax(0,1fr)}.agent-result p{overflow-wrap:anywhere}
:focus-visible{outline:3px solid #74a995!important;outline-offset:3px}
@media(max-width:1000px){.shell{grid-template-columns:195px minmax(0,1fr)}.work-grid,.readout,.agent-layout,.data-layout{grid-template-columns:1fr}}
@media(max-width:700px){.shell{display:block}.side{position:static;height:auto;padding:10px 14px;display:flex;flex-flow:row wrap;align-items:center;gap:4px}.side .brand{width:100%;padding:3px 2px 7px}.side .brand strong{width:auto}.side .brand small,.sidebar-note,.nav-caption{display:none}.side .nav-link{gap:5px;padding:6px 9px;font-size:13px}.side .nav-link svg{width:14px}.topbar{height:38px}.step{gap:6px}.step small{display:none}.step b{font-size:12px}.search-input label{display:none}.search-input input{flex:1;width:0}.cards{grid-template-columns:repeat(auto-fit,minmax(140px,1fr))}.work-card table{font-size:.85rem}main{padding-top:20px}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}
"""


# Structure follows the Make reference, with native app forms and truthful data.
CSS += """
.nav-advanced{margin:.75rem 0;padding:0;background:transparent;border:0;box-shadow:none}.nav-advanced summary{color:#bed7cc;padding:.45rem .75rem;font-size:.83rem}.nav-advanced .nav-link{padding-block:6px}
.step-rail{border:0;margin:26px 0 25px;padding:0;gap:15px;max-width:850px}.step:not(:last-child)::after{content:'';height:1px;flex:1;min-width:4px;background:#cbd8d2}.step.previous>span{background:var(--blue);color:white;border-color:var(--blue)}.step.previous::after{background:#92b2a6}
.workspace-caption{display:flex;justify-content:space-between;gap:1rem;align-items:start}.work-next .work-actions{display:grid}.workspace-list{margin:12px 0 0;padding:0;list-style:none}.workspace-list li{display:flex;align-items:center;gap:10px;padding:10px 0;border-top:1px solid var(--line);overflow-wrap:anywhere}.workspace-list li svg{flex:0 0 auto}.workspace-list small{margin-left:auto;white-space:nowrap}
.upload-management{margin:0 0 17px;padding:0 14px}.upload-management>summary{padding:10px 2px}.upload-management .library-board{margin-top:0;border:0;box-shadow:none;padding:0 0 .75rem}
.document-layout{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(250px,.9fr);gap:18px;align-items:start}.query-card .search-board{margin:0 0 11px;padding:0;border:0;box-shadow:none}.query-card .search-board form{padding:0 0 .75rem}.query-card .samples{margin:0 0 .6rem}.query-card .mode{font-size:.86rem}.query-card .answer{margin:10px 0 0;background:#f4faf6;border-color:#9dc3af}.query-card .answer.neutral{background:#f7f8f6;border-color:#b1bdb8}.query-card .answer.warning{background:#fcf8f1;border-color:#bd9869}.source-card{align-self:start}.source-card .source-ref{margin:0 0 .55rem}.source-card .source-ref small{display:block;margin-left:1rem}.source-card blockquote{border-left:2px solid #b8cabf;padding-left:10px}
.mfg-overview .cards article:first-child{background:#f1f7f3;color:var(--ink);border-color:#7da496}.mfg-overview .cards article:first-child strong,.mfg-overview .cards article:first-child small,.mfg-overview .cards article:first-child p{color:var(--ink)}
.formula-card{margin-top:14px;padding:18px;border-radius:11px;background:var(--forest);color:#fff}.formula-card h3{margin:0 0 8px;color:#fff}.formula-card small{color:#c3d8cf}.fraction-visual{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-top:10px}.fraction-visual b{padding:.35rem .6rem;border-radius:6px;background:#1c473d;color:#fff}.fraction-visual strong{color:#f0cd8e;font-size:1.35rem}
.metric-quality h2{margin:.25rem 0}.metric-quality details{margin:.65rem 0 0;box-shadow:none}.metric-quality .quality-tag{color:#765728;background:#f5ead7}
.agent-identity{display:flex;align-items:center;gap:10px;padding:0 0 12px;border-bottom:1px solid var(--line);margin-bottom:12px}.agent-identity>span{display:grid;place-items:center;width:36px;height:36px;background:var(--forest);color:#f0cd8e;border-radius:9px}.agent-identity small,.agent-identity strong{display:block}
.trace-list{padding:0;list-style:none}.trace-list li{padding:.55rem 0;border-bottom:1px solid var(--line);overflow-wrap:anywhere}.trace-list li::before{content:'›';margin-right:.55em;color:var(--blue);font-weight:700}.agent-composer{border-top:1px solid var(--line);margin-top:14px;padding:12px 0 .25rem}.agent-composer .search-input{border:1px solid #bdcbc5;padding:5px;border-radius:9px}.agent-composer .search-input input{border:0}.agent-composer label{font-size:.85rem}.agent-layout .work-actions{display:grid}
.data-source-note{margin:.65rem 0;padding:.55rem .85rem;border-radius:9px;background:#e9f1eb;color:#244b3d;font-weight:650}
@media(max-width:920px){.document-layout{grid-template-columns:1fr}}
@media(max-width:700px){.nav-advanced{margin:0}.nav-advanced summary{font-size:.8rem}.nav-advanced[open]{width:100%}.nav-advanced[open] .nav-link{display:inline-flex}.step-rail{margin:19px 0 16px}.step:not(:last-child)::after{display:none}.agent-composer label[for=agent-q]{display:none}}
"""

CSS += """
.case-caption{margin:0 0 .3rem;font-size:.76rem!important;font-weight:650}.document-case-card{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:3px;padding:4px;margin:0 0 14px;border-radius:9px;background:#edf2ee}.case-tab{display:inline-flex;align-items:center;justify-content:center;gap:6px;min-height:36px;padding:6px 3px;border:1px solid transparent;border-radius:7px;text-decoration:none;font-size:clamp(.72rem,1.25vw,.92rem);font-weight:700;color:#49645a;text-align:center}.case-tab:hover,.case-tab[aria-current=true]{background:#fff;border-color:#cfddd4;box-shadow:0 1px 5px #173a2c16}.case-answer[aria-current=true]{color:#215542}.case-conflict[aria-current=true]{color:#87521c}.case-tab span{flex:0 0 auto}
#api-prefs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));align-items:end;gap:14px 18px}#api-prefs .api-setting-field{display:grid;gap:5px;align-content:start;min-width:0}#api-prefs .api-setting-field span{display:block;line-height:1.35;font-weight:650;overflow-wrap:anywhere}#api-prefs .api-setting-field input{display:block;width:100%;min-width:0;margin:0;padding:.55rem .7rem}#api-prefs button{justify-self:start}
.agent-model-status{color:var(--blue);font-weight:700;margin-top:2px}.agent-tool-note{width:100%;margin-top:-.28rem}
@media(max-width:660px){#api-prefs{grid-template-columns:1fr}.case-tab{font-size:.76rem}}
"""

CSS += """
.formula-picker{border:0;margin:5px 0 0;padding:0;width:100%;min-width:0}.formula-picker legend{font-size:.83rem;font-weight:700;margin:0 0 5px}
.quality-workflow{margin:.8rem 0}.quality-cards h3{font-size:1rem;margin:.15rem 0}.quality-cards p{font-size:.9rem;margin:.3rem 0}.quality-steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:.6rem}.quality-steps details{margin:.5rem 0}.custom-metric{display:none;padding:.6rem 0}.custom-metric p{font-size:.9rem;overflow-wrap:anywhere}.formula-form:has(input[value="custom"]:checked) .custom-metric{display:block}.formula-form:has(input[value="custom"]:checked) input[name="formula"]{width:min(100%,32rem)}
.formula-tabs{display:flex;align-items:center;flex-wrap:wrap;gap:6px}
.formula-tab{position:relative;display:block;cursor:pointer}.formula-tab input{appearance:none;position:absolute;inset:0;width:100%;height:100%;min-width:0;margin:0;border:0;background:transparent;cursor:pointer}
.formula-tab span{display:block;white-space:nowrap;padding:.30rem .70rem;border-radius:999px;border:1px solid var(--line);background:#fff;font-size:.86rem;line-height:1.4}
.formula-tab:has(input:checked) span{border-color:#47836b;background:#e5f2ea}.formula-tab:has(input:disabled){opacity:.55;cursor:default}
.formula-tab:has(input:focus-visible) span{outline:2px solid #2f795d;outline-offset:2px}
.formula-form{display:block}.formula-controls{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));align-items:end;gap:10px;margin-top:14px}
.formula-controls label{display:grid;gap:3px;min-width:0}.formula-controls select{min-width:0;width:100%}.formula-denominator{display:none!important}
.formula-form:has(input[value="ratio"]:checked) .formula-denominator{display:grid!important}.mfg-search{margin-top:12px;margin-bottom:14px}.mfg-search h2{font-size:1.13rem}
"""

CSS += """
.direct-upload-ready .direct-upload-fallback,.direct-upload-ready input[type=file]{display:none}.direct-upload-ready [data-upload-open]{display:block}.work-drop .direct-upload-ready{justify-content:center;padding:.55rem 0}
"""

CSS += """
.process-flow{margin:14px 0;padding:.68rem .88rem;box-shadow:none;background:#f8faf8;border-color:#d9e1dc}.process-flow summary{color:#214b3e;font-size:.85rem}.process-flow summary span{margin-right:.75em}.process-flow summary b{font-weight:500;color:#456458}.process-flow p{margin:.48rem 0 0;color:var(--muted);font-size:.87rem}
"""

CSS += """
#choose-tables{align-items:flex-start;flex-direction:column}
#choose-tables .library-list{width:100%;padding-left:0}
#choose-tables label{display:inline-flex;align-items:center;gap:.55rem;overflow-wrap:anywhere}
#choose-tables input[type=checkbox]{min-width:auto;flex:none}
#choose-tables li{flex-wrap:wrap}
"""

# Keep the mobile document viewport fixed to the device width. Wide data
# previews scroll in their existing wrappers, not across the whole page.
CSS += """
@media(max-width:730px){
  .shell{display:block}
  .side{position:static;height:auto;overflow:visible;padding:10px 12px;gap:4px}
  .side .nav-link,.nav-advanced summary{min-height:44px;display:inline-flex;align-items:center}
  .nav-advanced{margin:0}
  .nav-advanced[open]{width:100%}
  .nav-advanced summary{display:list-item;align-content:center}
  .topbar{height:auto;min-height:38px;flex-wrap:wrap;gap:4px 12px;padding-block:5px}
  main{min-width:0;overflow-wrap:anywhere}
  main :is(section,article,details,form,fieldset,label,.main-wrap,.library-list li)>*{min-width:0}
  main :is(input,select,textarea,button){max-width:100%;font-size:16px}
  main :is(input,select,textarea,button,.work-button,summary){min-height:44px}
  main :is(input[type=radio],input[type=checkbox]){min-height:0}
  main :is(form,.library-list li){flex-wrap:wrap}
  main label:has(select){max-width:100%}
  main input[type=file]{width:100%}
  main :is(pre,[style*="overflow:auto"]){max-width:100%;overflow:auto}
  .drop-zone{padding-inline:.65rem}
  .step-rail{gap:8px}
  .step{min-height:44px}
  .step small{display:none}
  .step:not(:last-child)::after{display:none}
  .formula-tab span{min-height:44px;display:flex;align-items:center;white-space:normal}
}
@media(max-width:380px){
  main{padding-inline:12px}
  .search-input{flex-wrap:wrap}
  .search-input input{width:100%;flex-basis:100%}
}
"""
