# Reproducing the checks

Run commands from the repository root. Put test projects, downloaded sources and screenshots outside the installed skill. Use a fresh output directory for each run.

## Structure and unit tests

With the core dependencies installed:

```bash
python3 tools/validate.py
python3 -m unittest discover -s tests -v
python3 tools/verify_platform_contract.py --output /path/to/platform-checks.json
python3 tools/checksums.py
```

These commands check metadata, local links, Python/JSON syntax, installation copies, source IDs, packet handling and specific extraction/rendering invariants. The platform check uses isolated copies and does not start interactive client sessions.

`tools/checksums.py` verifies the manifest. After intentional file changes, update it with `python3 tools/checksums.py --write`, then run verification again. For the current test results and their scope, see the [validation record](../skills/document-translation/references/validation-summary.md).

## Format and browser checks

Install the optional test dependencies before generating Office fixtures:

```bash
python3 -m pip install -r requirements-optional.txt
python3 tools/format_regression.py --output-root /path/to/work/formats
python3 tools/integration.py --output-root /path/to/work/integration
```

Format regression creates author-owned documents and tests extraction. It needs `python-docx`, `python-pptx` and `openpyxl`. Legacy Office and OpenDocument fixture generation needs LibreOffice; local RTF extraction can use macOS `textutil`. OCR uses an available local engine. Review the report to see which routes actually ran.

Integration exercises document structure and pagination with supplied fixture translations. Those fixed translations test the publishing pipeline, not fresh translation by a model.

Additional browser checks:

```bash
python3 tools/editor_i18n_regression.py --output /path/to/work/editor-locales
python3 tools/reader_i18n_regression.py --output /path/to/work/reader-locales
python3 tools/asset_fidelity_regression.py --output /path/to/work/figure-colors
```

These scripts need a local Chromium browser. Use `TRANSLATION_BROWSER` or their `--browser` option for an existing installation. Locale checks cover Chromium desktop/mobile emulation. The figure test uses author-owned color and vector fixtures. Read each report's failures and skipped routes before describing the result.

## Rebuild the examples

```bash
python3 tools/make_demos.py --output-root /path/to/work/demos
python3 skills/document-translation/scripts/translate.py render /path/to/work/demos/demo-ar
```

`make_demos.py` creates the five language projects from fixed example translations. It replaces matching demo directories under its output root, so use a dedicated test folder. It does not rebuild the whole gallery.

For the scan and figure fixtures:

```bash
python3 tools/make_visual_demos.py --output-root /path/to/work/visual --font /path/to/licensed-cjk-font.ttf
```

This generator uses known transcription text. Run OCR separately if testing recognition. Rebuilt PDF bytes and page breaks can vary with browser and font versions; compare content, layout reports and actual page images.

## Translate a PDF corpus

Prepare a reproducible selection from an authorized local PDF directory:

```bash
python3 tools/pdf_corpus_regression.py prepare --pdf-root /path/to/pdfs --output-root /path/to/work/corpus --seed 173 --count 8 --scope full --language zh-Hans
```

The seed controls file selection. `--scope full` includes every source page; the default `first-middle` scope selects page 1 and the lower midpoint. Preparation creates projects and tasks with empty translation fields.

Complete each project through the [translation workflow](WORKFLOW.md): inspect extraction, supply both translations through the current client model, compare meaning, render and adjust the documents, inspect every output page and record review evidence. Then run:

```bash
python3 tools/pdf_corpus_regression.py check --output-root /path/to/work/corpus
```

Missing translations, partial scope in a full run, stale reviews or missing outputs leave the regression incomplete. Keep the failed report. Successful extraction or a PDF without blank pages does not establish semantic translation quality.

## Public-source fixtures

The repository retains [acquisition records and excerpt scope](../skills/document-translation/references/public-test-provenance.json), not the downloaded third-party PDFs. Historical results are identified in the validation record and should not be reported as a new run.

The optional `scripts/fetch_pdf.py URL OUTPUT.pdf --rights "Applicable rights"` helper records acquisition metadata and checks the response as a PDF. Use an authorized public source. Its URL checks do not replace network isolation for untrusted endpoints.
