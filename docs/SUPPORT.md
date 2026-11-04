# Supported routes and practical limits

| Input | Bundled route | Mandatory inspection |
|---|---|---|
| Native PDF | text blocks, page previews, image crops; one/two/auto column order; optional tables | ordering, tables, vector diagrams, math, hidden text, image placement |
| Scanned PDF / raster | preview + local Tesseract or macOS Vision OCR candidates | every OCR passage, names/numbers, duplicated source images, unreadable regions |
| DOCX | OOXML body paragraphs, tables, media, notes, headers/footers | numbering, fields, text boxes, equations, media anchors, merged cells |
| Static HTML | safe visible-structure text parser; scripts ignored | images, tables and interactive/hidden content; complex tables are provisional flattened text |
| Markdown / UTF-8 text | paragraphs / heading hints | code fences, lists and structure not fully parsed; agent repairs IR |
| CSV / TSV | cell-position table IR | delimiter, header choice, blank cells, ragged rows, units |
| PPTX | slide/shape text, tables, notes and common raster media in presentation order | grouped shapes, charts, SmartArt, animation and exact slide geometry |
| XLSX | worksheets and bounded cell tables; formulas remain protected source text and are never evaluated | styles/date serials, merged ranges, comments, charts, drawings, print areas; output is a reading edition, not a live workbook |
| ODT / ODS / ODP | native document structure, paragraphs, tables and common raster media | merged/repeated cells, formulas, footnotes, lists, embedded objects and anchors |
| EPUB | spine-order XHTML text; scripts are not run | navigation, out-of-spine files, images/SVG, notes and exact pagination |
| RTF / legacy DOC / XLS / PPT | local textutil or LibreOffice conversion, with source and intermediate hashes | conversion fidelity and unrepresented objects; host converter is required and no rename-as-conversion is used |

The standalone editor imports HTML and DOCX; it exports HTML, browser-print PDF, DOCX, ODT, Markdown, RTF, TXT and an editable project JSON. Every built translation HTML has an “open in layout editor” command that transfers the current HTML into the sibling editor copy. Keep `document-layout-editor.html` in the same folder as the translation HTML for this handoff. The editor sanitizes imported content, retains recognized source CSS/layout metadata, and supports direct text editing, common paragraph formatting, page size/margins/columns, image sizing, table row/column edits, measured pagination, bounded geometry-based layout suggestions and fallback preset ranking. Its offline optimizer uses deterministic DOM geometry rules; it does not include an ML model or provide semantic translation review.

This is a focused document-layout editor, not a full Word/Pages replacement. It does not provide complete tracked changes, comments/review workflows, arbitrary floating-object placement, equation editing, fidelity for every CSS construct, or a full desktop-publishing engine. DOCX export covers common paragraphs, basic formatting, tables and raster images; complex CSS, equations, footnotes, revisions, charts, nested tables and floating objects can simplify. PDF is produced through browser print. These exports are reading/editing artifacts. It does not export a recalculated XLSX workbook or a reconstructed PPTX slide deck.

No silent recovery from encrypted PDFs, missing OCR, missing glyphs or oversized objects. A readable reflowed translation is the default output; exact original-PDF replacement needs a separate geometry/redaction workflow and is not promised here. PDF output is static, not a fillable or legally usable replacement form. Source forms, signatures, seals and completed values must not be guessed.

The CLI does not guarantee arbitrary language fluency. Target language tags and RTL directions are configurable; actual glyph coverage, morphology, shaping, hyphenation and segmentation depend on fonts/browser/translator. Tested demos cover five languages, not every script. Unknown UI labels fall back to English; translating those labels is a presentation enhancement, not source-content translation.

Two-column flow is measured in the browser and balanced at source-page boundaries and around figures and tables. Wide objects span the page only when their source role or explicit presentation patch requires it. This is not a full desktop-publishing engine; inspect mixed column, RTL, broad table and floated-object layouts. Portrait A4/Letter are implemented. Extra-wide tables may require an explicitly designed landscape appendix or a column split with preserved keys.

The invoking model must visually compare original and rendered pages, record observed defects, apply a presentation-only patch and reopen the adjusted PDF pages. Automated measurements check text coverage, page bounds, empty pages and image placement, but cannot judge whether a layout is attractive or faithful to its source. See `skills/document-translation/references/visual-refinement.md`.

Sentence splitting is conservative and provisional: abbreviations/decimals, poems and table cells need contextual review. A unit may span several source sentences if splitting would destroy meaning. Alignment preserves source-to-target mapping, not a claim of universal grammatical 1:1 correspondence.

Author-owned cases are illustrative, not advice in law, taxation or medicine. Actual consequential translations retain source constraints; domain review can be requested separately. Source errors are disclosed, not silently corrected. No OCR confidence, back-translation score, number parity or successful release command proves semantic accuracy.
