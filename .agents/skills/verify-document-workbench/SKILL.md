---
name: verify-document-workbench
description: Use when verifying document upload, retrieval, source citations, or unsupported questions in the document-query demo.
---

# Verify the document workbench

## Launch
From the project root run `DEMO_PYTHON=python3 node scripts/verify-browser.mjs`. Use Node 22+, Chrome or Chromium, and a Python environment with `requirements-optional.txt`. The test starts its own app and a fresh browser on loopback with isolated state; do not start a second server or use a real exam document.

## Doctor
The script checks that Chrome is available and the app health response identifies local-offline mode. If Chrome cannot be found, set `CHROME_BIN` to its executable. If Python cannot import the app, point `DEMO_PYTHON` to the prepared virtual environment.

## Drive
The browser selects and submits the synthetic PDF through the real upload button, submits a supported query, then submits an unrelated query. Follow the assertions in [the feature map](features/document-query.md). Run the same command in GitHub Actions, not an API-only substitute.

## Evidence
Read `verification-evidence/report.json` and the two screenshots, or set `VERIFY_EVIDENCE` to a separate folder. A valid run shows the cited filename and page for the supported question, plus zero citations for the unsupported one. Any failed assertion is a failed run even if a screenshot exists.

## Cleanup
The script stops only the test processes and removes only its temporary profile. Evidence remains outside that profile. Never clear the user's existing browser uploads or send their files or model credentials to CI.
