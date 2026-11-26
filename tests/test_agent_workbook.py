from io import BytesIO
from unittest import TestCase
from fastapi.testclient import TestClient
from openpyxl import Workbook
from api_fastapi import app

class WorkspaceRouting(TestCase):
    def test_real_worksheet_selection_and_cells(self):
        w=Workbook(); w.active.title="舊"; w.active.append(["設備","金額"]); w.active.append(["X",1000])
        a=w.create_sheet("新"); a.append(["設備","金額"]); a.append(["Y",0]); a.append(["Z",None])
        b=BytesIO(); w.save(b)
        with TestClient(app) as c:
            self.assertEqual(c.get("/extract/workbook").status_code,200)
            r=c.post("/extract/workbook",headers={"X-Demo-Local":"1","X-Demo-Filename":"sample.xlsx"},content=b.getvalue())
            self.assertEqual(r.status_code,200)
            q=c.get("/extract/workbook",params=[("sheet","新"),("field","金額"),("download","true")])
            self.assertEqual(q.status_code,200)
            self.assertEqual(q.json()["rows"],[{"row":2,"cells":{"金額":{"value":0,"cell":"B2"}}},{"row":3,"cells":{"金額":{"value":None,"cell":"B3"}}}])
            q=c.get("/agent",params={"q":"擷取 金額","sheet":"新"})
            self.assertIn("B2",q.text)
            self.assertNotIn("1000",q.text.split("查詢依據")[-1])
    def test_agent_routes_and_does_not_answer_unsupported_question(self):
        with TestClient(app) as c:
            for question,expected in [("L1 不良率","3.40%"),("PDF-200 ALARM-931","第 2 頁"),("加總 金額","1550"),("DEMO-100 交接時限","來源衝突"),("台北會下雨嗎","不支援這個問題")]:
                with self.subTest(q=question):
                    r=c.get("/agent",params={"q":question,"source":"demo"})
                    self.assertEqual(r.status_code,200)
                    self.assertIn(expected,r.text)
                    self.assertIn("查詢依據",r.text)

    def test_api_defaults_to_empty_non_manufacturing_entry_and_runs_other_domains(self):
        with TestClient(app) as c:
            h=c.get("/integration").text
            self.assertIn('id="workspace-api-form"',h)
            self.assertNotIn('name="line"',h)
            self.assertIn('value="local"',h)
            for q,tool in [("加總 金額","通用表格分析"),("PDF-200 ALARM-931","文件檢索｜BM25")]:
                r=c.get("/api/workspace/query",params={"q":q,"source":"demo"})
                self.assertEqual(r.status_code,200)
                self.assertEqual(r.json()["tool"],tool)
                self.assertTrue(r.json()["evidence"])
            r=c.get("/api/workspace/query", params={"q":"加總 金額"})
            self.assertEqual(r.json()["status"],"missing")

    def test_single_html_contains_calculated_result_no_runtime_dependencies(self):
        with TestClient(app) as c:
            r=c.get("/api/workspace/report.html",params={"q":"加總 金額","source":"demo"})
            self.assertEqual(r.status_code,200)
            self.assertIn("attachment",r.headers["content-disposition"])
            self.assertIn("1550",r.text)
            self.assertIn("查詢依據",r.text)
            self.assertNotIn("<script",r.text)
            self.assertNotIn("127.0.0.1",r.text)

    def test_uploaded_non_manufacturing_data_shared_by_chat_and_api(self):
        with TestClient(app) as c:
            payload="幣別,金額\nTWD,10\nTWD,20\nUSD,8\n".encode()
            r=c.post("/analysis/file",headers={"X-Demo-Local":"1","X-Demo-Filename":"expense.csv"},content=payload)
            self.assertEqual(r.status_code,200)
            api=c.get("/api/workspace/query",params={"q":"加總 金額"})
            self.assertEqual([(a["unit"],a["sum"]) for a in api.json()["result"]["results"]],[("TWD","30"),("USD","8")])
            chat=c.get("/agent",params={"q":"加總 金額"})
            self.assertIn("TWD 全部：30",chat.text)
            self.assertIn("USD 全部：8",chat.text)
            report=c.get("/api/workspace/report.html",params={"q":"加總 金額"})
            self.assertIn("TWD 全部：30",report.text)
