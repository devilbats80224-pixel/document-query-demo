# Document query

- **Input:** `demo/docs/PDF-200.pdf`, a synthetic two-page document.
- **Positive:** query `PDF-200 ALARM-931` after browser upload; the original PDF name and page 2 must be shown.
- **Negative:** query `NOT-IN-SOURCE-8874`; the page must say there is no supported answer and show no citation.
- **Run:** `node scripts/verify-browser.mjs`; the process must exit zero and produce `report.json` and both screenshots.
