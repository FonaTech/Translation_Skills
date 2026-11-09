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

For low-text pages use `ocr` with installed Tesseract/language packs. Optional macOS Vision is a local fallback via the Swift helper. Both produce unreviewed candidates, not confidence guarantees. Verify names/quantities/tables/handwriting; never duplicate native text. If local OCR is unavailable, the invoking multimodal agent can submit literal, source-bound transcribe-page or transcribe-table operations; see [agent-workflow.md](agent-workflow.md). Unreadable content remains a disclosed limitation.

Reading order supports auto/one-column/two-column. Spanning headings, sidebars, rotated text and forms need preview-based review. Preserve checked fields without guessing values. Extraction executes no macros/scripts. Archives need explicit safe member selection.

PDF ingestion defaults to the bundled experimental learned role/link/contextual-region parser. `ingest --structure ml --structure-model PATH` explicitly selects another compatible model; `--structure native` selects the native fallback. Use it on a new project and compare the
native evidence ledger with the complete source pages before translating. Read
[structure training](structure-training.md) for the role ontology, immutable
annotations, whole-source splits, retraining and end-to-end acceptance. Its
scores and native accounting do not certify structure or semantic correctness.
