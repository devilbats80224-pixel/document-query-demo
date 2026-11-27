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

## 模型切換與手機版

- 「本地模型」及「智慧 Agent」顯示本次選擇，成功生成時另顯示實際使用的模型。沒有可用模型時，頁面會明示無法生成；文件檢索結果不會標成模型回答。關鍵字檢索和不依賴模型的工具仍可使用。
- 選用代管模型時，在後端服務環境提供 `LITEON_OPENAI_API_KEY` 或 `LITEON_GEMINI_API_KEY`，並用 `LITEON_CHAT_PROVIDERS=openai,gemini` 指定啟用的平台（只有一家時只填該家）。程式從支援平台的官方目錄自動列出候選，不把金鑰送至瀏覽器。目錄有列出不代表已有生成權限；嘗試生成後會標明結果，失敗的選項會停用並可重新檢查。頁面載入或目錄發現不會代你試跑生成。
- 預設 Mac Docker 交付未配置任何代管金鑰。不要把金鑰提交到 Git 或寫進映像；若對外開放，配置付費模型前應先有登入、速率限制及用量預算。代管模型只接收你輸入的生成問題，不會自動附上上傳檔案。想完全離線就維持本機模式。
- 瀏覽器測試涵蓋 320、390、430px 的九個頁面，並驗證窄版觸控上傳、移除和確認清空；這是 Chromium 證據，不等於所有手機或 Safari 實機都已測。
