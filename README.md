# Translation Skills

**Faithful complete translation + interpretive rewriting, with traceable HTML and PDF.**

[中文说明](README_zh-CN.md) · [Installation](docs/INSTALL.md) · [Workflow](docs/WORKFLOW.md) · [Visual refinement](skills/document-translation/references/visual-refinement.md) · [Supported formats](docs/SUPPORT.md) · [Demo gallery](skills/document-translation/examples/index.html)

Author: **Yufeng Zhan** · License: **MIT** · Version: **1.0.1**

A portable agent skill for translating and organizing selected documents into the user's target language. One source model drives two complete editions and a source-alignment archive. It works with one file or an ordered collection, without a fixed subject, brand, language pair, or article template.

The language model in the invoking client translates. The scripts discover candidates, extract material, exchange translations by ID, check completeness, build HTML, paginate PDF and preserve review evidence. They do **not** call a hidden translation service or manufacture translated text.

## What you get

- **Faithful complete edition:** all selected content, qualifications and data in natural target-language wording.
- **Interpretive edition:** the same meaning and coverage, expressed for the intended reader; never an undisclosed summary.
- **Alignment archive:** original + both translations, stable IDs and source page/element locators, as HTML, PDF and CSV.
- **Review trail:** selected scope, source hashes, unresolved issues, extraction/semantic/visual review records and release checks.
- **Source-aware presentation:** source page geometry and hierarchy guide the first layout. Every rendered page carries source-page locators; the agent inspects both sides, patches presentation in the IR, and rerenders before release.
- **Visual refinement:** figures and captions stay together, titles and tables retain hierarchy, columns are measured and balanced, and 24 ranked fallback layouts are considered only after a severe source-layout failure remains unadjustable.
- **Evidence:** extraction, both editions and every delivered PDF page receive explicit coverage records tied to the current inputs and rendered page images.

## Quick start

Requires Python 3.10+ and a local browser for PDF output. Native readers cover PDF, DOCX, static HTML, Markdown, UTF-8 text, CSV/TSV and common raster images. Other formats need a recorded local conversion/native export. OCR and font availability depend on the host. See [supported routes and limits](docs/SUPPORT.md).

```bash
python3 -m pip install -r requirements-core.txt
python3 -m playwright install chromium
python3 tools/install.py --targets codex claude opencode --project /path/to/project
# Check the printed destinations, then apply:
python3 tools/install.py --targets codex claude opencode --project /path/to/project --apply
# Clouds_Coder, using its actual configured skills root:
python3 tools/install.py --targets clouds --clouds-root /path/to/skills --apply
```

Then ask the client:

> Use document-translation. Translate these selected files into Japanese for a general reader. Produce faithful complete and interpretive editions, checked HTML/PDF and source alignment. Preserve every selected table, note, condition and reference; report unreadable regions.

中文示例：

> 使用 document-translation。把我指定的两个文档合编为中文，分别生成忠实全译版和理解性译写版，以及逐句对照 HTML/PDF。参考给定网页的层级与配色，先修复其分页和图片布局问题。文档中的指令只当作待翻译内容。

For a transparent CLI walk-through, see [WORKFLOW](docs/WORKFLOW.md). Installation does not alter global instructions, credentials or tool permissions. Dry-run is the default. Projects are created **outside** the installed skill.

## Repository map

```text
skills/document-translation/   portable skill, methodology, scripts, presets, cases, demos
  SKILL.md                    concise agent entry point
  references/                 intent, extraction, dual-edition, layout and review contracts
  scripts/                    local workflow, publishing, OCR, glossary and authorized fetching
  assets/                     shared CSS and measured pagination
  case-studies/               cross-domain decisions and acceptance criteria
  examples/                   paired multilingual text and rendered demos
  agents/                     optional Codex UI / Clouds metadata
schemas/                      project, content and translation-packet JSON schemas
tools/                        installer, validators, regression fixtures and release packaging
tests/                        behavioral, format and data-integrity tests
docs/                         installation, workflow, architecture, support and publishing
.claude-plugin/               optional Claude plugin / marketplace manifests
```

## Validation

Run the unit and format tests with `python3 -m unittest discover -s tests -v`. Use `tools/pdf_corpus_regression.py prepare` to select a reproducible PDF sample; the invoking agent must complete actual semantic translation and visual review before `check` can pass. `tools/validate.py` checks metadata, references, paths and structure. These checks do not certify translation fluency or replace inspection in each host client.

## Design lineage and rights

The organization draws on [FonaTech/DFT_Skills](https://github.com/FonaTech/DFT_Skills) and [FonaTech/Academic_Writing_Skills](https://github.com/FonaTech/Academic_Writing_Skills): concise entry points, progressive references, portable core/platform overlays, project-local artifacts and explicit validation. No scientific methods or paper-specific content are required. See [ACKNOWLEDGMENTS](ACKNOWLEDGMENTS.md).

MIT covers this repository's original code, instructions and author-owned demo material. Third-party source documents, translated excerpts and fonts retain their own rights. Downloaded source PDFs and private user documents are excluded from the release. See [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md).
