from unittest import TestCase
from fastapi.testclient import TestClient
from api_fastapi import app

HEADERS={"X-Demo-Local":"1"}

def upload(client, path, name, data):
    return client.post(path,headers={**HEADERS,"X-Demo-Filename":name},content=data)

class MultiSourceWorkspace(TestCase):
    def test_stacking_pins_files_and_exports_sources(self):
        with TestClient(app) as c:
            self.assertEqual(upload(c,"/analysis/file","jan.csv",b"site,total\nA,9\n").status_code,200)
            self.assertEqual(upload(c,"/analysis/file","feb.csv",b"total,site\n14,A\n").status_code,200)
            self.assertEqual(upload(c,"/analysis/file","jan.csv",b"site,total\nA,99\n").status_code,409)
            for name in ("jan.csv","feb.csv"):
                self.assertIn(name,c.get("/workspace").text)
            q=[("file","jan.csv"),("file","feb.csv")]
            run=c.get("/analysis",params=q+[("value","total"),("download","true")]).json()
            self.assertEqual(run["sources"],["jan.csv","feb.csv"])
            self.assertEqual(run["results"][0]["sum"],"23")
            reset=c.get("/analysis",params=q+[("reset","true")]).text
            for name in ("jan.csv","feb.csv"):
                self.assertIn(f'type="hidden" name="file" value="{name}"',reset)
            self.assertNotIn("下載分析 JSON",reset)
            self.assertEqual(c.delete("/analysis/file?name=jan.csv",headers=HEADERS).status_code,200)
            self.assertIn("feb.csv",c.get("/analysis").text)
            self.assertNotIn("jan.csv",c.get("/analysis").text)

    def test_mismatching_columns_never_stack(self):
        with TestClient(app) as c:
            upload(c,"/analysis/file","one.csv",b"amount\n90\n")
            upload(c,"/analysis/file","two.csv",b"units\n1\n")
            q=[("file","one.csv"),("file","two.csv"),("value","amount")]
            result=c.get("/analysis",params=q)
            self.assertIn("欄名不一致，未合併",result.text)
            self.assertNotIn("下載分析 JSON",result.text)
            self.assertEqual(c.get("/analysis",params=q+[("download","true")]).status_code,422)

    def test_docs_both_indexed_and_removal_does_not_clear_table(self):
        with TestClient(app) as c:
            upload(c,"/analysis/file","amount.csv",b"amount\n90\n")
            for n,v in (("east.txt","East shipping station charges 12 dollars."),("west.txt","West shipping station charges 20 dollars.")):
                self.assertEqual(upload(c,"/knowledge/files",n,v.encode()).status_code,200)
            docs=c.get("/knowledge",params={"q":"shipping station charges","mode":"bm25"}).text
            self.assertIn("east.txt",docs)
            self.assertIn("west.txt",docs)
            self.assertIn("清除全部已上傳文件",docs)
            self.assertIn("清除已上傳檔案",c.get("/agent").text)
            self.assertIn("清除已上傳檔案",c.get("/integration").text)
            self.assertEqual(c.delete("/knowledge/files?name=east.txt",headers=HEADERS).status_code,200)
            self.assertNotIn("east.txt",c.get("/knowledge").text)
            self.assertIn("west.txt",c.get("/knowledge").text)
            self.assertIn("amount.csv",c.get("/analysis").text)
