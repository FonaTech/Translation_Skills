# Formats and limits

[Installation](INSTALL.md) · [Workflow](WORKFLOW.md)

The CLI extracts source material into a common content model. The model in the client translates it, and the publishing helpers create reading editions. Extraction support and exact reproduction of the original file are different capabilities.

## Input formats

| Input | Extraction route | What to inspect |
|---|---|---|
| Native PDF | Model-proposed roles/links/regions, native text evidence, page previews and figure crops; optional native tables | Column order, hidden text, formulas, tables and vector figures |
| Scanned PDF | Original page artwork and available native evidence; no OCR or agent transcription | Unavailable text and incomplete translation scope |
| Non-PDF raster image | Legacy local recognition helpers, separate from PDF routes | Recognized text, quantities and unreadable regions |
| DOCX | OOXML paragraphs, tables, media, notes, headers and footers | Numbering, fields, text boxes, equations, anchors and merged cells |
| Static HTML | Visible text and structure; source scripts are ignored | Images, hidden content and tables; complex tables may be flattened |
| Markdown or UTF-8 text | Paragraphs and heading hints | Code fences, lists and other structure needing repair |
| CSV or TSV | Cell-position tables | Delimiter, headers, blank cells, uneven rows and units |
| PPTX | Slide and shape text, tables, notes and common raster media | Groups, charts, SmartArt, slide order and geometry |
| XLSX | Worksheets and bounded cell tables; formulas retained as source text | Date serials, merged cells, comments, charts and print areas |
| ODT, ODS or ODP | Document structure, paragraphs, tables and common raster media | Repeated/merged cells, formulas, notes and embedded objects |
| EPUB | XHTML text in spine order | Navigation, images, SVG, notes and omitted out-of-spine files |
| RTF or legacy DOC/XLS/PPT | Local textutil or LibreOffice conversion | Objects or formatting lost during conversion; a host converter is required |

Spreadsheet formulas are never evaluated. PowerPoint and spreadsheet inputs produce reading editions. They do not become a reconstructed slide deck or a recalculated workbook.

Encrypted PDFs need an authorized password. Optional non-PDF recognition engines and converters are installed separately. PDF extraction requires PyMuPDF 1.26.4 or later. Conversion records include source and intermediate hashes.

## PDF structure and font maps

Default PDF ingestion uses an offline model to propose roles, paragraph links and reading regions. `--structure native` retains the native extraction route. `--tables` in auto mode selects native cell extraction. Figure and table classifications, captions, columns and formulas remain reviewable proposals.

Systematically garbled text on a readable page may indicate a missing font map. The optional FontTools helper supports a restricted set of Identity-H/CIDFontType2 fonts and writes a new PDF. It retains existing maps and records ambiguous glyph decisions. See [font-map recovery](../skills/document-translation/references/font-map-recovery.md) and the [source model card](../skills/document-translation/assets/models/SOURCE_STRUCTURE_MODEL_CARD.md).

Supported native tables use a numerical cell-link model with source-rule and column constraints. Independent topology checks reject overlapping or incomplete merged cells. Unsupported hierarchical tables retain complete artwork and an unresolved finding. See the [table model card](../skills/document-translation/assets/models/TABLE_CELL_MODEL_CARD.md).

Repeated margin furniture is archived outside the body translation tasks. Source footnotes and prose continuations remain in scope. Source math glyphs may be retained by verified outlines; that preserves appearance without recovering unknown Unicode or mathematical meaning.

## Generated documents

The workflow produces faithful and interpretive HTML/PDF editions, plus a source comparison in HTML/PDF/CSV. HTML embeds its styles and assets. PDF uses browser pagination. A copy of `document-layout-editor.html` sits beside the HTML files for editing.

The layout begins with the source's proportions and hierarchy, then reflows the translated text. It can preserve source-page references without matching the original page count. A4 and Letter are available through the CLI; source-derived layouts can use source page dimensions. Wide tables, mixed columns, rotated content and large figures need inspection and may require restructuring.

The PDF output is static. A translated form does not retain interactive fields, signature validity or the authority of the original form. Exact replacement of text inside an original PDF requires a separate geometry and overlay workflow.

## Offline layout editor

| Operation | Formats |
|---|---|
| Import | HTML, DOCX |
| Export | HTML, browser-print PDF, DOCX, ODT, Markdown, RTF, TXT, editable project JSON |

The editor supports direct text editing, common paragraph formatting, page dimensions, margins, columns, image sizing and table row/column edits. Imported content is sanitized. Recognized layout styles and metadata are retained where supported.

Tracked changes, comments, equation editing and arbitrary floating-object placement are outside its scope. DOCX export handles common paragraphs, formatting, tables, raster images and supported static SVG with a PNG fallback. Equations, footnotes, revisions, charts, nested tables and complex CSS can be simplified. Inspect exports in the application that will be used to read them.

Automatic layout suggestions compare measured candidates with an embedded ranker. Manual control locks and independent content/geometry checks constrain those suggestions. Training used synthetic documents and engineering preferences. See the [model card](../skills/document-translation/assets/models/MODEL_CARD.md) for the data, evaluation and limits.

## Languages and fonts

Target-language tags and text direction are configurable. Translation fluency comes from the client model. Glyph coverage, shaping, segmentation and line breaks also depend on the installed fonts and browser. Inspect actual CJK, Arabic, Hebrew, Thai and Indic output where applicable.

The reader and editor offer 16 interface languages: English, Simplified Chinese, Traditional Chinese, Japanese, Spanish, Arabic, German, French, Portuguese, Italian, Russian, Korean, Hindi, Indonesian, Vietnamese and Turkish. Browser language preferences determine the initial selection, with English as fallback. A saved manual choice takes precedence. Interface changes preserve the document's text, language, direction and print layout.

Locale regression scripts exercise Chromium desktop/mobile emulation; they do not establish compatibility with every browser or operating system. Translation quality needs source-based review for the selected language.

## Figures and source comparison

Supported PDF vector paths can be retained as SVG with a source-rendered PNG fallback. Build and render compare retained-original PDF figures with source crops and record the results in `reports/asset-fidelity.json`. The workflow can use a source-rendered RGB crop when SVG appearance differs. See [vector figures](../skills/document-translation/references/vector-figures.md).

Outlined text remains part of the graphic. Translated captions or label maps do not replace those labels in place. Record retained-label exceptions, and inspect panels, axes, legends, units and transparency in the final export.

Alignment uses stable IDs and source locations. One original sentence may correspond to several translated sentences. Abbreviations, poems and table cells need contextual checking of the provisional sentence boundaries.

## Review and release

Extraction review covers the selected source content. Semantic review compares every unit with both editions. Visual review compares source previews with all delivered PDF pages. The release command checks coverage, unresolved issues and evidence freshness.

The visual checklist includes PDF page previews, available non-PDF previews or native source-file references. Compare non-PDF sources in their native reader when layout matters. A source hash identifies the file but does not establish that its layout was inspected.

Automated bounds, number, hash and image checks help locate problems. They cannot establish translation accuracy or prove that someone inspected a page. Unreadable text stays unresolved. Domain examples are fictional translation exercises; consequential documents may also need a qualified domain reviewer.
