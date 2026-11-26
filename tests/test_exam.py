import asyncio,contextlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from decimal import Decimal
import main,agent_api,retrieval,extract

P=Path(__file__).resolve().parents[1]
class ExamTest(unittest.TestCase):
    def test_math(self):
        r=main.report(main.clean(P/"demo"/"production.csv"),"l1")
        self.assertEqual(r["overall"]["defect_count"],102)
        self.assertAlmostEqual(r["overall"]["weighted_defect_rate"],.034)
        self.assertAlmostEqual(r["overall"]["mean_row_defect_rate"],.0285)
        self.assertEqual(r["data_quality"]["skipped"],{"defects_exceed_output":1})
    def test_empty(self):
        self.assertEqual(main.report(main.clean(P/"demo"/"production.csv"),"NONE")["status"],"empty")
    def test_unit_and_nonfinite(self):
        self.assertEqual(main.finite("2.5",kind="rate",bare_rate_unit="percent"),Decimal(".025"))
        for v in ["inf","-1","1,2","1.2"]:
            with self.assertRaises(ValueError):
                main.finite(v,kind="rate",bare_rate_unit="fraction")
    def test_weights_not_guessed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"x.csv";p.write_text("產線,不良率\nA,2%\n")
            self.assertIsNone(main.report(main.clean(p))["overall"]["weighted_defect_rate"])
    def test_output_safe(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"x.json"
            with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main.main(["--output",str(p)]),0)
                initial=p.read_bytes()
                self.assertEqual(main.main(["--output",str(p)]),2)
                self.assertEqual(main.main(["--question","x"]),2)
            self.assertEqual(p.read_bytes(),initial)
    def test_agent_two_turns(self):
        def fixture(messages):
            if len(messages)==2:
                return {"tool_calls":[{"id":"a","type":"function","function":{"name":"production_report","arguments":'{"line":"L1"}'}}]}
            self.assertEqual(messages[-1]["tool_call_id"],"a")
            self.assertNotIn("production.csv",messages[-1]["content"])
            return {"content":"fabricated 100% which program must ignore"}
        rr=agent_api.run("L1",main.clean(P/"demo"/"production.csv"),main.report,chat=fixture)
        self.assertEqual(rr["overall"]["weighted_defect_rate"],.034)
    def test_agent_reject_unknown_tool(self):
        with self.assertRaisesRegex(ValueError,"unsupported_or_duplicate_tool"):
            agent_api.run("x",{},main.report,chat=lambda _:{"tool_calls":[{"id":"a","type":"function","function":{"name":"shell","arguments":"{}"}}]})
    def test_agent_no_tool(self):
        with self.assertRaisesRegex(ValueError,"no_tool_evidence"):
            agent_api.run("x",{},main.report,chat=lambda _:{"content":"x"})
    def test_retrieval_id_and_no_match(self):
        docs=retrieval.load_docs(P/"demo"/"docs")
        self.assertEqual(retrieval.retrieve(docs,"E-402")[0]["source"],"DEVICE-DEMO.md")
        self.assertTrue(all(x["source"]=="DEVICE-DEMO.md" for x in retrieval.retrieve(docs,"DEMO-100 E-402")))
        self.assertEqual(retrieval.retrieve(docs,"SOP-999"),[])
    def test_hybrid(self):
        docs=retrieval.load_docs(P/"demo"/"docs")
        self.assertEqual(retrieval.retrieve(docs,"E-402",embed=lambda texts:[[1.,0.]]*len(texts))[0]["source"],"DEVICE-DEMO.md")
    def test_citations(self):
        docs=retrieval.load_docs(P/"demo"/"docs")
        d=next(x for x in docs if "DEVICE" in x["source"])
        valid=lambda q,c:{"answer":"4小時","citations":[{"chunk_id":c[0]["chunk_id"],"quote":"連續 4 小時"}]}
        self.assertEqual(retrieval.generate_answer("多久",[d],responder=valid)["status"],"ok")
        with self.assertRaisesRegex(ValueError,"citation_does_not_match"):
            retrieval.generate_answer("多久",[d],responder=lambda q,c:{"answer":"9","citations":[{"chunk_id":c[0]["chunk_id"],"quote":"9小時"}]})
        self.assertEqual(retrieval.generate_answer("沒有",[],responder=lambda *_:self.fail("unexpected network"))["status"],"not_found")
    def test_extract_missing_ambiguity(self):
        e=extract.extract(["狀態：OK\n設備：A","設備：B"],["狀態","設備","負責人"])
        self.assertEqual(e["fields"]["狀態"],"OK");self.assertIsNone(e["fields"]["設備"])
        self.assertEqual(e["missing"],["負責人"]);self.assertEqual(e["ambiguous"],["設備"])
    @patch.dict("os.environ",{"EXAM_API_HOST":"approved.example"},clear=True)
    def test_wrong_route_before_request(self):
        with self.assertRaisesRegex(ValueError,"endpoint_must_match"):
            agent_api.call_json("https://other.example/v1/chat/completions",{},required_route="/chat/completions",token="sample")

class OptionalMacTest(unittest.TestCase):
    def test_excel_actual(self):
        try: from openpyxl import Workbook
        except ImportError: self.skipTest("optional openpyxl not installed")
        with tempfile.TemporaryDirectory() as d:
            wb=Workbook();w=wb.active
            w.append(["line_id","output_qty","defect_count"]);w.append(["L1",800,20])
            file=Path(d)/"test.xlsx";wb.save(file);wb.close()
            self.assertEqual(main.report(main.clean(file),"L1")["overall"]["weighted_defect_rate"],.025)
    def test_pdf_actual(self):
        try:
            from pypdf import PdfWriter
            from pypdf.generic import NameObject, DictionaryObject, DecodedStreamObject
        except ImportError: self.skipTest("optional pypdf not installed")
        with tempfile.TemporaryDirectory() as d:
            w=PdfWriter();p=w.add_blank_page(width=250,height=100)
            font=DictionaryObject({NameObject("/Type"):NameObject("/Font"),NameObject("/Subtype"):NameObject("/Type1"),NameObject("/BaseFont"):NameObject("/Helvetica")})
            p[NameObject("/Resources")]=DictionaryObject({NameObject("/Font"):DictionaryObject({NameObject("/F1"):w._add_object(font)})})
            text=DecodedStreamObject();text.set_data(b"BT /F1 12 Tf 20 45 Td (Status: ready) Tj ET")
            p[NameObject("/Contents")]=w._add_object(text)
            p2=w.add_blank_page(width=250,height=100)
            p2[NameObject("/Resources")]=p[NameObject("/Resources")]
            content2=DecodedStreamObject();content2.set_data(b"BT /F1 12 Tf 20 45 Td (ALARM-931: Confirm power) Tj ET")
            p2[NameObject("/Contents")]=w._add_object(content2)
            file=Path(d)/"test.pdf";w.write(file);w.close()
            self.assertEqual(extract.extract(extract.pages(file),["Status"])["fields"],{"Status":"ready"})
            chunks=retrieval.load_docs(Path(d))
            hit=retrieval.retrieve(chunks,"ALARM-931")
            self.assertEqual((hit[0]["source"],hit[0]["page"],hit[0]["quote"]),("test.pdf",2,"ALARM-931: Confirm power"))
            self.assertEqual(retrieval.retrieve(chunks,"ALARM-999"),[])
            found=next(x for x in chunks if x["chunk_id"]==hit[0]["chunk_id"])
            verdict=retrieval.generate_answer("ALARM-931",[found],responder=lambda *_:{"answer":"Confirm power","citations":[{"chunk_id":found["chunk_id"],"quote":"Confirm power"}]})
            self.assertEqual(verdict["citations"][0]["page"],2)
    def test_scanned_pdf_is_clear_error(self):
        try: from pypdf import PdfWriter
        except ImportError: self.skipTest("optional pypdf not installed")
        with tempfile.TemporaryDirectory() as d:
            w=PdfWriter();w.add_blank_page(width=250,height=100);w.write(Path(d)/"scan.pdf");w.close()
            with self.assertRaisesRegex(ValueError,"no_extractable_pdf_text_ocr_required"):
                retrieval.load_docs(Path(d))
    def test_fastapi_asgi(self):
        try:
            import httpx
            from api_fastapi import app
        except ImportError: self.skipTest("optional FastAPI/httpx not installed")
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test.invalid") as c:
                self.assertEqual((await c.get("/health")).status_code,200)
                page=await c.get("/?sample=csv")
                self.assertEqual(page.status_code,200)
                self.assertIn("text/html",page.headers["content-type"])
                self.assertIn("3.40%", page.text)
                self.assertIn("2.85%", page.text)
                self.assertIn("排除 1 筆", page.text)
                self.assertIn("<td>6</td><td>L2</td>", page.text)
                self.assertIn("產量 100 ／不良數 120", page.text)
                self.assertIn("不良數大於產量", page.text)
                self.assertNotIn("defects_exceed_output", page.text)
                self.assertIn("查無有效資料", (await c.get("/",params={"line":"L9","sample":"csv"})).text)
                malicious='<script>alert(1)</script>'
                page=await c.get("/",params={"line":malicious,"sample":"csv"})
                self.assertNotIn(malicious.upper(),page.text)
                self.assertIn("&lt;SCRIPT&gt;",page.text)
                self.assertEqual((await c.get("/docs")).status_code,200)
                result=await c.post("/report",json={"line":"L1"})
                self.assertEqual(result.status_code,200)
                self.assertEqual(result.json()["overall"]["weighted_defect_rate"],.034)
                self.assertEqual((await c.post("/report",json={"line":"UNKNOWN"})).status_code,404)
                self.assertEqual((await c.post("/report",json={"path":"/etc/passwd"})).status_code,422)
        asyncio.run(check())

    def test_studio_all_routes(self):
        import httpx
        from api_fastapi import app
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test.invalid") as c:
                response=await c.get("/knowledge?source=demo")
                self.assertIn("混合檢索｜BM25 + 本機字元向量 + RRF",response.text)
                self.assertIn("DEVICE-DEMO.md",response.text)
                self.assertIn("30 mV",response.text)
                self.assertIn("本機字元向量",response.text)
                self.assertIn("只用 BM25",response.text)
                alt=await c.get("/knowledge",params={"source":"demo","mode":"bm25"})
                self.assertIn("關鍵字檢索｜BM25",alt.text)
                self.assertIn("查無可引用資料",(await c.get("/knowledge",params={"source":"demo","q":"DEMO-100 SOP-999"})).text)
                pdf=await c.get("/knowledge",params={"source":"demo","q":"PDF-200 ALARM-931"})
                self.assertIn("第 2 頁",pdf.text)
                self.assertIn("Confirm power",pdf.text)
                pdf_fields=await c.get("/extract",params={"file":"pdf","fields":"Asset,Status,Owner"})
                self.assertIn("PDF-200",pdf_fields.text)
                self.assertIn("Ready",pdf_fields.text)
                self.assertIn("文件未提供",pdf_fields.text)
                self.assertEqual((await c.get("/extract",params={"file":"text","fields":","})).status_code,422)
                self.assertIn("待確認",(await c.get("/extract?file=text&source=demo")).text)
                multi=await c.get("/extract/specs")
                self.assertEqual(multi.status_code,200)
                self.assertIn("成功擷取 2 筆；1 筆待人工核對",multi.text)
                self.assertIn("DEMO-A",multi.text)
                self.assertIn("DEMO-B",multi.text)
                self.assertIn("未提供備註",multi.text)
                import spec_extract
                data=spec_extract.parse(extract.pages(P/"demo"/"specs"/"products.pdf"))
                self.assertEqual([x.evidence.page for x in data.items],[1,2])
                self.assertEqual(data.items[0].compliance,["CE","RoHS"])
                self.assertIsNone(data.items[1].notes)
                self.assertEqual(data.unresolved[0].page,2)
                tool=await c.get("/agent?line=L1")
                self.assertIn("3.40%",tool.text)
                self.assertIn("production_report",tool.text)
                self.assertIn("用模擬方式",tool.text)
                self.assertIn("查無有效資料",(await c.get("/agent",params={"line":"L9"})).text)
                page=await c.get("/integration?line=L1")
                self.assertIn("Pydantic",page.text)
                self.assertIn("<details>",page.text)
                self.assertEqual((await c.get("/report.json")).json()["overall"]["weighted_defect_rate"],.034)
                self.assertIn("/report",(await c.get("/openapi.json")).json()["paths"])
        asyncio.run(check())

if __name__=="__main__": unittest.main()
