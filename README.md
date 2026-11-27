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
