# Document query demo

A local FastAPI document workbench. The tracked inputs in `demo/` are synthetic fixtures. No exam submissions, live API credentials, private uploads, or cloud deployment configuration are included.

Run `python -m pip install -r requirements-optional.txt`, then `python -B -m uvicorn api_fastapi:app --host 127.0.0.1 --port 8775`. Open the local `/knowledge` page.

To verify a change, run the unit tests and `node scripts/verify-browser.mjs` with Python 3.12, Node 22+, and Chrome or Chromium. The browser uses a separate profile; output is in `verification-evidence/`. The same commands run on pull requests.
