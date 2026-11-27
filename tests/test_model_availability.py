import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

import local_models
from api_fastapi import app


class ModelAvailabilityTests(TestCase):
    def test_status_tests_real_chat_and_embedding_responses_separately(self):
        def reply(kind, payload, *, timeout):
            self.assertLessEqual(timeout, 2)
            self.assertNotIn("documents", payload)
            if kind == "chat":
                return {"choices": [{"message": {"content": "ok"}}]}
            return {"data": [{"index": 0, "embedding": [0, 0]}]}
        with patch("local_models._call", side_effect=reply) as call:
            self.assertTrue(local_models.available("chat"))
            self.assertFalse(local_models.available("embedding"))
            self.assertEqual([args.args[0] for args in call.call_args_list], ["chat", "embedding"])

    def test_offline_embedding_is_not_selectable_and_agent_does_not_fallback(self):
        with TestClient(app) as client, patch("local_models.available", return_value=False), patch("local_models.search") as search:
            self.assertIn('<option value="qwen" disabled>', client.get("/agent").text)
            data = client.get("/api/workspace/query", params={"source":"demo", "q":"PDF-200 ALARM-931", "model":"qwen"}).json()
            self.assertEqual(data["status"], "model_unavailable")
            self.assertEqual(data["evidence"], [])
            search.assert_not_called()

    def test_independent_selection_and_unavailable_chat_cannot_be_forced(self):
        with tempfile.TemporaryDirectory() as d, patch.dict("os.environ", {"LITEON_SETTINGS_PATH":str(Path(d)/"prefs.json")}), TestClient(app) as client:
            headers = {"X-Demo-Local":"1"}
            with patch("local_models.available", side_effect=lambda kind:kind=="chat"):
                self.assertEqual(client.get("/models/status").json(), {"chat":True,"embedding":False})
                self.assertEqual(client.post("/models/settings", headers=headers, json={"chat":"qwen","embedding":"character"}).status_code, 200)
                self.assertEqual(client.post("/models/settings", headers=headers, json={"chat":"qwen","embedding":"qwen"}).status_code, 503)
            with patch("local_models.available", return_value=False), patch("local_models.chat") as chat:
                self.assertEqual(client.post("/models/chat", headers=headers, json={"question":"試聊"}).status_code, 503)
                chat.assert_not_called()

    def test_settings_saved_before_outage_do_not_fake_knowledge_or_chat(self):
        with TestClient(app) as client, patch("model_settings.local_load", return_value={"embedding":"qwen","chat":"qwen"}), patch("local_models.available", return_value=False), patch("local_models.search") as search:
            model_page = client.get("/models").text
            self.assertEqual(model_page.count('<option value="qwen" disabled>'), 2)
            self.assertIn('<button disabled>問本地模型</button>', model_page)
            self.assertIn('系統沒有更改原設定', model_page)
            knowledge = client.get("/knowledge", params={"source":"demo","q":"DEMO-100","mode":"vector"}).text
            self.assertIn('value="vector" disabled', knowledge)
            self.assertIn('本地向量模型目前無法完成查詢', knowledge)
            self.assertNotIn('找到可引用片段', knowledge)
            search.assert_not_called()
            fallback = client.get("/knowledge", params={"source":"demo","q":"DEMO-100","mode":"bm25"}).text
            self.assertIn('找到可引用片段', fallback)

    def test_offline_planner_no_model_invocation(self):
        with TestClient(app) as client, patch("local_models.available", return_value=False), patch("local_models.calculation_proposal") as plan:
            uploaded=client.post("/analysis/file",headers={"X-Demo-Local":"1","X-Demo-Filename":"store.csv"},
                                 content="部門,計畫,實際,單位\nA,10,8,個\n".encode())
            self.assertEqual(uploaded.status_code, 200)
            page=client.get("/agent/calc",params={"q":"我要對照這份表","planner":"qwen"}).text
            self.assertIn('<option value="qwen" disabled>', page)
            self.assertIn('可以手動輸入', page)
            plan.assert_not_called()

    def test_adding_trusted_api_discovers_chat_models_without_exposing_key(self):
        with tempfile.TemporaryDirectory() as d, patch.dict("os.environ", {"LITEON_SETTINGS_PATH":str(Path(d)/"prefs.json"),"LITEON_OPENAI_API_KEY":"synthetic-test-credential"}), TestClient(app) as client:
            with patch("local_models._provider_call",return_value={"data":[{"id":"gpt-4.1-mini"},{"id":"text-embedding-3-small"}]}) as upstream:
                outcome=client.post("/integration/settings",headers={"X-Demo-Local":"1"},json={"chat_url":"https://api.openai.com/v1/chat/completions"})
                self.assertEqual(outcome.status_code,200)
                self.assertEqual(outcome.json()["chat_models"],["gpt-4.1-mini"])
                self.assertNotIn("synthetic-test-credential",outcome.text)
                upstream.assert_called_once_with("/v1/models")

    def test_agent_distinguishes_retrieval_from_generation_when_no_model(self):
        with TestClient(app) as client, patch("local_models.available",return_value=False):
            h=client.get("/agent",params={"q":"PDF-200 ALARM-931","source":"demo"}).text
            self.assertIn("沒有可用模型，無法生成回答",h)
            self.assertIn("查詢結果（非模型生成）",h)
            self.assertIn("目前選用聊天模型",h)

    def test_switching_hosted_models_uses_exact_allowlisted_choice_and_reports_provider_result(self):
        with TestClient(app) as client, patch("local_models.provider_chat_models",return_value=["gpt-4.1-mini","gpt-4.1"]) as catalog:
            def provider_reply(route, body):
                self.assertEqual(route,"/v1/chat/completions")
                self.assertEqual(body["messages"][-1]["content"],"只送這個問題")
                self.assertNotIn("documents",body)
                return {"model":body["model"]+"-2025-04-14","choices":[{"message":{"content":"測試答案"}}]}
            with patch("local_models._provider_call",side_effect=provider_reply) as upstream:
                hdr={"X-Demo-Local":"1"}
                for choice in ("gpt-4.1-mini","gpt-4.1"):
                    response=client.post("/models/chat",headers=hdr,json={"question":"只送這個問題","model":"openai:"+choice})
                    self.assertEqual(response.status_code,200)
                    self.assertEqual(response.json()["model"],choice+"-2025-04-14（OpenAI）")
                    self.assertEqual(response.json()["answer"],"測試答案")
                response=client.post("/models/chat",headers=hdr,json={"question":"只送這個問題","model":"openai:text-embedding-3-small"})
                self.assertEqual(response.status_code,503)
                self.assertEqual(upstream.call_count,2)
                self.assertEqual(catalog.call_count,3)

    def test_unrecognized_provider_origin_never_discovers_models(self):
        with tempfile.TemporaryDirectory() as d, patch.dict("os.environ", {"LITEON_SETTINGS_PATH":str(Path(d)/"prefs.json"),"LITEON_OPENAI_API_KEY":"fixture-only"}), TestClient(app) as client, patch("local_models._provider_call") as upstream:
            response=client.post("/integration/settings",headers={"X-Demo-Local":"1"},json={
                "chat_url":"https://api.openai.com.example.invalid/v1/chat/completions","chat_model":"not-openai"})
            self.assertEqual(response.json(),{"status":"saved","provider_called":False})
            self.assertNotIn("not-openai",client.get("/agent").text)
            upstream.assert_not_called()

    def test_gemini_discovery_and_chat_use_fixed_provider_and_exclude_embedding(self):
        with tempfile.TemporaryDirectory() as d, patch.dict("os.environ", {"LITEON_SETTINGS_PATH":str(Path(d)/"prefs.json"),"LITEON_GEMINI_API_KEY":"fixture-only"}), TestClient(app) as client:
            def fake(route, body=None, *, provider="openai"):
                self.assertEqual(provider,"gemini")
                if body is None:
                    self.assertEqual(route,"/v1/models")
                    return {"data":[{"id":"gemini-2.5-flash"},{"id":"gemini-embedding-001"}]}
                self.assertEqual(route,"/v1/chat/completions")
                self.assertEqual(body["model"],"gemini-2.5-flash")
                return {"model":"gemini-2.5-flash","choices":[{"message":{"content":"Gemini 回答"}}]}
            with patch("local_models._provider_call",side_effect=fake):
                headers={"X-Demo-Local":"1"}
                result=client.post("/integration/settings",headers=headers,json={"chat_url":"https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"})
                self.assertEqual(result.json()["chat_models"],["gemini-2.5-flash"])
                self.assertIn('value="gemini:gemini-2.5-flash"',client.get("/agent").text)
                response=client.post("/models/chat",headers=headers,json={"question":"你好","model":"gemini:gemini-2.5-flash"})
                self.assertEqual(response.json(),{"model":"gemini-2.5-flash（Gemini）","answer":"Gemini 回答","citations":[]})

    def test_hosted_transport_never_uses_user_supplied_destination_or_other_key(self):
        with patch.dict("os.environ", {"LITEON_OPENAI_API_KEY":"openai-fixture","LITEON_GEMINI_API_KEY":"gemini-fixture"}), patch("local_models.build_opener") as build:
            response=build.return_value.open.return_value.__enter__.return_value
            response.read.return_value=b'{"data":[]}'
            local_models._provider_call("/v1/models",provider="gemini")
            request=build.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url,"https://generativelanguage.googleapis.com/v1beta/openai/models")
            self.assertEqual(request.headers["Authorization"],"Bearer gemini-fixture")
            self.assertEqual(request.get_method(),"GET")
            local_models._provider_call("/v1/models")
            request=build.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url,"https://api.openai.com/v1/models")
            self.assertEqual(request.headers["Authorization"],"Bearer openai-fixture")
            with self.assertRaisesRegex(ValueError,"invalid_provider_route"):
                local_models._provider_call("http://127.0.0.1/v1/models")
            self.assertEqual(build.call_count,2)
