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

### Vercel 雲端版（獨立入口；不取代 Mac Docker）

Vercel 專案用同一個 GitHub 儲存庫，Root Directory 保持根目錄，框架選 **FastAPI**。按 [Vercel FastAPI 官方說明](https://vercel.com/docs/frameworks/backend/fastapi) 由 `pyproject.toml` 指到 `vercel_app:app`，依賴鎖定在同一份 `pyproject.toml` 的 `[project]`。Mac Docker 仍以原本的 `api_fastapi:app` 啟動，不吃這些設定。合併 PR 的 GitHub Actions 須先全綠，再用 Vercel 對應 commit 的部署驗收；預覽先不帶任何金鑰。

- 雲端和 Mac 共用原版工作台、導航與九個頁面。雲端不直連 Mac 的模型；本地模型、離線操作仍在 Mac。訪客可以用工作台和示範資料，但未登入不可共用網站擁有者的模型額度。
- 在 Vercel Marketplace 將免費的 Upstash Redis 連到這個專案，讓瀏覽器重新整理及雲端執行個體切換後仍能讀回。支援整組 `KV_REST_API_URL`／`KV_REST_API_TOKEN` 或整組 `UPSTASH_REDIS_REST_URL`／`UPSTASH_REDIS_REST_TOKEN`，不可彼此混用。只暫存解析後的工作台資料，原始檔不寫入 Redis，各瀏覽器隔離、兩小時到期。沒配置時上傳選項會顯示原因，不會假裝已存。
- Vercel 版每個檔案 4 MB，避免超過 Vercel Functions 的 4.5 MB 請求限制；Mac 版原有上限不變。
- 要啟用私人模型區，在 Vercel 專案 **Settings → Environment Variables** 的 **Production** 環境加入：
  - `LITEON_CHAT_PROVIDERS` = `gemini`、`openai` 或 `openai,gemini`
  - 選 Gemini 時，`LITEON_GEMINI_API_KEY` = 自己在 [Google AI Studio](https://aistudio.google.com/apikey) 建立的 API 金鑰（用 Secret/Sensitive 設定）
  - 選 OpenAI 時，`LITEON_OPENAI_API_KEY` = 自己在 [OpenAI Platform](https://platform.openai.com/api-keys) 建立的 API 金鑰（用 Secret/Sensitive 設定）
  - `DEMO_CLOUD_OWNER_PASSWORD` = 另外產生的高熵隨機密碼，32–128 位英數、`_` 或 `-`，例如自行在終端執行 `openssl rand -hex 32` 產生。**不可與任一模型金鑰相同。**
- 重新部署該 Production 版本後，以 HTTPS 開 `/owner/`，使用固定帳號 `owner` 和自己設定的擁有者密碼登入。**不要把模型金鑰輸入網頁或貼到對話、GitHub、CI 紀錄。**金鑰只由伺服器傳給各自的模型供應商；不要分享擁有者密碼，也不要在共享裝置保存瀏覽器登入資料。
- 擁有者登入後才會讀取可選模型，選定後送出一則測試問題才會生成；頁面會顯示實際回傳的模型。生成會使用所選供應商帳戶額度，建議由擁有者設定適當配額／預算警示。
- 部署後驗收：`GET /health` 顯示 `mode: vercel_cloud`；`/knowledge?q=DEMO-100+E-402` 有可引用片段；用合成檔執行上傳、重新整理、查詢與清除，確認獨立瀏覽器看不到檔案；訪客送 `POST /models/chat` 必須是 401，不能消耗 API 額度。
