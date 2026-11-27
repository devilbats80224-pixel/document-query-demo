"""Cloud must publish the actual workbench rather than a hand-written demo."""
import unittest
from unittest.mock import patch
from test_cloud_sessions import SimulatedRedis

from fastapi.testclient import TestClient
import api_fastapi
import vercel_app


class FullWorkbenchCloud(unittest.TestCase):
    def test_cloud_uses_the_same_workbench_and_its_original_routes(self):
        routes=("/workspace","/knowledge","/analysis","/agent","/","/extract","/models","/integration","/guide")
        with TestClient(vercel_app.app) as cloud, TestClient(api_fastapi.app) as mac:
            for route in routes:
                with self.subTest(route=route):
                    cloud_page=cloud.get(route)
                    mac_page=mac.get(route)
                    self.assertEqual(cloud_page.status_code,200)
                    self.assertEqual(mac_page.status_code,200)
                    self.assertIn("KNOWLEDGE OPS",cloud_page.text)
                    self.assertIn("KNOWLEDGE OPS",mac_page.text)
                    self.assertIn('name="viewport"',cloud_page.text)

    def test_upload_read_query_and_reset_across_cloud_backend_instances(self):
        slots={}
        # A new backend object for every request, with an isolated shared store;
        # the test can't accidentally pass using Mac module globals.
        with patch("cloud_sessions.backend",side_effect=lambda:SimulatedRedis(slots)):
            with TestClient(vercel_app.app,base_url="https://example.test") as cloud:
                headers={"x-demo-local":"1","x-demo-filename":"ROUTE-573.md"}
                seed=cloud.post("/knowledge/files",headers=headers,content=b"# ROUTE-573\nROUTE-573 reports DELTA-804.")
                self.assertEqual(seed.status_code,200,seed.text)
                self.assertTrue(slots)
                own=cloud.get("/knowledge",params={"q":"ROUTE-573 DELTA-804","mode":"bm25","source":"local"})
                self.assertIn("ROUTE-573.md",own.text)
                isolated=TestClient(vercel_app.app,base_url="https://example.test").get("/workspace")
                self.assertNotIn("ROUTE-573.md",isolated.text)
                clear=cloud.delete("/knowledge/files",headers=headers)
                self.assertEqual(clear.status_code,200,clear.text)
                self.assertNotIn("ROUTE-573.md",cloud.get("/workspace").text)
