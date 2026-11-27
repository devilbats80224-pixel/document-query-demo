"""Exercise the built container via real HTTP without external services."""
import http.cookiejar
from pathlib import Path
import json
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlencode

root = 'http://127.0.0.1:8775'
http = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))

def get(url):
    with http.open(root+url,timeout=4) as r:
        return r.read().decode()

assert json.loads(get('/health')) == {'status':'ok','mode':'local_offline'}
pdf = Path('/app/demo/docs/PDF-200.pdf').read_bytes()
with http.open(Request(root+'/knowledge/files', pdf, headers={'X-Demo-Local':'1',
        'X-Demo-Filename':'PDF-200.pdf','Content-Type':'application/octet-stream'}),timeout=4) as r:
    assert json.load(r)['status']=='indexed'
def q(text):
    return get('/knowledge?'+urlencode({'source':'local','mode':'bm25','q':text}))
hit=q('PDF-200 ALARM-931')
assert '找到可引用片段' in hit and '第 2 頁' in hit and 'PDF-200.pdf' in hit
miss=q('NOT-IN-SOURCE-8874')
assert '查無可引用資料' in miss and '沒有可顯示的來源' in miss
print('ARM64_DOCKER_OFFLINE_UPLOAD_AND_RETRIEVAL_PASS')
