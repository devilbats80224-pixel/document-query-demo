from unittest import TestCase
from unittest.mock import patch
from fastapi.testclient import TestClient
from api_fastapi import app

class DoneCards(TestCase):
    def test_document_cases_in_one_card_in_that_order(self):
        with TestClient(app) as c:
            text=c.get("/knowledge").text
            card=text.split('class="document-case-card"',1)[1].split('</nav>',1)[0]
            labels=["找到答案","文件沒寫","來源衝突"]
            self.assertEqual(sorted(map(card.index,labels)),list(map(card.index,labels)))
            self.assertNotIn("停止出貨",text)
            self.assertIn("來源衝突，暫不給單一答案",
                         c.get("/knowledge",params={"source":"demo","q":"DEMO-100 交接時限"}).text)

    def test_agent_picker_calls_chosen_real_tool_and_labels_this_result(self):
        with TestClient(app) as c, patch("local_models.search",return_value=[]) as pick:
            a=c.get("/agent")
            self.assertIn('id="agent-model"',a.text)
            self.assertIn("Qwen3 Embedding 0.6B",a.text)
            q=c.get("/agent",params={"source":"demo","q":"PDF-200 ALARM-931","model":"qwen"})
            self.assertIn("本次使用：Qwen3 Embedding 0.6B",q.text)
            pick.assert_called_once()
            self.assertEqual(pick.call_args.args[2],"hybrid")
            data=c.get("/api/workspace/query",params={"source":"demo","q":"加總 金額","model":"qwen"}).json()
            self.assertEqual("未使用模型",data["model"])
            self.assertEqual(pick.call_count,1)
            self.assertIn('class="api-setting-field"',c.get("/integration").text)

    def test_agent_fails_clearly_when_model_offline_no_silent_fallback(self):
        with TestClient(app) as c, patch("local_models.search",side_effect=ValueError("local_model_not_running")):
            r=c.get("/api/workspace/query",params={"source":"demo","q":"PDF-200 ALARM-931","model":"qwen"})
            self.assertEqual(r.json()["status"],"model_unavailable")
            self.assertEqual(r.json()["evidence"],[])
