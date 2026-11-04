# Changelog

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
