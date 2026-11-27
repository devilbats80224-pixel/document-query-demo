from unittest import TestCase
from fastapi.testclient import TestClient
from api_fastapi import app

class Planning(TestCase):
    def test_first_proposes_then_uses_real_rows_and_separates_currencies(self):
        data="產品,收入,成本,幣別\nA,100,60,TWD\nA,300,180,TWD\nA,10,2,USD\nB,0,10,TWD\nA,900,,TWD\n".encode()
        with TestClient(app) as c:
            r=c.post("/analysis/file",headers={"X-Demo-Local":"1","X-Demo-Filename":"trade.csv"},content=data)
            self.assertEqual(200,r.status_code)
            page=c.get("/agent/calc",params={"q":"各產品毛利率是多少"})
            self.assertEqual(200,page.status_code)
            self.assertIn("(SUM(A)-SUM(B))/SUM(A)",page.text)
            self.assertNotIn("計算結果</h2>",page.text)
            import re
            pin=re.search(r'name="sheet_pin" value="([^"]+)"',page.text).group(1)
            out=c.get("/agent/calc",params={"run":"true","download":"true","sheet_pin":pin,
                        "q":"各產品毛利率是多少","formula":"(SUM(A)-SUM(B))/SUM(A)","group":"產品","unit":"幣別","percent":"true"})
            html = c.get("/agent/calc", params={k: v for k, v in out.request.url.params.items()
                                               if k != "download"})
            self.assertEqual(200, html.status_code, html.text)
            self.assertIn("40.00%", html.text)
            self.assertIn("80.00%", html.text)
            self.assertEqual(200,out.status_code,out.text)
            result=out.json()
            self.assertEqual([(x["group"],x["unit"],x["ratio"]) for x in result["results"]],
                             [("A","TWD","0.4"),("B","TWD",None),("A","USD","0.8")])
            self.assertEqual(result["excluded"]["invalid_numeric"],1)
            forbidden=c.get("/agent/calc",params={"run":"true","download":"true","sheet_pin":pin,"formula":"SUM(A).__class__","unit":"幣別"})
            self.assertEqual(422,forbidden.status_code)
            c.post("/analysis/file",headers={"X-Demo-Local":"1","X-Demo-Filename":"new.csv"},content=data.replace(b'100',b'200'))
            stale=c.get("/agent/calc",params={"run":"true","download":"true","sheet_pin":pin,"formula":"SUM(A)","unit":"幣別"})
            self.assertEqual(422,stale.status_code)

    def test_ambiguous_column_does_not_guess(self):
        with TestClient(app) as c:
            c.post("/analysis/file",headers={"X-Demo-Local":"1","X-Demo-Filename":"amb.csv"},
                   content="產品,含稅收入,未稅收入,成本\nA,100,90,20\n".encode())
            h=c.get("/agent/calc",params={"q":"各產品毛利率是多少"}).text
            self.assertIn("收入欄不唯一",h)
            self.assertNotIn('value="(SUM(A)-SUM(B))/SUM(A)"',h)

    def test_agent_redirects_weighted_question_without_guessing_plain_average(self):
        with TestClient(app) as c:
            c.post("/analysis/file",headers={"X-Demo-Local":"1","X-Demo-Filename":"grades.csv"},
                   content="成績,權重\n90,2\n60,1\n".encode())
            q="成績依權重加權平均"
            r=c.get("/agent",params={"q":q})
            self.assertEqual("/agent/calc",r.url.path)
            self.assertIn("SUM(A*B)/SUM(B)",r.text)
            self.assertNotIn("計算結果</h2>",r.text)
            x=c.get("/api/workspace/query",params={"q":q})
            self.assertEqual("confirm_formula",x.json()["status"])
            self.assertIsNone(x.json()["result"])

    def test_model_plan_is_validated_and_not_executed(self):
        from unittest.mock import patch
        with TestClient(app) as c, patch("local_models.available",return_value=True):
            c.post("/analysis/file",headers={"X-Demo-Local":"1","X-Demo-Filename":"store.csv"},
                   content="部門,計畫,實際,單位\nA,10,8,個\n".encode())
            with patch("local_models.calculation_proposal",return_value={"formula":"SUM(A).__class__","group":"","unit":"","percent":False}):
                page=c.get("/agent/calc",params={"q":"我要對照這份表","planner":"qwen"})
                self.assertIn("未能提供可驗證的算式",page.text)
                self.assertNotIn("計算結果</h2>",page.text)
            with patch("local_models.calculation_proposal",return_value={"formula":"SUM(B)/SUM(A)","group":"部門","unit":"","percent":True}) as m:
                h=c.get("/agent/calc",params={"q":"我要完成比率","planner":"qwen"}).text
                self.assertIn("本機模型的草案",h)
                self.assertIn("SUM(B)/SUM(A)",h)
                self.assertNotIn("計算結果</h2>",h)
                self.assertEqual(m.call_args.args[1],{"A":"計畫","B":"實際"})
