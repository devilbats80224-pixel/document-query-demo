import json
from html import unescape
import re
import unittest

from fastapi.testclient import TestClient

from api_fastapi import app


class JsonAndSearchUi(unittest.TestCase):
    def test_workspace_attachment_opt_in_and_exact_agent_payload(self):
        query = {"q": "PDF-200 ALARM-931", "source": "demo"}
        with TestClient(app) as client:
            inline = client.get("/api/workspace/query", params=query)
            download = client.get("/api/workspace/query", params={**query, "download": "true"})
            self.assertNotIn("content-disposition", inline.headers)
            self.assertEqual(download.headers["content-disposition"], 'attachment; filename="workspace-result.json"')
            self.assertEqual(download.headers["cache-control"], "no-store")
            self.assertEqual(download.json(), inline.json())
            agent = client.get("/agent", params=query).text
            self.assertIn("查看本次 JSON", agent)
            self.assertIn("下載 JSON", agent)
            payload = re.search(r'<textarea hidden id="agent-json-content">(.*?)</textarea>', agent, re.S)
            self.assertIsNotNone(payload)
            self.assertEqual(json.loads(unescape(payload[1])), inline.json())
            playground = client.get("/integration").text
            self.assertIn('id="workspace-api-download" download="workspace-result.json"', playground)
            self.assertIn('new Blob([JSON.stringify(reply,null,2)]', playground)

    def test_search_copy_distinguishes_methods_from_tabular_analysis(self):
        with TestClient(app) as client:
            doc = client.get("/knowledge").text
            for phrase in ["關鍵字搜尋", "字元相似搜尋", "混合搜尋", "關鍵字檢索（BM25 排名）",
                           "字元向量（TF-IDF）", "餘弦相似度", "Qwen3 Embedding"]:
                self.assertIn(phrase, doc)
            self.assertIn("不做文件索引", client.get("/analysis").text)
            self.assertNotIn("BM25", client.get("/analysis").text)
