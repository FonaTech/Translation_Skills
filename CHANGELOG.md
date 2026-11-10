# Changelog

## 1.0.3 — 2026-11-10

- Added native table-cell linking, merged-cell topology validation and supported DOCX spans.
- Improved source glyphs, restricted font-map recovery, hidden text-layer accounting and figure/raster ownership.
- Archived repeated margin headers, footers and edge page numbers outside body translation.
- Added explicit UTF-8 streams, file I/O and subprocess handling with Windows CP936 regressions.
- Disabled PDF OCR and agent page/table transcription; unavailable native text stays source artwork with incomplete findings.
- Raised the PyMuPDF minimum to 1.26.4 for native crop pruning.
- Added a separate Chronos Document WebUI 1.1.4 download using the author's Project_Chronos model. The skill installation and runtime remain independent.

## 1.0.2 — 2026-11-09

### Translation workflow

- Added a resumable workflow controller for source review, translation, rendering and evidence-backed delivery.
- Added checked source-review operations and source-bound page/table transcription.
- Preserved contributor IDs and locations when joining verified source fragments; refreshed parser layout maps after corrections.
- Added offline PDF structure proposals and retained an explicit native extraction route.
- Added optional recovery for supported missing PDF Unicode font maps, writing a separate repaired copy.

### Figures, layout and editor

- Added automatic figure crops with native text, font, coordinate and caption evidence.
- Improved multipart figures, caption boundaries, waveform/table distinctions and bibliography continuations.
- Fixed balanced-column height serialization that could create extra print columns or shrink PDF pages.
- Improved column geometry, short-table/heading placement, editorial notes and source-relative figure comparisons.
- Improved image handling in editor exports and made stale publishing artifacts trigger rebuilding.
- Updated macOS Vision OCR configuration and retained source-reviewed transcription when local OCR is unavailable.
- Retained signed PyMuPDF color normalization from 1.0.1.

### Distribution

- Removed generated demonstrations and outdated validation snapshots from the package.
- Kept only public skill resources, model assets, documentation, development tools and tests.
- Updated version metadata and the public-inventory checks used by checksums and release packaging.
- Installed optional development dependencies in CI so NumPy-based training tests run in clean environments.

## 1.0.1 — 2026-11-05

### Reader and editor

- Added 16 interface languages to generated HTML reader controls, with browser-language detection, English fallback and manual selection.
- Kept interface language changes independent of document text, direction and printed pages.
- Fixed editor pagination after HTML reimport and checked that the content area remains measurable.
- Added checks for JPEG/SVG colors, legacy PNG fallbacks and HTML/PDF/DOCX export.

### Figures and pagination

- Fixed inverted CMYK and explicit Decode colors through PDF-context decoding, preserving soft masks and original dark artwork.
- Compared figures with source crops in browser and print rendering, including PNG fallback checks and evidence freshness.
- Fixed trailing blank pages, including pages with a white vector fill.
- Normalized signed PyMuPDF color values before selecting a document accent color.

### Workflow and distribution

- Included the portable dual-edition workflow, source alignment, review records, local OCR routes and four-client installer.
- Added a seeded PDF corpus regression tool with explicit excerpt/full-document scope and review checks.
- Included the offline editor, measured layout helpers and synthetic layout-ranker data.
- Reorganized the English and Chinese guides around installation and use, corrected review-evidence commands and clarified format/release limits.
