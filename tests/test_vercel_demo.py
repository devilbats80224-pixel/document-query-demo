import base64
from pathlib import Path
import tomllib
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

import cloud_sessions
import vercel_app


ENV={"LITEON_CHAT_PROVIDERS":"openai,gemini",
     "LITEON_OPENAI_API_KEY":"openai-provider-secret-fixture",
     "LITEON_GEMINI_API_KEY":"gemini-provider-secret-fixture",
     "DEMO_CLOUD_OWNER_PASSWORD":"owner-fixture-enough-characters-and-distinct"}


def basic():
    return {"Authorization":"Basic "+base64.b64encode(("owner:"+ENV["DEMO_CLOUD_OWNER_PASSWORD"]).encode()).decode()}


class VercelCloudTests(TestCase):
    def test_official_entrypoint_and_cloud_health(self):
        base=Path(__file__).resolve().parents[1]
        config=tomllib.loads((base/"pyproject.toml").read_text())
        self.assertEqual(config["tool"]["vercel"]["entrypoint"],"vercel_app:app")
        self.assertTrue(any(dep.startswith("fastapi==") for dep in config["project"]["dependencies"]))
        with TestClient(vercel_app.app) as client:
            self.assertEqual(client.get("/health").json()["mode"],"vercel_cloud")
            page=client.get("/knowledge",params={"q":"DEMO-100 E-402","source":"demo"}).text
            self.assertIn("KNOWLEDGE OPS",page)
            self.assertIn("來源",page)

    def test_anonymous_visitors_never_discover_or_bill_provider(self):
        with patch.dict("os.environ",ENV,clear=True), patch("local_models._provider_call") as upstream, TestClient(vercel_app.app) as client:
            for path in ("/agent","/models","/integration"):
                page=client.get(path).text
                self.assertIn("私人模型區",page)
                self.assertNotIn(ENV["LITEON_GEMINI_API_KEY"],page)
            self.assertEqual(client.post("/models/chat",headers={"X-Demo-Local":"1"},json={"model":"gemini:gemini-test","question":"hello"}).status_code,401)
            self.assertEqual(client.post("/integration/settings",headers={"X-Demo-Local":"1"},json={}).status_code,403)
            self.assertEqual(client.get("/owner/",follow_redirects=False).status_code,401)
            upstream.assert_not_called()

    def test_browser_session_is_secure_and_owner_can_switch_providers_in_original_ui(self):
        def upstream(route, body=None, *, provider="openai"):
            if route=="/v1/models":
                return {"data":[{"id":"gpt-4.1-mini" if provider=="openai" else "gemini-fixture"}]}
            return {"model":body["model"]+"-version","choices":[{"message":{"content":"fixture"}}]}
        with patch.dict("os.environ",ENV,clear=True), patch("local_models._provider_call",side_effect=upstream) as calls, TestClient(vercel_app.app,base_url="https://testserver") as client:
            owner=client.get("/owner/",headers=basic(),follow_redirects=False)
            self.assertEqual(owner.status_code,303)
            self.assertEqual(owner.headers["location"],"/models")
            cookie=owner.headers["set-cookie"]
            for part in ("Secure","HttpOnly","SameSite=strict","Path=/"):
                self.assertIn(part,cookie)
            self.assertNotIn(ENV["DEMO_CLOUD_OWNER_PASSWORD"],cookie)
            page=client.get("/models").text
            self.assertIn('value="openai:gpt-4.1-mini"',page)
            self.assertIn('value="gemini:gemini-fixture"',page)
            self.assertNotIn("local:qwen",page)
            self.assertNotIn(ENV["LITEON_OPENAI_API_KEY"],page)
            self.assertIn('value="gemini:gemini-fixture"',client.get("/agent").text)
            hdr={"X-Demo-Local":"1"}
            for provider,name,label in (("openai","gpt-4.1-mini","OpenAI"),("gemini","gemini-fixture","Gemini")):
                reply=client.post("/models/chat",headers=hdr,json={"model":provider+":"+name,"question":"hello"})
                self.assertEqual(reply.json(),{"model":name+"-version（"+label+"）","answer":"fixture","citations":[]})
                self.assertEqual(calls.call_args.kwargs.get("provider","openai"),provider)
            count=calls.call_count
            self.assertEqual(client.post("/models/chat",headers=hdr,json={"model":"local:qwen","question":"hello"}).status_code,503)
            self.assertEqual(client.post("/models/chat",headers={**hdr,"Sec-Fetch-Site":"cross-site"},json={"model":"gemini:gemini-fixture","question":"hello"}).status_code,403)
            self.assertEqual(client.post("/models/settings",headers=hdr,json={"chat":"qwen","embedding":"qwen"}).status_code,403)
            self.assertEqual(calls.call_count,count)

    def test_missing_storage_fails_loudly_and_oversize_is_rejected_before_handler(self):
        with patch.dict("os.environ",{},clear=True), TestClient(vercel_app.app) as client:
            self.assertIn("雲端上傳目前未設定",client.get("/workspace").text)
            response=client.post("/knowledge/files",headers={"X-Demo-Local":"1"},content=b"data")
            self.assertEqual(response.status_code,503)
            self.assertIn("沒有配置儲存空間",response.json()["detail"])
        with patch("cloud_sessions.backend",return_value=object()), TestClient(vercel_app.app) as client:
            response=client.post("/knowledge/files",headers={"Content-Length":"4500001","X-Demo-Local":"1"},content=b"synthetic")
            self.assertEqual(response.status_code,413)
            self.assertIn("4 MB",response.json()["detail"])

    def test_provider_key_cannot_double_as_password_and_cookie_tampering_fails(self):
        env={**ENV,"DEMO_CLOUD_OWNER_PASSWORD":ENV["LITEON_GEMINI_API_KEY"]}
        with patch.dict("os.environ",env,clear=True), TestClient(vercel_app.app) as client:
            self.assertEqual(client.get("/owner/").status_code,404)
        with patch.dict("os.environ",ENV,clear=True), TestClient(vercel_app.app) as client:
            client.cookies.set(vercel_app.OWNER_COOKIE,"1765000000."+"0"*64)
            self.assertEqual(client.post("/models/chat",headers={"X-Demo-Local":"1"},json={"question":"hello","model":"gemini:gemini-test"}).status_code,401)

    def test_cloud_store_outage_is_not_reported_as_unreadable_file(self):
        with patch("cloud_sessions.backend",return_value=object()), patch("local_library.add",side_effect=cloud_sessions.CloudStorageError("secret internal failure")), TestClient(vercel_app.app) as client:
            headers={"X-Demo-Local":"1","X-Demo-Filename":"hello.txt"}
            response=client.post("/knowledge/files",headers=headers,content=b"Synthetic content for source verification.")
            self.assertEqual(response.status_code,503)
            self.assertIn("雲端儲存暫時無法使用",response.json()["detail"])
            self.assertNotIn("secret internal failure",response.text)
