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
    '--user-data-dir='+join(temp,'profile'),'--window-size=1365,960','about:blank'],{stdio:'ignore'});
  browser.on('error',e=>log+=e.message);
  const devPort=await until(()=>readFileSync(join(temp,'profile','DevToolsActivePort'),'utf8').split('\n')[0],'Chrome startup');
  const tabs=await until(async ()=>(await (await fetch('http://127.0.0.1:'+devPort+'/json/list')).json()).find(x=>x.type==='page'),'Chrome tab');
  sock=new WebSocket(tabs.webSocketDebuggerUrl);
  await until(()=>sock.readyState===WebSocket.OPEN,'browser connection');
  let seq=0;
  const pending=new Map();
  sock.addEventListener('message',({data})=>{
    const r=JSON.parse(data); const wait=pending.get(r.id);
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
  await until(()=>run("!!document.querySelector('#local-upload button')"),'upload page');
  const doc=(await cmd('DOM.getDocument')).root.nodeId;
  const file=(await cmd('DOM.querySelector',{nodeId:doc,selector:'#doc-files'})).nodeId;
  assert(file);
  await cmd('DOM.setFileInputFiles',{nodeId:file,files:[join(root,'demo/docs/PDF-200.pdf')]});
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
  writeFileSync(join(evidence,'report.json'),JSON.stringify({status:'pass',...writes},null,2)+'\n');
  console.log('DOCUMENT_BROWSER_VERIFICATION_PASS');
} catch(e) {
  writeFileSync(join(evidence,'report.json'),JSON.stringify({status:'fail',...writes,error:e.message},null,2)+'\n');
  throw e;
} finally {
  sock?.close();
  browser?.kill();
  app?.kill();
  await delay(400);
  rmSync(temp,{recursive:true,force:true,maxRetries:3});
}
