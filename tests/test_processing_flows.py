from unittest import TestCase
from fastapi.testclient import TestClient
from api_fastapi import app

class ProcessingFlows(TestCase):
    def test_visible_workflows_are_route_specific(self):
        checks={"/workspace":"掃描 PDF 需要先做 OCR","/knowledge":"查詢時才按所選模式排名",
                "/analysis":"表格讀成欄與列，不做文件索引","/":"查產線",
                "/extract":"Excel 可選工作表與欄位",
                "/agent":"所選模型只影響文件搜尋",
                "/integration":"儲存設定不會連外","/models":"試聊與文件問答分開","/guide":"兩種來源分開"}
        with TestClient(app) as c:
            for route,t in checks.items():
                with self.subTest(route=route):
                    r=c.get(route)
                    self.assertEqual(r.status_code,200)
                    self.assertIn('class="process-flow"',r.text)
                    self.assertIn(t,r.text)
            self.assertNotIn(">上傳 Excel</a>",c.get("/agent").text)
