# Reproduce checks

Run from repository root. Work and downloaded sources belong outside the installed skill.

```bash
python3 tools/validate.py
python3 -m unittest discover -s tests -v
python3 tools/format_regression.py --output-root /path/to/work/formats
python3 tools/make_demos.py --output-root /path/to/work/demos
python3 skills/document-translation/scripts/translate.py render /path/to/work/demos/demo-ar
python3 tools/integration.py --output-root /path/to/work/integration
python3 tools/pdf_corpus_regression.py prepare --pdf-root /path/to/pdf-corpus --output-root /path/to/work/pdf-corpus-regression --seed 173 --count 8
python3 tools/checksums.py
```

`integration.py` additionally needs python-docx (`requirements-optional.txt`). Reusing an existing integration directory is intentionally rejected by init; choose a fresh directory or explicitly remove only your test output. If Playwright's downloaded browser is not the one installed on the host, use `TRANSLATION_BROWSER` or `--browser`. No machine-specific executable path is packaged.

`format_regression.py` creates owned fixtures for native and conversion-backed common formats outside the package, then tests extraction and structural preservation. Legacy Office formats need local LibreOffice or macOS `textutil`.

`pdf_corpus_regression.py prepare` selects PDFs from a lexicographically sorted recursive inventory using the supplied seed, extracts page 1 and the one-based lower midpoint, and creates translation tasks. Extraction alone does not make this a completed regression. In the invoking agent loop, inspect each selected source page, correct its IR, translate every selected unit into both editions, apply real packets, compare original text against both editions, build and render, refine and inspect actual page images, and record complete extraction/semantic/visual evidence. Then run `pdf_corpus_regression.py check`; it rejects missing translations, stale reviews, and incomplete rendered outputs. Keep project, PDF, translation and screenshot results outside the distributable skill package.

To fetch an authorized source use `scripts/fetch_pdf.py URL OUTPUT.pdf --rights "record the applicable rights"`. Curl follows checked redirects, validates HTTP(S), rejects private addresses by default, enforces time/size limits, checks the signature and opens the PDF; it writes acquisition metadata. URL checks are not a comprehensive untrusted-network sandbox. Use only trusted public endpoints. Do not disable TLS verification to force a pass.

The invoking model performs translation directly; no external inference service is required. Do not use fixed fixture translations, source echoes or seeded strings as evidence of a semantic regression. Historical OCR remains blocked until each uncertain unit is checked against the page.

Bundled demo outputs are snapshots. Rebuilding may change page breaks, PDF bytes and metadata across fonts/browser versions. Use semantic/coverage/layout checks, then visually inspect the rebuilt pages rather than expecting identical PDF hashes.

Additional owned visual fixtures: run `python3 tools/make_visual_demos.py --output-root /path/to/work/visual --font /path/to/licensed-cjk-font.ttf`, render both projects, then compare the actual images and captions. This generator uses known transcription ground truth; it does not claim a fresh OCR run. Re-run OCR separately for OCR validation.

Platform copy/metadata checks: `python3 tools/verify_platform_contract.py`; add `--clouds-source /path/to/trusted/Clouds_Coder.py` only for a trusted snapshot whose pure metadata methods you intend to execute. No full client import or interactive session is implied.
