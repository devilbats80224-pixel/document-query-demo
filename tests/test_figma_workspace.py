from unittest import TestCase
from fastapi.testclient import TestClient
from api_fastapi import app

class FigmaWorkspaceTest(TestCase):
    def test_export_theme_is_shared_and_does_not_import_external_assets(self):
        with TestClient(app) as c:
            for path in ("/workspace","/","/knowledge","/analysis","/extract","/agent","/integration","/models","/guide"):
                with self.subTest(path=path):
                    r=c.get(path)
                    self.assertEqual(200,r.status_code)
                    self.assertIn('data-ui="figma-make"',r.text)
                    self.assertIn('aria-label="操作流程"',r.text)
                    self.assertNotIn("fonts.googleapis.com",r.text)
                    self.assertNotIn("早安，林組長",r.text)

    def test_ui_routes_connect_to_current_data_and_not_fixed_mock(self):
        with TestClient(app) as c:
            home=c.get("/workspace").text
            self.assertIn('data-upload-scope="workspace"',home)
            for target in ('/knowledge?source=local','/analysis','/models','/integration'):
                self.assertIn(f'href="{target}"',home)
            self.assertIn("3.40%",c.get("/agent?line=L1").text)
            self.assertIn("查無有效資料",c.get("/agent?line=L9").text)
            self.assertIn("排除 1 筆",c.get("/?sample=csv&line=L1").text)
            self.assertNotIn("86.4%",c.get("/agent").text)

    def test_presentation_pages_do_not_show_private_prep_copy(self):
        with TestClient(app) as c:
            for path in ("/workspace","/knowledge","/analysis","/extract","/agent","/integration","/models","/guide"):
                with self.subTest(path=path):
                    html=c.get(path).text
                    for banned in ("考官","考場","考試","主辦","口說","Codex"):
                        self.assertFalse(banned in html, f"{path} contains private prep copy: {banned}")
