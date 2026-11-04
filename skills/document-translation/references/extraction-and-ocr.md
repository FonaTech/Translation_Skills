# Extraction, reconstruction and OCR

Inspect count, encryption, rotation, text coverage, images, tables and column geometry. Save all PDF page previews. Extraction can reorder columns, flatten superscripts, split ligatures and duplicate math glyphs. Visible pages override suspect hidden text.

Direct readers: PDF/PyMuPDF, DOCX/OOXML, static HTML, Markdown, UTF-8 text, CSV/TSV and raster images. Other formats can use a local converter/native export with version and intermediate hash recorded. Unsupported formats are not silently renamed. Encryption requires an authorized password.

Auto table detection is provisional. Compare cells, merged regions, signs, precision, column count and blank positions against the page. Exclude detected table areas from paragraph extraction. Screenshots preserve layout but do not translate table content; rebuild verified cells or label unresolved work incomplete.

Figure/vector content needs inspection. Ingestion keeps page previews and image crops and flags vector-heavy pages. `crop` adds a verified complete figure/equation including axis/panel labels, legends and units. Translate captions/labels using mappings or checked overlays; never alter data curves. State retained-label exceptions.

For low-text pages use `ocr` with installed Tesseract/language packs. Optional macOS Vision is a local fallback via the Swift helper. Both produce unreviewed candidates, not confidence guarantees. Verify names/quantities/tables/handwriting; never duplicate native text. Missing OCR is an explicit limitation.

Reading order supports auto/one-column/two-column. Spanning headings, sidebars, rotated text and forms need preview-based review. Preserve checked fields without guessing values. Extraction executes no macros/scripts. Archives need explicit safe member selection.
