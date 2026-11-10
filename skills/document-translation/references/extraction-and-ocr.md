# Extraction, reconstruction and OCR

Inspect count, encryption, rotation, text coverage, images, tables and column geometry. Save all PDF page previews. Extraction can reorder columns, flatten superscripts, split ligatures and duplicate math glyphs. Visible pages override suspect hidden text.

If visible text is readable but the native layer is systematically garbled,
inspect missing font maps before training or translating. See
[font-map recovery](font-map-recovery.md) for exact-outline recovery to a separate
copy, explicit ambiguity policies, source-page checks and source-family lineage.
It supports a restricted font class, not arbitrary encoding repair.

Direct readers: PDF/PyMuPDF, DOCX/OOXML, static HTML, Markdown, UTF-8 text, CSV/TSV and raster images. Other formats can use a local converter/native export with version and intermediate hash recorded. Unsupported formats are not silently renamed. Encryption requires an authorized password.

Auto table detection is provisional. Compare cells, merged regions, signs, precision, column count and blank positions against the page. Exclude detected table areas from paragraph extraction. Screenshots preserve layout but do not translate table content; rebuild verified cells or label unresolved work incomplete.

Figure/vector content needs inspection. Ingestion records provisional vector regions. Read [vector-figures.md](vector-figures.md) for complete checked SVG/PNG crops, label coverage, caption binding and editor/export limits. Never alter data curves; state retained-label exceptions.

PDF processing never invokes OCR, including on raster tables or page crops, and rejects the PDF `ocr` command. Use native text, embedded font outlines, vector artwork and measured geometry. Existing embedded invisible text is native source evidence and may conflict with visible text. Scans or outlined tables without recoverable native text retain complete source artwork and an open unavailable-text finding; they are not certified as fully translated. Do not route PDF text through host-agent transcription. The optional legacy OCR/transcription helpers are for separately selected non-PDF raster inputs only.

Reading order supports auto/one-column/two-column. Spanning headings, sidebars, rotated text and forms need preview-based review. Preserve checked fields without guessing values. Extraction executes no macros/scripts. Archives need explicit safe member selection.

PDF ingestion defaults to the bundled experimental learned role/link/contextual-region parser. `ingest --structure ml --structure-model PATH` explicitly selects another compatible model; `--structure native` selects the native fallback. Use it on a new project and compare the
native evidence ledger with the complete source pages before translating. Read
[structure training](structure-training.md) for the role ontology, immutable
annotations, whole-source splits, retraining and end-to-end acceptance. Its
scores and native accounting do not certify structure or semantic correctness.

## Display equations and inline notation

Use the learned role/region heads to identify standalone display equations,
then apply page, column, number and neighboring-prose constraints. Each exported
display records its model hash, neural seed line IDs, source bounding box and
unchanged source artwork. A crop is visual preservation, not recovered LaTeX.
Measure display detection against independently reviewed source regions and
measure exported appearance separately; neither score substitutes for the other.

Inline notation follows the ordinary text path. Preserve native characters and
font/baseline evidence, keep their literal intervals outside generative
translation, and compose them into the translated sentence with text, italic,
subscript and superscript styling. Measured inline fractions use positioned text
and the evidenced fraction rule, without individual formula image crops.
Do not infer missing symbols, algebra or a denominator from surrounding prose.
Unresolved Unicode mappings remain explicit extraction findings.

Numbered display regions retain upright identifiers beside measured relation
operators and descriptive subscripts at their original positions. The same
words in a figure or an ordinary clause are not display evidence. The region
decoder combines these source constraints with the numerical model; successful
cropping does not certify a missing or incorrectly assigned formula fragment.

Use exact source outline bounds when an extended mathematical glyph's declared
font box understates its ink. Keep both geometries and identify a derived math
axis as an estimate. Adjacent display isolation requires disjoint native-row
ownership; role predictions alone cannot authorize removing neighboring text.
An aligned final cases branch needs an actual connected source brace and another
branch from the same native object. Never infer an absent condition or symbol.

Measured detached inline accents and fractions can rejoin a unique owning prose
gap while preserving their original native IDs and source character intervals.
These are geometry repairs, not mathematical transcription. Preserve verified
unknown-font outlines as bounded inline runs; scale a wide run proportionally to
its available column instead of clipping its final characters. Appearance
retention does not recover unreadable text or establish a complete translation.

Actual-PDF verification checks each glyph occurrence independently on the same
physical sampling grid. A verification-scoped cache may reuse immutable display
lists, with source identity, transforms and exclusions in its keys; it must not
reuse pixel verdicts or relax thresholds. Check source hashes before and after
placement and verification. The owned `tools/native_math_regression.py` browser
fixture checks narrow-column reflow and original-PDF glyph appearance; it is not
a document-model accuracy benchmark.

Captioned native tables can use the learned table-row assignments with empty
vertical gutters and repeated stub-column rows to propose a cell map. The map
must account for each physical row exactly once. A single well-joined paragraph
still contributes its native row evidence to source-column inference.
Cell headers and descriptive text enter translation; isolated mathematical
cells, including conditional function definitions, retain their source artwork
with the source aspect ratio. A separate numerical cell-link model joins
source-supported wrapped records; ruled-grid constraints preserve recurring
columns and multi-tier/merged headers. Independent topology checks reject
overlapping owners and missing covered cells. Connected vertical merges stay
together during pagination; DOCX export preserves gridSpan/vMerge. See the
[table model card](../assets/models/TABLE_CELL_MODEL_CARD.md) for actual training
scope and limits. Partial hierarchical separators, diagonal headers and
uncertain gutters can still require complete source artwork with an open
unresolved-topology finding. A retained picture is not a translated table.

## Running headers and footers

The existing learned role/region heads are followed by a narrower physical
ownership check. Repeated normalized text must match an outer-margin slot on
another page; isolated page numbers require an outer edge position. Interior
body evidence and prose-continuation guards reduce accidental exclusion of real
text. Footnotes, captions, references, code, equations and source table regions
are protected. This additional classifier is a deterministic document-geometry
filter; the role model weights have not been retrained for furniture.

Excluded running furniture retains its original text, native row IDs, typography,
geometry and model decisions in `reports/page-furniture/`. It does not enter the
body translation task list. Source layout annotations show the archived regions.
These checks depend on the available pages: short excerpts with no repeated
context, unusual margin placement and genuine repeated prose require source
review. Do not report arbitrary header/footer accuracy from a fixture test.

When a native glyph has no reliable Unicode mapping, the parser can retain its
exact source font outline at the measured glyph origin. This adds no OCR or
guessed symbol: the transcript and unresolved finding remain unchanged. The
publisher composes that outline inline while ordinary surrounding prose is
translated. It rejects ambiguous, rotated or clipped outline matches. Missing
appearance evidence still blocks translation of the affected unit; a protected
placeholder alone never establishes a successful repair.
This check includes DEL and C1 control mappings as well as C0/replacement
characters. Their exact source outlines preserve appearance without asserting
that the intended Unicode symbol has been recovered.

For separately selected non-PDF raster inputs, legacy OCR recognition
confidence does not establish table-cell ownership. Empty or merged cells,
multiple recognition items in one cell, or inconsistent row baselines require
source-grid review. PDF tables never use these recognition helpers. Retain the
complete table artwork and its caption instead of sending a provisional
flattened grid into translation. Retained source artwork does not mean that
the table text was translated.
