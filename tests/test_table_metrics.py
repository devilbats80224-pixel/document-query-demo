import json
from unittest import TestCase

from fastapi.testclient import TestClient
from api_fastapi import app


class TableMetrics(TestCase):
    def test_uploaded_table_formula_selection_and_real_ratio(self):
        with TestClient(app) as client:
            data=b"category,actual,target\nA,3,10\nA,7,30\nB,2,0\nC,bad,20\n"
            uploaded=client.post("/analysis/file",headers={"X-Demo-Local":"1","X-Demo-Filename":"uploaded.csv"},content=data)
            self.assertEqual(200,uploaded.status_code)
            start=client.get("/analysis").text
            self.assertIn('value="sum"',start)
            self.assertIn('value="ratio"',start)
            self.assertNotIn('分析結果</h2>',start)
            numer=client.get("/analysis",params={"metric":"average","value":"actual","group":"category","download":True}).json()
            self.assertEqual(numer["metric"],"average")
            self.assertEqual(numer["results"][0]["average"],"5.0000")
            ratio=client.get("/analysis",params={"metric":"ratio","value":"actual","denominator":"target","group":"category","download":True}).json()
            self.assertEqual([g["ratio"] for g in ratio["results"]],["0.250000",None])
            self.assertEqual(ratio["excluded"]["non_numeric"],1)
            self.assertEqual(ratio["results"][0]["numerator_sum"],"10")
            output=client.get("/analysis",params={"metric":"ratio","value":"actual","denominator":"target","group":"category"}).text
            self.assertIn("25.00%",output)
            self.assertIn("分母為 0",output)

    def test_no_false_defaults_and_one_numeric_column_no_ratio(self):
        with TestClient(app) as client:
            empty=client.get("/analysis").text
            self.assertIn("可用公式",empty)
            self.assertNotIn('分析結果</h2>',empty)
            client.post("/analysis/file",headers={"X-Demo-Local":"1","X-Demo-Filename":"uploaded.csv"},content=b"category,amount\nA,10\n")
            self.assertNotIn('name="metric" value="ratio"',client.get("/analysis").text)
            no_manufacturing_file=client.get("/").text
            self.assertIn('id="line"',no_manufacturing_file)
            self.assertIn('尚未上傳表格',no_manufacturing_file)
            self.assertNotIn('加權不良率</h3>',no_manufacturing_file)
            posted=client.post("/manufacturing/file",headers={"X-Demo-Local":"1","X-Demo-Filename":"factory.csv"},content=b"line_id,output_qty,defect_count\nA3,300,15\n")
            self.assertEqual(200,posted.status_code)
            self.assertNotIn('5.00%',client.get("/").text)
            self.assertIn('5.00%',client.get("/",params={"line":"A3"}).text)

    def test_compact_shared_formula_labels(self):
        with TestClient(app) as client:
            example=client.get("/analysis?sample=finance").text
            client.post("/analysis/file",headers={"X-Demo-Local":"1","X-Demo-Filename":"batch.csv"},content=b"group,value,target\nA,10,20\n")
            uploaded=client.get("/analysis?sample=local").text
            for page in (example,uploaded):
                self.assertIn(".formula-tabs{display:flex",page)
                self.assertIn("border-radius:999px",page)
                part=page.split('class="formula-tabs"',1)[1].split("</fieldset>",1)[0]
                self.assertNotIn("<small>",part)
                self.assertIn('value="average"',part)
                self.assertIn('value="count"',part)
