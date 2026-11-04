# Validation record

Last checked: 2026-11-05.

Environment: macOS on arm64, Python 3.10.20, PyMuPDF 1.25.2, Playwright 1.62.0, PyYAML 6.0 and Pillow 11.2.1. Browser checks used local Google Chrome in headless mode.

| Check | Result | Scope |
|---|---|---|
| `tools/validate.py` | Passed | Frontmatter, local Markdown links, JSON/Python syntax, metadata, versions and private-path scan |
| Skill Creator `quick_validate.py` | Passed | Skill naming, frontmatter and scaffold checks |
| Unit tests | 63 passed | Packet integrity, source scope, layout invariants, reader controls, vector/color handling and release checks |
| `tools/verify_platform_contract.py` | Four clients passed | Isolated copies and metadata for Codex, Claude Code, OpenCode and Clouds_Coder |
| `tools/reader_i18n_regression.py` | 166 checks passed | Generated reader controls, 16 locales, desktop/mobile emulation, document invariants and editor handoff |
| `tools/editor_i18n_regression.py` | 152 checks passed | Editor locales, responsive controls, document invariants and common exports |
| `tools/asset_fidelity_regression.py` | 31 checks passed | Author-owned color/vector fixtures, browser/PDF appearance, compatibility fallbacks and editor round trips |
| `tools/format_regression.py` | 18 fixtures passed | Native and conversion-backed extraction; local LibreOffice/textutil and macOS Vision routes |
| Gallery navigation | 83 local links resolved | Example-page links and images |

The unit run exposed signed PyMuPDF color values being compared as RGB values. Normalizing those values fixed accent-color selection; the existing regression then passed.

## What remains outside this run

The four clients were checked through installation copies, without interactive end-to-end sessions. Format fixtures tested extraction and structure without generating fresh translations. Browser locale checks used Chromium emulation. Translation accuracy for arbitrary documents or languages was not measured in this run.

The current visual-checklist helper requires PDF source previews. Non-PDF inputs need additional native-source visual evidence, and projects without PDF previews cannot complete that helper. This release limitation is described in the support and workflow guides.

## Earlier public-source examples

The [source record](public-test-provenance.json) identifies earlier W3C, IRS W-9 and National Archives tests. It distinguishes the complete single-phrase fixture, six selected form excerpts and an unsuccessful handwriting OCR trial. Those source downloads and translation reviews were not repeated in this run. Raw third-party PDFs are excluded from the package.
