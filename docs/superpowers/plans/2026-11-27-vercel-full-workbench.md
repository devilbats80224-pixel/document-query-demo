# Original workbench on Vercel: implementation plan

> **For agentic workers:** Use superpowers:executing-plans, one verified step at a time.

**Goal:** Serve the original Mac workbench's interface and feature set on Vercel, not a simplified showcase.

**Architecture:** Reuse the original FastAPI app, templates, routes, document and table parsers. Only replace hosting-specific capabilities at the cloud boundary. Vercel needs expiring, browser-isolated storage for parsed sessions across function instances; cloud models are server-configured and protected.

**Stack:** Existing FastAPI, Python 3.12 and Chromium; Vercel deployment. The storage boundary must be reusable and must not tie the project to a particular personal host.

## Gates

- [ ] Add a browser parity test and verify the current reduced cloud app fails: original navigation, all workbench routes, and upload/query/reset are present.
- [ ] Reuse the original app for cloud entry, with cloud cookie and settings logic. Verify original visuals on mobile and preserve the existing Mac entry and local-model transport.
- [ ] Implement an isolated, private, expiring cloud session store for parsed data; prove upload in one instance, read/query after process restart in another, reset, and no cross-session access. Do not persist raw uploads unnecessarily.
- [ ] Keep Gemini/OpenAI switching in the original Agent/model screens, protect cloud generation with owner authentication; no key sent to the browser or shared with guests.
- [ ] Verify supported public upload size before buffering and show actual cloud platform limits; do not silently lose content. No changed storage provider, persistent account, or paid resource without authorization.
- [ ] Green GitHub checks on the latest PR plus cloud preview end-to-end with synthetic data before publishing; anonymous share, private generation, and Mac verified separately.
