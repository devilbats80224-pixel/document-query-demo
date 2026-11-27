"""Exam day cases; synthetic inputs with known results and no provider calls."""
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook
from pydantic import ValidationError
from pypdf import PdfWriter

import agent_api
import extract
import main
import retrieval
import spec_extract
import studio

ROOT=Path(__file__).resolve().parents[1]

class ExamDayScenarios(unittest.TestCase):
    def test_legacy_chinese_csv_with_thousands_and_invalid_row(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"主辦給的檔案.csv"
            p.write_bytes('產線,產量,不良數\r\n甲,"1,000",24\r\n甲,500,6\r\n乙,3,4\r\n'.encode("cp950"))
            audit=main.report(main.clean(p),"甲")
            self.assertEqual(audit["overall"]["weighted_defect_rate"],.02)
            self.assertEqual(audit["data_quality"]["skipped_examples"][0]["line"],"乙")

    def test_excel_percent_only_does_not_invent_denominator(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"原資料.xlsx"
            w=Workbook()
            w.active.append(["line_id","defect_rate_pct"])
            w.active.append(["L7",2.5])
            w.active.append(["L7",4.5])
            w.save(p);w.close()
            report=main.report(main.clean(p),"L7")
            self.assertAlmostEqual(report["overall"]["mean_row_defect_rate"],.035)
            self.assertIsNone(report["overall"]["weighted_defect_rate"])

    def test_pdf_only_produces_real_structured_cli_output(self):
        design=ROOT/"demo/specs/products.pdf"
        data=subprocess.check_output([sys.executable,"-B",str(ROOT/"spec_extract.py"),str(design)])
        r=json.loads(data)
        self.assertEqual([(x["part_number"],x["evidence"]["page"]) for x in r["items"]],
                         [("DEMO-A",1),("DEMO-B",2)])
        self.assertIn("Check fan speed",r["items"][0]["evidence"]["quote"])
        self.assertIsNone(r["items"][1]["notes"])
        self.assertEqual(len(r["unresolved"]),1)

    def test_prose_conflict_and_duplicate_product_not_guessed(self):
        r=spec_extract.parse(["1. Part: D-100; Category: PSU; 類別: BBU\n2. Part: D-300; Category: PSU",
                              "1. Part: D-300; Category: BBU\n2. Part: D-500; Compliance: CE、RoHS"])
        self.assertEqual([x.part_number for x in r.items],["D-500"])
        self.assertEqual([x.page for x in r.unresolved],[1,1,2])
        with self.assertRaises(ValidationError):
            spec_extract.Evidence.model_validate({"page":"2","line":1,"quote":"X"})
        self.assertEqual(r.items[0].compliance,["CE","RoHS"])

    def test_hybrid_keeps_exact_id_and_does_not_fake_source(self):
        docs=retrieval.load_docs(ROOT/"demo/docs")
        self.assertEqual(studio.local_hybrid("DEMO-100 SOP-999",docs,"hybrid"),[])
        evidence=studio.local_hybrid("PDF-200 ALARM-931",docs,"hybrid")
        self.assertEqual(evidence[0]["page"],2)
        self.assertEqual(set(evidence[0]["channels"]),{"BM25","本機字元向量"})

    def test_scanned_document_reports_need_for_ocr(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"沒有文字層.pdf"
            w=PdfWriter();w.add_blank_page(width=300,height=100);w.write(p);w.close()
            run=subprocess.run([sys.executable,"-B",str(ROOT/"spec_extract.py"),str(p)],capture_output=True,text=True)
            self.assertEqual(run.returncode,2)
            self.assertNotIn('"items"',run.stdout)
            self.assertIn("ocr_required",run.stderr)

    def test_agent_error_never_fakes_result_and_offline_can_deliver(self):
        p=ROOT/"demo"/"production.csv"
        def lost(_):
            raise TimeoutError("simulated provider cutoff")
        with self.assertRaisesRegex(TimeoutError,"simulated"):
            agent_api.run("L1",main.clean(p),main.report,chat=lost)
        with patch("agent_api.call_json",side_effect=AssertionError("offline must not call provider")):
            done=subprocess.check_output([sys.executable,"-B",str(ROOT/"main.py"),"--data",str(p),"--line","L1"])
        self.assertEqual(json.loads(done)["overall"]["weighted_defect_rate"],.034)

    def test_agent_loop_exhausted_is_not_a_pass(self):
        p=ROOT/"demo"/"production.csv"
        def spinning(m):
            return {"tool_calls":[{"id":str(len(m)),"type":"function",
                 "function":{"name":"production_report","arguments":'{"line":"L1"}'}}]}
        with self.assertRaisesRegex(ValueError,"agent_turn_budget_exhausted"):
            agent_api.run("L1",main.clean(p),main.report,chat=spinning)

    def test_cli_bad_header_does_not_write_false_delivery(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"weird.csv"; out=Path(d)/"交件.json"
            p.write_text("line_id,weirdstuff\nL1,123\n")
            r=subprocess.run([sys.executable,"-B",str(ROOT/"main.py"),"--data",str(p),"--output",str(out)],capture_output=True,text=True)
            self.assertEqual(r.returncode,2)
            self.assertFalse(out.exists())
            self.assertIn("need_line_and_output_plus_defects_or_rate",r.stderr)

class MoreFileRoutes(unittest.TestCase):
    def test_tsv_json_and_jsonl_match_csv_real_fixtures(self):
        expected=.034
        for ext in ("tsv","xlsx","jsonl"):
            source=ROOT/"demo"/("production."+ext)
            self.assertEqual(main.report(main.clean(source),"L1")["overall"]["weighted_defect_rate"],expected)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"主辦記錄.json"
            path.write_text('[{"line_id":"L1","output_qty":500,"defect_count":17}]')
            self.assertEqual(main.report(main.clean(path),"L1")["overall"]["weighted_defect_rate"],expected)
            path.write_text('[{"line_id":"L1","output_qty":500,"output_qty":50,"defect_count":17}]')
            with self.assertRaisesRegex(ValueError,"duplicate_json_key"):
                main.clean(path)
            path.write_text('[{"line_id":"L1","nested":{"output_qty":500},"defect_count":17}]')
            with self.assertRaisesRegex(ValueError,"nested_json_requires_explicit_mapping"):
                main.clean(path)

    def test_excel_explicit_sheet_and_missing_sheet(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"workbook.xlsx"
            w=Workbook();w.active.title="說明"
            w.active.append(["僅供說明"])
            ws=w.create_sheet("數據");ws.append(["line_id","output_qty","defect_count"]);ws.append(["T",500,10])
            w.save(path);w.close()
            self.assertEqual(main.report(main.clean(path,sheet="數據"))["overall"]["weighted_defect_rate"],.02)
            with self.assertRaisesRegex(ValueError,"xlsx_sheet_not_found"):
                main.clean(path,sheet="不存在")

    def test_word_real_table_and_paragraph_with_no_invented_page(self):
        p=ROOT/"demo/docs/WORD-210.docx"
        parsed=extract.extract(extract.pages(p),["設備","狀態","聯絡人"])
        self.assertEqual(parsed["fields"],{"設備":"WORD-210","狀態":"待檢查","聯絡人":None})
        chunks=retrieval.load_docs(p.parent)
        word=studio.local_hybrid("WORD-210 EVT-221",chunks,"hybrid")[0]
        self.assertEqual(word["source"],p.name)
        self.assertIn("先關閉供電",word["quote"])
        self.assertNotIn("page",word)

    def test_html_only_visible_and_does_not_run_scripts(self):
        from document_io import read
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"頁面.html"
            p.write_text('<!doctype html><title>Secret Index</title><script>alert("DO-NOT-INDEX")</script><p>設備：BENCH-001</p><p>狀態：OK</p>')
            clean=read(p)
            self.assertNotIn("DO-NOT-INDEX",clean)
            self.assertNotIn("Secret Index",clean)
            self.assertEqual(extract.extract([clean],["設備","狀態"])["fields"],{"設備":"BENCH-001","狀態":"OK"})

    def test_docx_external_xml_decl_not_accepted(self):
        from zipfile import ZipFile
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"not-a-safe-word.docx"
            with ZipFile(p,"w") as z: z.writestr("word/document.xml",'<!DOCTYPE a><a/>')
            with self.assertRaisesRegex(ValueError,"unsupported_docx_xml"):
                extract.pages(p)

    def test_demo_can_change_real_inputs(self):
        import asyncio
        import httpx
        from api_fastapi import app
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test.invalid") as c:
                for fmt in ("csv","tsv","xlsx","jsonl"):
                    page=await c.get("/",params={"sample":fmt})
                    self.assertEqual(page.status_code,200)
                    self.assertIn(f'value="{fmt}" selected',page.text)
                    self.assertIn("3.40%",page.text)
                for route in ("/knowledge","/extract"):
                    response=await c.get(route)
                    self.assertIn("支援格式",response.text)
                    self.assertIn("Word .docx",response.text)
                word=await c.get("/extract",params={"file":"docx"})
                self.assertIn("待檢查",word.text)
                self.assertIn("WORD-210",word.text)
                self.assertNotIn("第 1 頁",word.text)
                hit=await c.get("/knowledge",params={"source":"demo","q":"WORD-210 EVT-221"})
                self.assertIn("WORD-210.docx",hit.text)
                self.assertIn("先關閉供電",hit.text)
        asyncio.run(check())

    def test_vector_mode_runs_without_bm25_and_guide_links_work(self):
        import asyncio
        import httpx
        from api_fastapi import app
        corpus=retrieval.load_docs(ROOT/"demo/docs")
        with patch("studio.retrieval.retrieve",side_effect=AssertionError("vector-only must not use BM25")):
            vector=studio.local_hybrid("PDF-200 ALARM-931",corpus,"vector")
            self.assertEqual(vector[0]["channels"],["本機字元向量"])
            self.assertEqual(vector[0]["page"],2)
            self.assertEqual(studio.local_hybrid("SOP-999",corpus,"vector"),[])
        self.assertEqual(studio.local_hybrid("PDF-200 ALARM-931",corpus,"bm25")[0]["channels"],["BM25"])
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test.invalid") as c:
                vector_ui=await c.get("/knowledge",params={"source":"demo","q":"PDF-200 ALARM-931","mode":"vector"})
                self.assertEqual(vector_ui.status_code,200)
                self.assertIn('value="vector" checked',vector_ui.text)
                self.assertIn("向量檢索｜本機字元向量 + cosine",vector_ui.text)
                self.assertIn("第 2 頁",vector_ui.text)
                self.assertIn("mode=vector",vector_ui.text)
                guide=await c.get("/guide")
                self.assertEqual(guide.status_code,200)
                self.assertIn("文件問答｜比較三種模式",guide.text)
                self.assertIn("核對資料來源與下載結果",guide.text)
                self.assertNotIn('name="mode"',(await c.get("/")).text)
        asyncio.run(check())

    def test_local_upload_lifecycle_isolation_formats_and_privacy(self):
        import asyncio
        import httpx
        from urllib.parse import quote
        from api_fastapi import app
        async def check():
            transport=httpx.ASGITransport(app=app)
            headers=lambda name:{"X-Demo-Local":"1","X-Demo-Filename":quote(name)}
            async with httpx.AsyncClient(transport=transport,base_url="http://test.invalid") as a, httpx.AsyncClient(transport=transport,base_url="http://test.invalid") as b:
                self.assertEqual((await a.post("/knowledge/files",content=b"x")).status_code,403)
                self.assertEqual((await a.delete("/knowledge/files")).status_code,403)
                body="CUSTOM-853 溫度警告：立即通報品管。\n".encode()
                up=await a.post("/knowledge/files",headers=headers("合成規範.txt"),content=body)
                self.assertEqual(up.status_code,200)
                self.assertIn("HttpOnly",up.headers["set-cookie"])
                self.assertIn("samesite=strict",up.headers["set-cookie"].lower())
                self.assertEqual(up.json()["name"],"合成規範.txt")
                self.assertEqual((await a.post("/knowledge/files",headers=headers("合成規範.txt"),content=body)).status_code,422)
                default=await a.get("/knowledge",params={"source":"local"})
                self.assertIn("請輸入問題",default.text)
                self.assertIn("合成規範.txt",default.text)
                for mode in ("vector","bm25","hybrid"):
                    query={"source":"local","q":"CUSTOM-853","mode":mode}
                    hit=await a.get("/knowledge",params=query)
                    self.assertIn("立即通報品管",hit.text)
                    self.assertEqual(hit.headers["cache-control"],"no-store")
                    self.assertNotIn("立即通報品管",(await b.get("/knowledge",params=query)).text)
                    self.assertNotIn("立即通報品管",(await a.get("/knowledge",params={**query,"source":"demo"})).text)
                self.assertEqual((await a.post("/knowledge/files",headers=headers("../bad.txt"),content=body)).status_code,422)
                self.assertEqual((await a.post("/knowledge/files",headers=headers("thing.exe"),content=body)).status_code,422)
                self.assertEqual((await a.post("/knowledge/files",headers=headers("broken.pdf"),content=body)).status_code,422)
                self.assertEqual((await a.post("/knowledge/files",headers=headers("oversize.txt"),content=b"x"*(5*1024*1024+1))).status_code,413)
                pdf=ROOT/"demo/docs/PDF-200.pdf"
                doc=ROOT/"demo/docs/WORD-210.docx"
                self.assertEqual((await a.post("/knowledge/files",headers=headers(pdf.name),content=pdf.read_bytes())).status_code,200)
                self.assertIn("第 2 頁",(await a.get("/knowledge",params={"source":"local","q":"PDF-200 ALARM-931"})).text)
                self.assertEqual((await a.post("/knowledge/files",headers=headers(doc.name),content=doc.read_bytes())).status_code,200)
                self.assertIn("先關閉供電",(await a.get("/knowledge",params={"source":"local","q":"WORD-210 EVT-221"})).text)
                self.assertEqual((await a.delete("/knowledge/files",headers={"X-Demo-Local":"1"},params={"name":"合成規範.txt"})).status_code,200)
                self.assertNotIn("立即通報品管",(await a.get("/knowledge",params={"source":"local","q":"CUSTOM-853"})).text)
                self.assertEqual((await a.delete("/knowledge/files",headers={"X-Demo-Local":"1"})).status_code,200)
                self.assertNotIn("先關閉供電",(await a.get("/knowledge",params={"source":"local","q":"WORD-210 EVT-221"})).text)
                self.assertIn("30 mV",(await a.get("/knowledge?source=demo")).text)
        asyncio.run(check())

    def test_candidate_walkthrough_cases_are_distinct_and_grounded(self):
        import asyncio,httpx
        from api_fastapi import app
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test.invalid") as c:
                samples=[
                    ("DEMO-100 老化要做幾小時","連續 4 小時"),
                    ("DEMO-100 E-402 告警條件","超過 30 mV"),
                    ("DEMO-100 E-402 告警後怎麼處理","停止出貨"),
                    ("DEMO-100 保固幾年","查無可引用資料"),
                    ("DEMO-100 交接時限","來源衝突，暫不給單一答案"),
                ]
                for q,want in samples:
                    response=await c.get("/knowledge",params={"source":"demo","q":q})
                    body=response.text.split('id="search-results"',1)[1]
                    self.assertIn(want,body)
                    self.assertIn("searchForm.addEventListener",body)
                    self.assertIn("root.replaceWith(next)",body)
                    if "交接" in q:
                        self.assertIn("15 分鐘",body)
                        self.assertIn("30 分鐘",body)
                self.assertIn("計算與驗證",(await c.get("/agent?line=L1")).text)
                for path in ("/","/knowledge","/extract","/agent","/integration","/guide"):
                    self.assertEqual((await c.get(path)).status_code,200)
        asyncio.run(check())

    def test_manufacturing_upload_and_api_download_use_same_table(self):
        import asyncio,httpx
        from api_fastapi import app
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test.invalid") as c:
                headers={"X-Demo-Local":"1","X-Demo-Filename":"sample.csv"}
                upload=await c.post("/manufacturing/file",headers=headers,content=b"line_id,output_qty,defect_count\nM6,300,15\nM6,3,4\n")
                self.assertEqual(upload.status_code,200)
                page=await c.get("/",params={"sample":"local","line":"M6"})
                self.assertIn("5.00%",page.text)
                self.assertIn("sample.csv",page.text)
                api=await c.get("/report.json",params={"line":"M6","source":"local","download":"true"})
                self.assertEqual(api.status_code,200)
                self.assertIn("attachment",api.headers["Content-Disposition"])
                self.assertEqual(api.json()["overall"]["weighted_defect_rate"],.05)
                self.assertEqual((await c.delete("/manufacturing/file",headers={"X-Demo-Local":"1"})).status_code,200)
                self.assertEqual((await c.get("/report.json",params={"line":"M6","source":"local"})).status_code,404)
        asyncio.run(check())

    def test_model_settings_persist_separate_endpoint_pairs_no_network(self):
        import asyncio,httpx
        from api_fastapi import app
        from model_settings import load
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test.invalid") as c:
                with tempfile.TemporaryDirectory() as d, patch.dict("os.environ",{"LITEON_SETTINGS_PATH":str(Path(d)/"prefs.json")}):
                    data={"embedding_url":"https://example.test/v1/embeddings","embedding_model":"vector-demo","chat_url":"https://example.test/v1/chat/completions","chat_model":"chat-demo"}
                    self.assertEqual((await c.post("/integration/settings",json=data)).status_code,403)
                    r=await c.post("/integration/settings",json=data,headers={"X-Demo-Local":"1"})
                    self.assertEqual(r.json(),{"status":"saved","provider_called":False})
                    self.assertEqual(load(),data)
                    self.assertIn("vector-demo",(await c.get("/integration")).text)
                    bad={**data,"chat_url":"https://x:y@example.test/v1/chat/completions"}
                    self.assertEqual((await c.post("/integration/settings",json=bad,headers={"X-Demo-Local":"1"})).status_code,422)
                    self.assertEqual(load(),data)
        asyncio.run(check())

    def test_data_drills_daily_and_join_with_unmatched_and_duplicates(self):
        from data_drills import by_day,left_join
        d=by_day(ROOT/"demo/production.csv","L1")
        self.assertEqual(d["top_weighted_day"]["weighted_defect_rate"],.045)
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/"a.csv",Path(d)/"b.csv"
            a.write_text("BATCH,Value\n123,5\n456,6\n")
            b.write_text("BATCH,Owner\n123,TEST\n")
            r=left_join(a,b,"BATCH")
            self.assertEqual(r["unmatched"],1)
            self.assertEqual(r["rows"][0]["lookup"],{"Owner":"TEST"})
            self.assertIsNone(r["rows"][1]["lookup"])
            with b.open("a") as f:f.write("123,OTHER\n")
            with self.assertRaisesRegex(ValueError,"lookup_key_missing_or_duplicate"):left_join(a,b,"BATCH")

    def test_general_tables_handle_finance_and_nonmanufacturing(self):
        import asyncio,httpx
        from api_fastapi import app
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test.invalid") as c:
                finance=(await c.get("/analysis?sample=finance&download=true")).json()["results"]
                self.assertIn(("TWD","商品收入","1550"),{(r["unit"],r["group"],r["sum"]) for r in finance})
                self.assertIn(("USD","運費","-20"),{(r["unit"],r["group"],r["sum"]) for r in finance})
                page=await c.get("/analysis",params={"sample":"finance","value":"金額"})
                self.assertIn("不會把 USD 和 TWD 直接相加",page.text)
                ops=(await c.get("/analysis?sample=operations&download=true")).json()
                self.assertEqual(ops["excluded"]["non_numeric"],1)
                self.assertIn(("客服","32.0000"),{(r["group"],r["average"]) for r in ops["results"]})
                payload='店別,收益\nA,"(1,250)"\nA,200\nB,20\n'.encode()
                upload=await c.post("/analysis/file",headers={"X-Demo-Local":"1","X-Demo-Filename":"store.csv"},content=payload)
                self.assertEqual(upload.status_code,200)
                r=await c.get("/analysis",params={"sample":"local","value":"收益","group":"店別","download":"true"})
                self.assertEqual(r.status_code,200)
                self.assertIn("attachment",r.headers["Content-Disposition"])
                self.assertIn(("A","-1050"),{(v["group"],v["sum"]) for v in r.json()["results"]})
                self.assertEqual((await c.delete("/analysis/file",headers={"X-Demo-Local":"1"})).status_code,200)
                self.assertIn("沒有可分析的上傳表格",(await c.get("/analysis?sample=local")).text)
        asyncio.run(check())

    def test_universal_cross_domain_sample_outputs(self):
        import asyncio,httpx
        from api_fastapi import app
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test.invalid") as c:
                for sample,g,total in (("retail","網路","2200"),("inventory","北倉","95"),("survey","網路","8")):
                    r=await c.get("/analysis",params={"sample":sample,"download":"true"})
                    self.assertEqual(r.status_code,200)
                    self.assertIn((g,total),{(v["group"],v["sum"]) for v in r.json()["results"]})
                survey=(await c.get("/analysis?sample=survey&download=true")).json()
                self.assertEqual(survey["excluded"]["non_numeric"],1)
                inventory=await c.get("/analysis",params={"sample":"inventory","value":"增減量"})
                self.assertIn("不同幣別或單位",inventory.text)
        asyncio.run(check())

    def test_local_models_configuration_does_not_fake_completion(self):
        import asyncio,httpx
        from api_fastapi import app
        async def check():
            with tempfile.TemporaryDirectory() as d,patch.dict("os.environ",{"LITEON_SETTINGS_PATH":str(Path(d)/"prefs.json")}):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test.invalid") as c:
                    headers={"X-Demo-Local":"1"}
                    self.assertEqual((await c.post("/models/chat",headers=headers,json={"question":"試聊"})).status_code,409)
                    with patch("local_models.available",return_value=True):
                        self.assertEqual((await c.post("/models/settings",headers=headers,json={"chat":"qwen","embedding":"qwen"})).status_code,200)
                    self.assertIn("Qwen3 Embedding 0.6B",(await c.get("/models")).text)
                    with patch("local_models.available",return_value=True), patch("studio.local_models.search",side_effect=ValueError("not_running")):
                        result=await c.get("/knowledge",params={"source":"demo","q":"DEMO-100"})
                        self.assertIn("本地向量模型目前無法完成查詢",result.text)
                        self.assertNotIn("找到可引用片段",result.text)
                        self.assertIn("關鍵字檢索｜BM25",(await c.get("/knowledge",params={"source":"demo","q":"DEMO-100","mode":"bm25"})).text)
        asyncio.run(check())
