# Layout and localization

One IR drives both editions. HTML embeds CSS/assets, escapes content, sets language/direction and provides responsive reading plus fixed print pages. A reference informs hierarchy, not text or existing defects.

Wait for fonts/images and measure real boxes. Keep headings with following content and figures with captions. Split table rows with repeated headers. Split oversized paragraphs at sentence/word/grapheme boundaries retaining IDs. Oversized atomic objects require readable rescaling or explicit handling, never hidden clipping.

Use requested A4/Letter. Reflow is normal after translation. Exact source-PDF redaction/overlay is a separate mode needing verified geometry; this package promises translated reflow with source locators, not pixel-identical replacement.

CJK needs glyph coverage; Arabic/Hebrew need RTL/shaping; Thai/Indic need shaping/segmentation. Isolate mixed code/numbers LTR. Embed only licensed/authorized fonts. PDF text extraction does not prove visible glyphs; inspect pages.

Editorial, accessible, compact and parallel profiles change presentation only. Check margins, page labels, cell positions, graph labels, captions and overfull lines. Blank space for an atomic figure may be better than unreadable shrinking. Mechanical bounds/coverage/hash checks complement visual review.

The generated reader toolbar and the standalone editor have separate interface-language preferences. Reader controls, including edition names, reading/page view, opening the editor, printing and popup notices, embed 16 locales. They use browser-provided system-language preferences and fall back to English; a saved manual selection takes precedence. Only the toolbar gets a new language/direction. Preserve document language, body text, printed labels and pagination when the interface changes. The toolbar is excluded from PDF printing. Run tools/reader_i18n_regression.py in a fresh external output directory to test the actual generated HTML and editor handoff.
