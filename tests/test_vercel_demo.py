import base64
from pathlib import Path
import tomllib
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

import vercel_app


class VercelCloudTests(TestCase):
    def test_official_entrypoint_and_fixtures(self):
        base=Path(__file__).resolve().parents[1]
        config=tomllib.loads((base/"pyproject.toml").read_text())
        self.assertEqual(config["tool"]["vercel"]["entrypoint"],"vercel_app:app")
        self.assertIn("fastapi", (base/"requirements.txt").read_text())
        with TestClient(vercel_app.app) as client:
            self.assertEqual(client.get("/health").json()["mode"],"vercel_cloud")
            page=client.get("/knowledge",params={"q":"DEMO-100 E-402"}).text
            self.assertIn("內建合成文件",page)
            self.assertIn("可引用片段",page)

    def test_public_cloud_ui_cannot_upload_configure_or_use_provider(self):
        with patch.dict("os.environ",{"LITEON_GEMINI_API_KEY":"fixture-only"},clear=True), patch("local_models._provider_call") as upstream, TestClient(vercel_app.app) as client:
            page=client.get("/").text
            self.assertIn("不接收上傳",page)
            self.assertNotIn("fixture-only",page)
            for path in ("/owner/chat","/models/chat","/knowledge/files","/analysis/file","/extract/workbook","/integration/settings"):
                self.assertEqual(client.post(path,headers={"X-Demo-Local":"1"},json={"question":"hello"}).status_code,404)
            upstream.assert_not_called()

    def test_owner_limited_to_authenticated_gemini_and_exact_route(self):
        key="secret-fixture-should-not-be-returned"
        owner_pass="owner-pass-fixture-with-enough-length"
        auth="Basic "+base64.b64encode(("owner:"+owner_pass).encode()).decode()
        with patch.dict("os.environ",{"DEMO_CLOUD_OWNER_PASSWORD":owner_pass,"LITEON_GEMINI_API_KEY":key,"LITEON_CHAT_PROVIDERS":"gemini"},clear=True), patch("local_models._provider_call") as upstream, TestClient(vercel_app.app) as client:
            headers={"Authorization":auth,"X-Demo-Cloud-Chat":"1"}
            self.assertEqual(client.get("/owner/").status_code,401)
            self.assertEqual(client.post("/owner/chat",json={"model":"gemini:gemini-test","question":"hello"}).status_code,401)
            self.assertEqual(client.post("/owner/chat",headers={"Authorization":auth},json={"model":"gemini:gemini-test","question":"hello"}).status_code,403)
            self.assertEqual(client.post("/owner/chat",headers={**headers,"Sec-Fetch-Site":"cross-site"},json={"model":"gemini:gemini-test","question":"hello"}).status_code,403)
            upstream.assert_not_called()
            upstream.side_effect=[
                {"data":[{"id":"gemini-test"},{"id":"gemini-embedding-001"}]},
                {"data":[{"id":"gemini-test"},{"id":"gemini-embedding-001"}]},
                {"model":"gemini-test-version","choices":[{"message":{"content":"fixture answer"}}]},
            ]
            page=client.get("/owner/",headers=headers)
            self.assertEqual(page.status_code,200)
            self.assertNotIn(key,page.text)
            self.assertNotIn(owner_pass,page.text)
            self.assertNotIn("gemini-embedding-001",page.text)
            self.assertEqual(page.headers["cache-control"],"no-store")
            reply=client.post("/owner/chat",headers=headers,json={"model":"gemini:gemini-test","question":"hello"})
            self.assertEqual(reply.json(),{"provider":"Gemini","model":"gemini-test-version","answer":"fixture answer"})
            self.assertEqual([c.kwargs.get("provider") for c in upstream.call_args_list],["gemini"]*3)
            self.assertEqual(upstream.call_args.args[0],"/v1/chat/completions")

    def test_provider_key_cannot_double_as_owner_login(self):
        secret="fixture-secret-that-must-stay-server-side"
        with patch.dict("os.environ",{"LITEON_GEMINI_API_KEY":secret,"DEMO_CLOUD_OWNER_PASSWORD":secret},clear=True), patch("local_models._provider_call") as upstream, TestClient(vercel_app.app) as client:
            self.assertEqual(client.get("/owner/").status_code,404)
            upstream.assert_not_called()

    def test_owner_switches_between_both_configured_providers(self):
        owner_pass="owner-fixture-enough-characters-and-distinct"
        auth="Basic "+base64.b64encode(("owner:"+owner_pass).encode()).decode()
        env={"LITEON_CHAT_PROVIDERS":"openai,gemini","LITEON_OPENAI_API_KEY":"openai-fixture",
             "LITEON_GEMINI_API_KEY":"gemini-fixture","DEMO_CLOUD_OWNER_PASSWORD":owner_pass}
        def upstream(route, body=None, *, provider="openai"):
            if route=="/v1/models":
                return {"data":[{"id":"gpt-4.1-mini" if provider=="openai" else "gemini-fixture"}]}
            self.assertEqual(route,"/v1/chat/completions")
            return {"model":body["model"]+"-version","choices":[{"message":{"content":"fixture"}}]}
        with patch.dict("os.environ",env,clear=True), patch("local_models._provider_call",side_effect=upstream) as calls, TestClient(vercel_app.app) as client:
            headers={"Authorization":auth,"X-Demo-Cloud-Chat":"1"}
            page=client.get("/owner/",headers=headers).text
            self.assertIn("私人模型區",page)
            self.assertIn('value="openai:gpt-4.1-mini"',page)
            self.assertIn('value="gemini:gemini-fixture"',page)
            for provider,name,label in (("openai","gpt-4.1-mini","OpenAI"),("gemini","gemini-fixture","Gemini")):
                reply=client.post("/owner/chat",headers=headers,json={"model":provider+":"+name,"question":"hello"})
                self.assertEqual(reply.json(),{"provider":label,"model":name+"-version","answer":"fixture"})
                self.assertEqual(calls.call_args.kwargs.get("provider","openai"),provider)
            count=calls.call_count
            reply=client.post("/owner/chat",headers=headers,json={"model":"unknown:model","question":"hello"})
            self.assertEqual(reply.status_code,503)
            self.assertEqual(calls.call_count,count)
