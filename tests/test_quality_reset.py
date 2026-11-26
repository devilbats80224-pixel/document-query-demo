from unittest import TestCase

from fastapi.testclient import TestClient

from api_fastapi import app


HEADERS = {"X-Demo-Local": "1"}

def upload(client, path, name, data):
    return client.post(path, headers={**HEADERS, "X-Demo-Filename": name}, content=data)


class CleaningFlow(TestCase):
    def test_quality_cards_and_reversible_filters(self):
        data = ("item,total,date,unit\n"
                "a,10,2026-01-01,kg\na,10,2026-01-01,kg\n"
                "b,,2026-01-01,kg\nc,broken,2026-13-01,kg\n"
                "d,11,2026-01-01,kg\ne,12,2026-01-01,kg\nf,12,2026-01-01,kg\n"
                "g,13,2026-01-01,kg\nh,12,2026-01-01,kg\ni,999,2026-01-01,kg\n"
                "j,4,2026-01-01,lb\n")
        with TestClient(app) as c:
            self.assertEqual(upload(c, "/analysis/file", "quality.csv", data.encode()).status_code, 200)
            q = {"sample": "local", "metric": "sum", "value": "total", "day": "date", "unit": "unit"}
            shown = c.get("/analysis", params=q).text
            for label in ("缺失值", "重複資料", "異常值與錯誤資料", "格式與單位不一致", "檢視與探索",
                          "處理缺失與異常", "去重與標準化", "驗證與監控", "1 格空白", "1 筆整列重複",
                          "1 筆疑似異常", "1 格數值格式錯誤", "日期格式錯誤 1 筆", "kg、lb"):
                self.assertIn(label, shown)
            filtered = c.get("/analysis", params={**q, "drop_dupes":True, "drop_outliers":True, "download":True}).json()
            self.assertEqual(filtered["cleaning"]["removed"], 2)
            self.assertEqual(filtered["cleaning"]["remaining"], 9)
            self.assertEqual(c.get("/analysis", params={**q,"download":True}).json()["cleaning"]["remaining"], 11)

    def test_custom_formula_and_reset_without_forgetting_the_upload(self):
        with TestClient(app) as c:
            self.assertEqual(upload(c, "/analysis/file", "scores.csv", b"score,weight\n90,2\n60,1\n").status_code, 200)
            q = {"metric":"custom","formula":"SUM(A*B)/SUM(B)","download":True}
            self.assertEqual(c.get("/analysis", params=q).json()["results"][0]["ratio"], "80")
            self.assertEqual(c.get("/analysis", params={**q,"formula":"SUM(D)"}).status_code, 422)
            html=c.get("/analysis?reset=true").text
            self.assertIn("scores.csv",html)
            self.assertNotIn("下載分析 JSON",html)
            self.assertNotIn('value="custom" checked',html)

    def test_clear_is_scoped_and_does_not_remove_separate_field_upload(self):
        with TestClient(app) as c:
            self.assertEqual(upload(c, "/analysis/file", "scores.csv", b"score\n90\n").status_code,200)
            self.assertEqual(upload(c, "/extract/file", "source.txt", b"Owner: Ada\n").status_code,200)
            self.assertIn('data-clear-uploads="workspace"',c.get("/workspace").text)
            self.assertEqual(c.delete("/workspace/uploads?scope=workspace").status_code,403)
            self.assertIn("scores.csv",c.get("/analysis").text)
            self.assertEqual(c.delete("/workspace/uploads?scope=workspace",headers=HEADERS).status_code,200)
            self.assertNotIn("scores.csv",c.get("/analysis").text)
            self.assertIn("source.txt",c.get("/extract?file=text&source=local").text)
