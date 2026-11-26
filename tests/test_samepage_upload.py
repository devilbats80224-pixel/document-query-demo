from pathlib import Path
from unittest import TestCase
from fastapi.testclient import TestClient
from api_fastapi import app

class SamePageUploads(TestCase):
    def test_overview_upload_endpoints_show_actual_readiness(self):
        with TestClient(app) as c:
            initial=c.get('/workspace').text
            self.assertIn('data-upload-scope="workspace"',initial)
            self.assertIn('type="file"',initial)
            self.assertIn('尚未上傳',initial)
            for url,name,contents in [
                 ('/knowledge/files','new.txt',b'Part: R42'),
                 ('/analysis/file','stock.csv',b'name,qty\nitem,42\n')]:
                res=c.post(url,headers={'X-Demo-Local':'1','X-Demo-Filename':name},content=contents)
                self.assertEqual(res.status_code,200,res.text)
            page=c.get('/workspace')
            self.assertEqual(page.status_code,200)
            self.assertIn('已就緒 · 2 份',page.text)
            self.assertIn('new.txt',page.text)
            self.assertIn('stock.csv',page.text)

    def test_extract_uploaded_document_and_excel_on_single_page(self):
        with TestClient(app) as c:
            page=c.get('/extract').text
            self.assertIn('data-upload-scope="extract"',page)
            self.assertIn('<option value="xlsx">Excel (.xlsx)</option>',page)
            self.assertNotIn('上傳 Excel 擷取欄位',page)
            self.assertNotIn('待確認',page)
            self.assertIn('待確認',c.get('/extract?source=demo&file=text').text)
            r=c.post('/extract/file',headers={'X-Demo-Local':'1','X-Demo-Filename':'new.html'},
                     content=b'<script>Secret: fake</script><p>Asset: R42</p>')
            self.assertEqual(r.status_code,200,r.text)
            target='/extract?file=html&source=local&fields=Asset,Secret'
            doc=c.get(target)
            self.assertEqual(doc.status_code,200,doc.text)
            self.assertIn('new.html',doc.text)
            self.assertIn('R42',doc.text)
            self.assertNotIn('fake',doc.text)
            self.assertIn('文件未提供',doc.text)
            root=Path(__file__).resolve().parents[1]
            book=next((root/'demo').glob('*.xlsx'))
            loaded=c.post('/extract/workbook',headers={'X-Demo-Local':'1','X-Demo-Filename':book.name},content=book.read_bytes())
            self.assertEqual(loaded.status_code,200,loaded.text)
            res=c.get('/extract?file=xlsx&source=local')
            self.assertEqual(res.status_code,200,res.text)
            self.assertIn('工作表',res.text)
            self.assertIn('name="field"',res.text)
            self.assertIn('action="/extract#workbook-results"',res.text)

    def test_pdf_docx_txt_markdown_and_privacy(self):
        fixtures=Path(__file__).resolve().parents[1]/"demo"/"docs"
        with TestClient(app) as c, TestClient(app) as other:
            for kind,name,field,contents,expected in (
                ("pdf","sample.pdf","Asset",(fixtures/"PDF-200.pdf").read_bytes(),"PDF-200"),
                ("docx","sample.docx","設備",(fixtures/"WORD-210.docx").read_bytes(),"WORD-210"),
                ("text","sample.txt","Asset",b"Asset: REAL-TXT","REAL-TXT"),
                ("md","sample.md","Asset",b"# Manual\nAsset: REAL-MD\n","REAL-MD"),
            ):
                with self.subTest(kind=kind):
                    r=c.post('/extract/file',headers={'X-Demo-Local':'1','X-Demo-Filename':name},content=contents)
                    self.assertEqual(200,r.status_code,r.text)
                    params={"file":kind,"source":"local","fields":field}
                    response=c.get('/extract',params=params)
                    self.assertEqual(200,response.status_code,response.text)
                    self.assertIn(expected,response.text)
                    self.assertNotIn(expected,other.get('/extract',params=params).text)
            self.assertEqual(c.post('/extract/file',headers={'X-Demo-Filename':'bad.txt'},content=b'Owner: hidden').status_code,403)

    def test_pdf_exports_fields_and_evidence_without_ocr(self):
        fixtures=Path(__file__).resolve().parents[1]/"demo"/"docs"
        with TestClient(app) as c:
            r=c.post("/extract/file",headers={"X-Demo-Local":"1","X-Demo-Filename":"readable.pdf"},
                     content=(fixtures/"PDF-200.pdf").read_bytes())
            self.assertEqual(200,r.status_code)
            params={"source":"local","file":"pdf","fields":"Asset,Status,Owner"}
            self.assertIn("下載結構化 JSON",c.get("/extract",params=params).text)
            r=c.get("/extract",params={**params,"download":"true"})
            self.assertEqual(200,r.status_code)
            value=r.json()
            self.assertEqual(value["source"],"readable.pdf")
            self.assertEqual(value["fields"],{"Asset":"PDF-200","Status":"Ready","Owner":None})
            self.assertTrue(all("page" in hit for hit in value["evidence"]["Asset"]))

    def test_mixed_pdf_reports_unreadable_page_and_does_not_publish_partial_values(self):
        from io import BytesIO
        from pypdf import PdfReader, PdfWriter
        base=Path(__file__).resolve().parents[1]/"demo"/"docs"/"PDF-200.pdf"
        writer=PdfWriter()
        writer.add_page(PdfReader(base).pages[0])
        writer.add_blank_page(width=200,height=200)
        output=BytesIO();writer.write(output)
        with TestClient(app) as c:
            for endpoint in ("/knowledge/files","/extract/file"):
                r=c.post(endpoint,headers={"X-Demo-Local":"1","X-Demo-Filename":"partial.pdf"},content=output.getvalue())
                self.assertEqual(422,r.status_code)
                self.assertEqual({"detail":"ocr_required","review_pages":[2],"accepted":False},r.json())
            self.assertNotIn("partial.pdf",c.get("/workspace").text)
            p=c.get("/extract",params={"source":"demo","file":"pdf","fields":"Asset,Status,Owner","download":"true"})
            self.assertEqual("original_not_verified",p.json()["review"]["status"])
            self.assertTrue(p.json()["review"]["cited_pages"])
