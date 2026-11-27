import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {accessSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const evidence = resolve(process.env.VERIFY_EVIDENCE || 'verification-evidence');
const temp = mkdtempSync(join(tmpdir(), 'demo-check-'));
const chrome = [process.env.CHROME_BIN, '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome', '/usr/bin/chromium'].filter(Boolean).find(x => { try { accessSync(x); return true; } catch { return false; } });
mkdirSync(evidence, {recursive:true});
const writes = {};
async function until(fn, label) {
  let error;
  for (let i=0; i<160; i++) {
    try { const value=await fn(); if(value) return value; } catch(e) { error=e; }
    await delay(100);
  }
  throw new Error('Timed out: '+label+(error ? ' '+error.message : ''));
}
let app, browser, sock;
let browserLog='';
try {
  assert(chrome && typeof WebSocket === 'function', 'Need Chrome and Node 22+');
  let log='';
  let base=process.env.VERIFY_BASE_URL;
  if(!base) {
  app=spawn(process.env.DEMO_PYTHON || 'python3',['-B','-m','uvicorn','api_fastapi:app','--host','127.0.0.1','--port','0'],{
    cwd:root,env:{PATH:process.env.PATH,HOME:temp,PYTHONNOUSERSITE:'1'},stdio:['ignore','pipe','pipe']
  });
  for(const stream of [app.stdout,app.stderr]) stream.on('data',chunk=>log+=chunk);
  app.on('error',e=>log+=e.message);
  base=await until(()=>log.match(/Uvicorn running on (http:\/\/127\.0\.0\.1:\d+)/)?.[1], 'app startup');
  }
  assert.match(base,/^https?:\/\/127\.0\.0\.1:\d+$/,'Only inspect a loopback verification target');
  const health=await (await fetch(base+'/health')).json();
  assert.equal(health.mode,'local_offline');
  browser=spawn(chrome,['--headless','--no-first-run','--no-default-browser-check','--disable-background-networking',
    '--disable-sync','--disable-dev-shm-usage','--remote-debugging-port=0','--remote-debugging-address=127.0.0.1',
    '--user-data-dir='+join(temp,'profile'),'--window-size=1365,960','about:blank'],{stdio:['ignore','ignore','pipe']});
  browser.stderr.on('data',chunk=>browserLog=(browserLog+chunk).slice(-12000));
  // Keep the independent browser check fail-closed, but surface what failed
  // rather than timing out on a file after Chrome has already exited.
  const stopped=new Promise((_,reject)=>{
    browser.once('error',reject);
    browser.once('exit',(code,signal)=>reject(new Error('Chrome exited: '+(signal||code)+' '+browserLog.trim())));
  });
  const devPort=await Promise.race([until(()=>readFileSync(join(temp,'profile','DevToolsActivePort'),'utf8').split('\n')[0],'Chrome startup'),stopped]);
  const tabs=await until(async ()=>(await (await fetch('http://127.0.0.1:'+devPort+'/json/list')).json()).find(x=>x.type==='page'),'Chrome tab');
  sock=new WebSocket(tabs.webSocketDebuggerUrl);
  await until(()=>sock.readyState===WebSocket.OPEN,'browser connection');
  let seq=0;
  const pending=new Map();
  const dialogs=[];
  sock.addEventListener('message',({data})=>{
    const r=JSON.parse(data);
    if(r.method==='Page.javascriptDialogOpening') dialogs.push(r.params);
    const wait=pending.get(r.id);
    if (!wait) return;
    pending.delete(r.id); clearTimeout(wait.timer);
    if(r.error) wait.reject(new Error(JSON.stringify(r.error))); else wait.resolve(r.result);
  });
  function cmd(method, params={}) {
    return new Promise((resolve,reject)=>{
      const id=++seq;
      const timer=setTimeout(()=>{pending.delete(id); reject(new Error('CDP timeout: '+method));},8000);
      pending.set(id,{resolve,reject,timer});
      sock.send(JSON.stringify({id,method,params}));
    });
  }
  async function run(expression) {
    const r=await cmd('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
    if(r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || 'Page JavaScript failed');
    return r.result.value;
  }
  const screenshot=async name=>writeFileSync(join(evidence,name+'.png'),
    Buffer.from((await cmd('Page.captureScreenshot',{format:'png'})).data,'base64'));
  await cmd('Page.navigate',{url:base+'/knowledge?source=local&mode=bm25'});
  await until(()=>run("document.readyState==='complete' && location.pathname==='/knowledge' && !!document.querySelector('#local-upload button')"),'upload page');
  await until(async ()=>{
    const file=(await cmd('Runtime.evaluate',{expression:"document.querySelector('#doc-files')"})).result.objectId;
    if(!file) return false;
    await cmd('DOM.setFileInputFiles',{objectId:file,files:[join(root,'demo/docs/PDF-200.pdf')]});
    return run("document.querySelector('#doc-files').files.length===1");
  },'stable browser file input');
  await run("document.querySelector('#local-upload button').click()");
  await until(()=>run("document.querySelector('.library-list')?.textContent.includes('PDF-200.pdf')"),'PDF indexed');
  writes.upload='PDF-200.pdf indexed';

  async function query(q) {
    await run(`document.querySelector('#query').value=${JSON.stringify(q)}; document.querySelector('#knowledge-search button').click()`);
    await until(()=>run(`new URL(location.href).searchParams.get('q')===${JSON.stringify(q)} && !!document.querySelector('#search-results section.answer h2')`),'query result');
    return run("({answer:document.querySelector('#search-results section.answer h2').textContent, sources:document.querySelector('#document-sources').innerText, count:document.querySelectorAll('#document-sources .source-ref').length})");
  }
  const found=await query('PDF-200 ALARM-931');
  assert.equal(found.answer,'找到可引用片段');
  assert.match(found.sources,/PDF-200\.pdf/);
  assert(found.count>0);
  await run("document.querySelector('#document-sources .source-ref').open=true");
  assert.match(await run("document.querySelector('#document-sources').innerText"),/第 2 頁/);
  await screenshot('answer-with-source');
  writes.answer={status:found.answer,source:'PDF-200.pdf',page:2};
  const none=await query('NOT-IN-SOURCE-8874');
  assert.equal(none.answer,'查無可引用資料');
  assert.equal(none.count,0);
  await screenshot('no-supported-answer');
  writes.noAnswer={status:none.answer,sources:0};
  // User-reported grouped amount result must not render in the 29px step-number column.
  for (const width of [1365,390]) {
    await cmd('Emulation.setDeviceMetricsOverride',{width,height:850,deviceScaleFactor:1,mobile:width<600});
    const amountURL=base+'/agent?source=demo&model=bm25&q='+encodeURIComponent('加總 金額');
    await cmd('Page.navigate',{url:amountURL});
    await until(()=>run("document.readyState==='complete' && !!document.querySelector('.agent-layout .plain-step p')"),'grouped amount result');
    const dims=await run(`(() => {
      const step=document.querySelector('.agent-layout .plain-step');
      const text=step.querySelector('p');
      return {width:step.getBoundingClientRect().width,textWidth:text.getBoundingClientRect().width,result:text.textContent};
    })()`);
    assert(dims.result.includes('1550') && dims.result.includes('TWD'),'query must show the expected result');
    assert(dims.textWidth>=dims.width*.65 && dims.textWidth>=175,`Agent answer too narrow at ${width}px: ${dims.textWidth}px out of ${dims.width}px`);
  }
  writes.agentAmountLayout='Grouped monetary answer uses the result pane at 1365 and 390px';
  const mobile = [];
  const mobileRoutes = ['/workspace','/knowledge?source=local&mode=bm25','/analysis','/agent','/','/extract','/models','/integration','/guide'];
  for (const width of [320,390,430]) {
    await cmd('Emulation.setDeviceMetricsOverride',{width,height:850,deviceScaleFactor:1,mobile:true});
    await cmd('Emulation.setTouchEmulationEnabled',{enabled:true});
    for (const route of mobileRoutes) {
      const expected = new URL(route,base);
      await cmd('Page.navigate',{url:expected.href});
      await until(()=>run(`document.readyState==='complete' && location.href===${JSON.stringify(expected.href)} && !!document.querySelector('main h1')`),route);
      const state=await run(`(() => {
        const root=document.documentElement;
        const nav=[...document.querySelectorAll('.side > a.nav-link, .side .nav-advanced > summary')];
        return {viewport:root.clientWidth, width:root.scrollWidth,
          forms:[...document.querySelectorAll('main form,main input:not([type=hidden]),main select,main button')].filter(el=>el.getClientRects().length).map(el=>{
            const box=el.getBoundingClientRect();return {name:el.tagName+'#'+el.id,left:box.left,right:box.right};
          }).filter(el=>el.left < -1 || el.right>root.clientWidth+1),
          nav:nav.map(el=>[Math.round(el.getBoundingClientRect().height),el.getBoundingClientRect().right]),
          overflowing:[...document.querySelectorAll('main *')].filter(el=>el.getBoundingClientRect().right>root.clientWidth+1 && !el.closest('table,pre')).slice(0,8).map(el=>el.tagName+'.'+el.className)};
      })()`);
      mobile.push({route, requested:width, ...state});
    }
  }
  writes.mobile=mobile;
  assert.deepEqual(mobile.filter(r=>r.viewport!==r.width || r.viewport!==r.requested || r.forms.length || r.nav.some(([height,right])=>height<44 || right>r.viewport+1))
    .map(({route,viewport,width,overflowing,forms,nav})=>({route,viewport,width,overflowing,forms,nav})), [], 'Mobile layout must fit and primary navigation needs 44px touch targets');
  // Use actual emulated touch events, not programmatic clicks, for mobile controls.
  await cmd('Page.enable');
  await cmd('Emulation.setDeviceMetricsOverride',{width:320,height:850,deviceScaleFactor:1,mobile:true});
  await cmd('Page.navigate',{url:base+'/knowledge?source=local&mode=bm25'});
  await until(()=>run("document.readyState==='complete' && !!document.querySelector('[data-delete-doc]')"),'mobile library contains PDF');
  async function tap(selector) {
    const pos=await run(`(() => {const el=document.querySelector(${JSON.stringify(selector)}); if(!el) return null;
      el.scrollIntoView({block:'center',inline:'nearest'});
      const r=el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2,width:r.width,height:r.height};})()`);
    assert(pos && pos.width>0 && pos.height>=44, 'Expected visible 44px touch target: '+selector);
    assert(pos.x>0 && pos.x<320 && pos.y>0 && pos.y<850,'Touch target is on screen: '+selector);
    await cmd('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:pos.x,y:pos.y}]});
    await cmd('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  }
  await tap('.upload-management > summary');
  const file=(await cmd('Runtime.evaluate',{expression:"document.querySelector('#doc-files')"})).result.objectId;
  await cmd('DOM.setFileInputFiles',{objectId:file,files:[join(root,'demo/docs/DEVICE-DEMO.md'),join(root,'demo/docs/HANDOFF-DAY.md')]});
  await tap('#local-upload button');
  await until(()=>run("document.querySelector('.library-list')?.textContent.includes('HANDOFF-DAY.md') && document.querySelector('.library-list')?.textContent.includes('DEVICE-DEMO.md')"),'mobile multi-file upload');
  async function confirmTap(selector,accept,pattern) {
    const count=dialogs.length;
    const touched=tap(selector);
    const dialog=await until(()=>dialogs[count],'mobile confirmation');
    assert.match(dialog.message,pattern);
    await cmd('Page.handleJavaScriptDialog',{accept});
    await touched;
  }
  await tap('.upload-management > summary');
  await confirmTap('[data-delete-doc="DEVICE-DEMO.md"]',true,/確定移除/);
  await until(()=>run("!document.querySelector('[data-delete-doc=\"DEVICE-DEMO.md\"]') && !!document.querySelector('[data-delete-doc=\"HANDOFF-DAY.md\"]')"),'mobile individual removal');
  await tap('.upload-management > summary');
  await confirmTap('[data-delete-doc=""]',false,/確定清除全部/);
  assert(await run("!!document.querySelector('[data-delete-doc=\"HANDOFF-DAY.md\"]')"),'cancel preserves uploaded docs');
  await confirmTap('[data-delete-doc=""]',true,/確定清除全部/);
  await until(()=>run("document.querySelector('.library-board')?.innerText.includes('沒有上傳的文件')"),'mobile confirmed reset');
  writes.mobileUpload='320px: multi-file upload, individual removal, cancel and confirm reset passed';
  if(!process.env.VERIFY_BASE_URL) {
    await cmd('Page.navigate',{url:base+'/agent?source=demo&q=PDF-200+ALARM-931'});
    await until(()=>run("document.readyState==='complete' && !!document.querySelector('[data-chat-switch]')"),'offline model controls');
    const modelUI=await run(`(() => {
      const form=document.querySelector('[data-chat-switch]');
      return {disabled:form.querySelector('[value="local:qwen"]').disabled,
        submit:form.querySelector('button').disabled,noModel:form.querySelector('[data-generated-chat]').textContent,
        actual:form.querySelector('[data-used-chat]').textContent,
        retrieval:document.querySelector('.plain-step')?.textContent.includes('查詢結果（非模型生成）')};})()`);
    assert.deepEqual(modelUI,{disabled:true,submit:true,noModel:'沒有可用模型，無法生成回答',
      actual:'本次實際使用：尚未生成',retrieval:true});
    writes.offlineModel='Agent disables unavailable chat and separately presents non-generated retrieval';
  }
  writeFileSync(join(evidence,'report.json'),JSON.stringify({status:'pass',...writes},null,2)+'\n');
  console.log('DOCUMENT_BROWSER_VERIFICATION_PASS');
} catch(e) {
  if(browserLog) writeFileSync(join(evidence,'chrome-stderr.log'),browserLog);
  writeFileSync(join(evidence,'report.json'),JSON.stringify({status:'fail',...writes,error:e.message},null,2)+'\n');
  throw e;
} finally {
  sock?.close();
  browser?.kill();
  app?.kill();
  await delay(400);
  rmSync(temp,{recursive:true,force:true,maxRetries:3});
}
