from unittest import TestCase
from fastapi.testclient import TestClient
from api_fastapi import app

class Presentation(TestCase):
    def test_blank_analysis_does_not_use_sample_or_results(self):
        with TestClient(app) as c:
            h=c.get("/analysis").text
            self.assertIn("尚未選擇資料",h)
            self.assertNotIn("下載分析 JSON",h)
            self.assertNotIn("1550",h)
            example=c.get("/analysis?sample=finance").text
            self.assertIn("內建示範 · 金融收支",example)
            self.assertIn("1550",example)
            uploaded=c.post("/analysis/file",headers={"X-Demo-Local":"1","X-Demo-Filename":"table.csv"},content=b"label,total\nA,7123\n")
            self.assertEqual(uploaded.status_code,200)
            waiting=c.get("/analysis?sample=local").text
            self.assertIn("table.csv",waiting)
            self.assertIn('id="universal-result"></div>',waiting)
            self.assertNotIn("下載分析 JSON",waiting)
            calculated=c.get("/analysis?sample=local&value=total").text
            self.assertIn("7123",calculated)
    def test_follows_four_main_sections_and_side_by_side_evidence(self):
        with TestClient(app) as c:
            home=c.get("/workspace").text
            self.assertIn('class="nav-advanced"',home)
            self.assertIn('class="workspace-readiness"',home)
            docs=c.get("/knowledge?source=demo&q=PDF-200+ALARM-931").text
            self.assertIn('class="document-layout"',docs)
            self.assertIn('id="document-sources"',docs)
            self.assertIn("第 2 頁",docs)
            manufacturing=c.get("/?sample=csv&line=L1").text
            self.assertIn('class="fraction-visual"',manufacturing)
            self.assertIn("3,000",manufacturing)
            agent=c.get("/agent?q=DEMO-100+老化要做幾小時&source=demo").text
            self.assertIn('class="agent-identity"',agent)
            self.assertIn('class="trace-list"',agent)
            self.assertIn("4 小時",agent)

    def test_document_and_manufacturing_default_to_no_demo(self):
        with TestClient(app) as c:
            docs=c.get("/knowledge").text
            self.assertIn("我的上傳文件",docs)
            self.assertNotIn("30 mV",docs)
            self.assertIn("請輸入問題",docs)
            mfg=c.get("/").text
            self.assertIn("尚未上傳表格",mfg)
            self.assertNotIn("3.40%",mfg)
            r=c.post("/manufacturing/file",headers={"X-Demo-Local":"1","X-Demo-Filename":"sample.csv"},content=b"line_id,output_qty,defect_count\nM6,300,15\n")
            self.assertEqual(200,r.status_code)
            self.assertNotIn("5.00%",c.get("/?sample=local").text)
            self.assertIn("5.00%",c.get("/?sample=local&line=M6").text)
