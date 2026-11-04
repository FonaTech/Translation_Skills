# Translation Skills

Translate documents into two complete editions, with HTML, PDF and a source-by-source comparison.

[中文说明](README_zh-CN.md) · [Installation](docs/INSTALL.md) · [Workflow](docs/WORKFLOW.md) · [Supported formats](docs/SUPPORT.md) · [Examples](skills/document-translation/examples/index.html)

Yufeng Zhan · MIT · v1.0.1

Translation Skills adds a document translation workflow to Codex, Claude Code, OpenCode and Clouds_Coder. Use it for a single file or a collection of manuals, reports, articles, stories or other documents. You choose the files, target language and intended reader.

The model in your client writes the translations. Local scripts extract the source, track each passage, check coverage and produce the reading editions. No separate translation API is required. Your client's own data handling still applies to the files it reads.

## The three outputs

| Output | Purpose |
|---|---|
| Faithful translation | A complete translation that preserves facts, tone, qualifications, numbers, notes and references. |
| Interpretive edition | The same content, rewritten for the intended reader. It can clarify references and divide long sentences while retaining the source's meaning and detail. |
| Source comparison | Original text alongside both translations, with stable passage IDs and page or element locations. Available as HTML, PDF and CSV. |

Tables, captions, footnotes and figure labels belong to the selected content too. Unreadable passages and labels retained in the original language are reported with their locations. Additional explanations appear as translator's notes.

## Get started

You need Python 3.10 or later. PDF output and figure checks use a local Chromium browser. OCR is optional and needs Tesseract or macOS Vision.

```bash
git clone https://github.com/FonaTech/Translation_Skills.git
cd Translation_Skills
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-core.txt
python3 -m playwright install chromium
```

The activation command above is for macOS/Linux. On Windows, use `.venv\Scripts\Activate.ps1` in PowerShell.

For a Codex project, preview the installation destination, then copy the skill:

```bash
python3 tools/install.py --targets codex --project /path/to/project
python3 tools/install.py --targets codex --project /path/to/project --apply
```

Choose your client in the [installation guide](docs/INSTALL.md). Existing skill folders are backed up before replacement. Keep the repository's Python environment available to the client when it runs the helpers.

Then make a request such as:

> Use document-translation to translate /path/to/manual.pdf into Japanese for first-time users. Produce the faithful translation, interpretive edition and source comparison as HTML and PDF. Keep the warnings, tables and figure labels, and list anything unreadable.

Translation projects are saved outside the installed skill. For command-line use, follow the [workflow guide](docs/WORKFLOW.md).

## Layout and editing

The first layout follows the source's page proportions, headings, columns and figure relationships. Translated text can take more space, so page breaks may change. The agent compares the source and rendered pages, adjusts the layout and checks the result.

Generated HTML includes reader controls and a link to the bundled layout editor. The editor works offline and supports text edits, page settings, images and tables. Keep `document-layout-editor.html` beside the translation HTML to use that link. The reader and editor offer 16 interface languages; changing the interface leaves the document text unchanged.

The editor imports HTML and DOCX. It exports HTML, browser-print PDF, DOCX, ODT, Markdown, RTF, TXT and editable project JSON. Complex Word formatting and exact source-page reconstruction have limits; see [format support](docs/SUPPORT.md).

## Try the examples

Download or clone the repository, then open [the example gallery](skills/document-translation/examples/index.html) in a browser. GitHub displays HTML source rather than running the gallery. Each example also has PDFs you can preview directly on GitHub.

The gallery contains Chinese, Japanese, Arabic, Spanish and French examples, plus scan reconstruction, figure labels and selected public-PDF excerpts. These are sample outputs; they do not establish translation quality for every language or document.

## For contributors

The skill lives in [`skills/document-translation`](skills/document-translation/SKILL.md). Its `references/` folder describes translation and review methods; `scripts/` contains the local workflow helpers. Repository-level `tools/` handles installation, checks and packaging.

```bash
python3 tools/validate.py
python3 -m unittest discover -s tests -v
python3 tools/checksums.py
```

See [reproducible checks](docs/REPRODUCIBILITY.md), [architecture](docs/ARCHITECTURE.md) and [contributing](CONTRIBUTING.md). Automated checks cover structure, coverage and specific format cases. Translation meaning and rendered pages still need direct review.

## License

Original code, skill instructions and author-owned examples are released under [MIT](LICENSE). Input documents, third-party excerpts and dependencies retain their own licenses. See [third-party notices](THIRD_PARTY_NOTICES.md).
