"""Optional offline JSON demo. Always bound to loopback, no arbitrary file input."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import argparse,json
from pathlib import Path
from main import clean,report

def handler_for(table):
    class Handler(BaseHTTPRequestHandler):
        def write_json(self,status,value):
            b=json.dumps(value,ensure_ascii=False,allow_nan=False).encode("utf-8")
            self.send_response(status);self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
        def do_GET(self):
            self.write_json(200,{"status":"ok","mode":"local_offline"}) if self.path=="/health" else self.write_json(404,{"status":"not_found"})
        def do_POST(self):
            if self.path!="/report":return self.write_json(404,{"status":"not_found"})
            try:
                n=int(self.headers.get("Content-Length","0")); self.connection.settimeout(3)
                if not 1<=n<=8192:raise ValueError()
                data=json.loads(self.rfile.read(n))
                if not isinstance(data,dict) or set(data)-{"line"}:raise ValueError()
                line=data.get("line")
                if line is not None and (not isinstance(line,str) or not line.strip() or len(line)>64):raise ValueError()
                r=report(table,line,0)
                # Keep absolute machine path out of the demo HTTP result.
                r.get("data_quality",{}).pop("source",None)
                self.write_json(200 if r["status"]=="ok" else 404,r)
            except (ValueError,TimeoutError):
                self.write_json(400,{"status":"error","error":"invalid_request"})
    return Handler

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--port",type=int,default=8765)
    p.add_argument("--data",type=Path,default=Path(__file__).parent/"demo"/"production.csv")
    a=p.parse_args()
    with HTTPServer(("127.0.0.1",a.port),handler_for(clean(a.data))) as s:
        print(f"Offline demo: http://127.0.0.1:{s.server_port}/health",flush=True)
        try:s.serve_forever()
        except KeyboardInterrupt:pass
