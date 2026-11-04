# Vector figures and label translation

PDF vector drawings are page commands and may have no embedded bitmap. Ingestion records provisional connected regions in reports/vector-inventory.json, including sparse figures. Regions may split panels or capture table rules: inspect the full page before choosing complete figure bounds.

After inspecting the source, run:

    python scripts/translate.py crop PROJECT --document D001 --page 3 --bbox X0,Y0,X1,Y1 --width 170 --format auto

Auto preserves intersecting vector paths as static SVG with a source-rendered PNG fallback. Explicit svg fails when unsupported; png deliberately rasterizes. Rotated pages require normalization and visual checking or a recorded PNG fallback. Text is outlined to preserve source font appearance. Outlines are not editable or automatically translated text. Mixed figures retain bitmap pixel dimensions. Risky CMYK/ICC/Decode images are decoded inside a temporary copy of the source PDF and converted losslessly to RGB before SVG serialization. Never invert a standalone extracted JPEG or force genuine dark artwork to white. Soft masks and vector paths remain intact; the original PDF is never edited.

Compare all edges, panels, axes, legends, units, arrowheads, overbars and transparency. Bind the same-page caption and place the figure at the correct reading position. Account for every visible natural-language label as source units. A retained original plus translated label map is not in-place label replacement: record retained-original and disclose the exception. Replacing labels requires separate verified overlays; never change data curves or invent missing text. Faithful translation never completes the source.

HTML and Chromium PDF use SVG. Editor imports and HTML exports preserve supported static SVG. DOCX contains SVG and a PNG compatibility fallback, and both can be reimported. Whole-figure size and placement are editable; individual circuit paths and outlined labels are not Word shapes. Word/LibreOffice display requires native visual review. Compare source and rendered page images after layout changes; path counts do not prove semantic or visual fidelity.

## Mandatory source-appearance gate

Both `build` and `render` call `scripts/asset_fidelity.py`. It renders every retained-original PDF figure from its declared source page/bounds in opaque RGB, decodes the actual SVG/raster in Chromium, and compares source-relative color error and newly black regions. It also checks PNG compatibility fallbacks. Old SVGs migrate through the source-aware exporter. When SVG appearance still differs, use an opaque RGB PNG rendered from the same source crop and record the lost vector capability. This is an image-fidelity fallback, not permission to switch document templates.

Results live in `reports/asset-fidelity.json`, with source/asset/evidence hashes and comparison metrics. `release` rejects missing/stale coverage or failed final metrics. Out-of-page PDF image transforms are clipped to the actual visible page; wholly off-page/invalid crops stop the workflow. Do not treat metric success as label, extraction-completeness or aesthetic review. Compare panels, masks, small details and output-page placement visually.

For intentionally translated labels or sources without a comparable PDF crop, retain the native-source visual-review requirement. Never overwrite a translated graphic with its source just to pass pixel comparison. The existing page-evidenced visual review remains required. The editor rejects four-component JPEGs even with a spoofed MIME. A supplied static PNG fallback can be used for legacy import; otherwise the missing/unsafe image blocks export. HTML/PDF/DOCX exports recheck current images; DOCX compatibility images are generated from the browser-decoded current figure.

Run the author-owned regression in a fresh directory:

    python3 tools/asset_fidelity_regression.py --output /path/to/fresh-test-directory --browser /path/to/chromium

It exercises CMYK, explicit RGB/gray Decode, soft masks, original dark art, pure vectors, incorrect main/fallback images, stale evidence, HTML/PDF rendering, legacy editor import and DOCX round trips. Thresholds are conservative engineering tolerances, not calibrated guarantees for arbitrary PDFs or substitutes for source/output visual comparison.
