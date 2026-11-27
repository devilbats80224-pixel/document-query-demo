# Document query demo

A local FastAPI document workbench. The tracked inputs in `demo/` are synthetic fixtures. No exam submissions, live API credentials, private uploads, or cloud deployment configuration are included.

Run `python -m pip install -r requirements-optional.txt`, then `python -B -m uvicorn api_fastapi:app --host 127.0.0.1 --port 8775`. Open the local `/knowledge` page.

To verify a change, run the unit tests and `node scripts/verify-browser.mjs` with Python 3.12, Node 22+, and Chrome or Chromium. The browser uses a separate profile; output is in `verification-evidence/`. The same commands run on pull requests.

## Mac Docker (Apple Silicon)

GitHub CI tests the ARM64 image without any network. A green build on `main`
attaches that tested image plus its commit and checksums. The Mac CD entry
loads the artifact from the verified Actions run, validates it and binds the
web app only to `127.0.0.1:8875`. The original offline Mac bundle is unaffected.
Model-independent upload, retrieval and analysis do not need a model or internet.
The optional Mac model servers remain at loopback; the container connects
through Docker Desktop's host alias using a read-only local token mount.
No token or model weights are part of the image or CI. The upload library
remains in memory and resets on container restart.

## 靜態檢查

PR 的既有必過工作會跑 `ruff check .`（全庫 Python 語法與未定義名稱等高信號錯誤）及
`pyright --project pyrightconfig.json`（目前指定的文件讀取、表格品質、模型設定和映像識別模組，並非全庫）。
本機使用 Ruff 0.17.6 與 Pyright 1.1.414 即可重跑。擴大型別檢查範圍時請更新
`pyrightconfig.json`，不要用型別檢查取代既有測試或 Docker 驗證。
