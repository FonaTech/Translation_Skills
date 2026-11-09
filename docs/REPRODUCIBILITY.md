# Reproducing the checks

Run commands from the repository root. Keep generated projects, downloaded sources and screenshots outside the repository and installed skill. Choose a fresh output directory for each run.

## Structure and unit tests

With core dependencies installed:

```bash
python3 tools/validate.py
python3 -m unittest discover -s tests -v
python3 tools/verify_platform_contract.py --output /path/to/platform-checks.json
python3 tools/checksums.py
```

Validation checks metadata, local links, syntax and version consistency. Unit tests exercise packet integrity, source structure, review evidence, layout behavior and release inventory. Platform checks use isolated installation copies rather than interactive client sessions.

After intentional file changes, run `python3 tools/checksums.py --write` and verify again. `tools/pack_release.py --output /path/to/Translation_Skills.zip` packages the same public inventory and reopens it to verify every manifest entry.

## Format and browser checks

Install optional fixture dependencies:

```bash
python3 -m pip install -r requirements-optional.txt
python3 tools/format_regression.py --output-root /path/to/work/formats
python3 tools/integration.py --output-root /path/to/work/integration
```

Format fixtures use python-docx, python-pptx and openpyxl. Legacy Office/OpenDocument generation needs LibreOffice, and RTF extraction can use macOS textutil. OCR uses an available local engine. Inspect the report to see the actual routes. Integration uses supplied fixture translations to test publishing; it does not measure fresh translation quality.

With a local Chromium browser:

```bash
python3 tools/reader_i18n_regression.py --output /path/to/work/reader --browser /path/to/chromium
python3 tools/editor_i18n_regression.py --output /path/to/work/editor-locales --browser /path/to/chromium
python3 tools/editor_regression.py --output /path/to/work/editor --browser /path/to/chromium
python3 tools/layout_runtime_regression.py --output /path/to/work/layout --browser /path/to/chromium
python3 tools/asset_fidelity_regression.py --output /path/to/work/figures --browser /path/to/chromium
```

These checks cover locale controls, document invariants, image handling, common exports, pagination and source-relative figure colors. They use owned fixtures and browser emulation. Inspect actual source/output images separately where visual quality matters.

For complete translated projects, use `tools/full_document_editor_regression.py --project /path/to/project --output /path/to/fresh/evidence --browser /path/to/chromium`. It imports generated HTML from disk, compares reader/editor geometry, exercises layout controls and checks exports. Large documents need their own run; a small fixture does not establish memory behavior for every input.

## PDF corpus workflow

```bash
python3 tools/pdf_corpus_regression.py prepare --pdf-root /path/to/authorized/pdfs --output-root /path/to/work/corpus --seed 173 --count 8 --scope full --language zh-Hans
```

The seed controls file selection. `--scope full` includes every page; the default `first-middle` scope selects page 1 and the lower midpoint. Preparation creates projects and tasks without filling translations.

Complete the [translation workflow](WORKFLOW.md), including source correction, both editions, semantic comparison, rendering and page review. Then run:

```bash
python3 tools/pdf_corpus_regression.py check --output-root /path/to/work/corpus
```

Missing translations, partial scope in a full run, stale evidence or missing outputs keep the regression incomplete. Successful extraction and nonblank PDFs alone do not establish semantic accuracy.

## Model reproduction

The [DOM ranker card](../skills/document-translation/assets/models/MODEL_CARD.md) identifies the bundled synthetic dataset and its evaluation. The [source model card](../skills/document-translation/assets/models/SOURCE_STRUCTURE_MODEL_CARD.md) explains the structure model and its limits. Source annotation, freezing, training and evaluation commands are in [structure training](../skills/document-translation/references/structure-training.md).

Use whole-source splits and retain declared lineage for repaired or converted copies. Private source documents and real-data annotations are not distributed. Reproducing that fit requires separately authorized material. Keep fresh-source evaluation separate from training and development results.
