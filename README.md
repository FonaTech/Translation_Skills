# Translation Skills

Translate documents into two complete editions, with HTML, PDF and a source-by-source comparison.

[中文说明](README_zh-CN.md) · [Installation](docs/INSTALL.md) · [Workflow](docs/WORKFLOW.md) · [Supported formats](docs/SUPPORT.md)

Yufeng Zhan · MIT · v1.0.3

Translation Skills adds a document translation workflow to Codex, Claude Code, OpenCode and Clouds_Coder. Use it for a single file or an ordered collection of manuals, reports, articles, stories or other documents. You choose the files, target language and intended reader.

The model in your client writes the translations. Local scripts extract the source, track each passage, check coverage and produce the reading editions. No separate translation API is required. Your client's own data handling still applies to the files it reads.

## The three outputs

| Output | Purpose |
|---|---|
| Faithful translation | A complete translation that preserves facts, tone, qualifications, numbers, notes and references. |
| Interpretive edition | The same content, expressed for the intended reader. It can clarify references and divide long sentences while retaining meaning and detail. |
| Source comparison | Original text alongside both translations, with stable passage IDs and page or element locations. Available as HTML, PDF and CSV. |

Tables, captions, footnotes and figure labels belong to the selected content too. Unreadable passages and labels retained in the original language are reported with their locations. Additional explanations appear as translator's notes.

## Get started

You need Python 3.10 or later. PDF output and figure checks use a local Chromium browser. PDF extraction requires PyMuPDF 1.26.4 or later. PDF scans without recoverable native text remain incomplete; optional non-PDF raster helpers are separate.

```bash
git clone https://github.com/FonaTech/Translation_Skills.git
cd Translation_Skills
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-core.txt
python3 -m playwright install chromium
```

The activation command is for macOS/Linux. In Windows PowerShell, use `.venv\Scripts\Activate.ps1`.

For a Codex project, preview the installation destination, then copy the skill:

```bash
python3 tools/install.py --targets codex --project /path/to/project
python3 tools/install.py --targets codex --project /path/to/project --apply
```

Choose your client in the [installation guide](docs/INSTALL.md). Existing skill folders are backed up before replacement. Keep the Python environment available to the client when it runs the helpers. Save translation projects outside the installed skill.

Then make a request such as:

> Use document-translation to translate /path/to/manual.pdf into Japanese for first-time users. Produce the faithful translation, interpretive edition and source comparison as HTML and PDF. Keep the warnings, tables and figure labels, and list anything unreadable.

## Changes in 1.0.3

- Added native table-cell linking and independent merged-cell topology checks. Supported spans survive HTML pagination and DOCX export.
- Improved source math glyphs, figure ownership and font-map recovery while retaining original evidence and unresolved findings.
- Separated repeated margin headers, footers and edge page numbers from body translation while preserving their source records.
- Added explicit UTF-8 file, console and subprocess handling, with Windows CP936 regression checks.
- PDF processing now uses native text, font outlines, vectors and geometry only. Unavailable text remains source artwork with an incomplete finding; PDF OCR and page/table transcription are disabled.

See the [changelog](CHANGELOG.md) and [workflow guide](docs/WORKFLOW.md).

## Standalone translator

The same [1.0.3 Release](https://github.com/FonaTech/Translation_Skills/releases/tag/v1.0.3) also offers **Chronos Document WebUI 1.1.4** as an experimental, separate download. It uses the author's [Project_Chronos](https://github.com/FonaTech/Project_Chronos) translation model for local English-to-Chinese PDF translation and provides a browser interface.

The skill uses the model in your agent client and produces both complete editions. The standalone program runs its own local model and produces a Chinese reading edition plus a bilingual comparison. Each has its own dependencies and installation. See the [program download and startup guide](docs/WEBUI.md).

## Layout and editing

The first layout follows the source's page proportions, hierarchy, columns and figure relationships. Translation can change text length and page breaks. The agent compares source and rendered pages, adjusts presentation and checks the result.

Generated HTML includes reader controls and a link to the bundled offline layout editor. Keep `document-layout-editor.html` beside the translation HTML to use that link. Both interfaces offer 16 languages; changing the interface leaves the document text unchanged.

The editor imports HTML and DOCX. It exports HTML, browser-print PDF, DOCX, ODT, Markdown, RTF, TXT and editable project JSON. Complex Word formatting and exact source-page reconstruction have limits; see [format support](docs/SUPPORT.md).

## Development

The skill lives in [`skills/document-translation`](skills/document-translation/SKILL.md). Its `references/` folder describes translation and review methods; `scripts/` contains the local workflow helpers. Repository-level `tools/` handles installation, validation, model training and packaging.

```bash
python3 -m pip install -r requirements-optional.txt
python3 tools/validate.py
python3 -m pip install pytest
python3 -m pytest tests -q
python3 tools/checksums.py
```

See [reproducible checks](docs/REPRODUCIBILITY.md) and [contributing](CONTRIBUTING.md). Automated tests cover specific structural and format behavior. Translation meaning and rendered pages still need direct review.

## License

Original code, skill instructions, model parameters and author-owned fixtures are released under [MIT](LICENSE). Input documents and dependencies retain their own licenses. See [third-party notices](THIRD_PARTY_NOTICES.md).
