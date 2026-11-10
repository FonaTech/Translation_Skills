# Missing PDF font maps

Use this path when a PDF looks readable but native extraction contains systematic
gibberish. More role/link training cannot repair an absent Unicode map. Inspect
the original raster and embedded font metadata first. Scanned pages and fonts
with an incorrect existing map remain unresolved; this tool deliberately
preserves existing maps. PDF OCR and page/table transcription are disabled.
Retain original artwork when native text is unavailable.

Native PDFs can contain both visible text and an existing invisible text layer.
The extractor consolidates exact coincident duplicates, including short headings
and equation numbers. A unique visible row can also retain a geometrically
coincident conflicting hidden row as an alternate; both transcripts and every
native row ID remain in the evidence. Preserved unknown font outlines may support
this association through the remaining known source text, but never decode the
unknown symbols. A conflicting alternate remains an open source-review finding.
Use the unchanged visible primary for reading, retain the original `native_lines`
for formula/prose boundaries, and do not treat row-accounting coverage as a
resolved wording conflict or semantic accuracy.

From the repository root:

```sh
python3 tools/recover_pdf_font_mapping.py PRIVATE/original.pdf \
  --reference-font LOCAL/reference.ttf \
  --output PRIVATE/recovered-copy.pdf --report PRIVATE/font-evidence.json
```

The optional FontTools dependency compares normalized embedded glyph outlines
and advance widths against locally supplied reference fonts. Supported sources
are Type0 Identity-H, CIDFontType2 fonts with explicit/default identity glyph
maps and no ToUnicode. It does not download or redistribute fonts. The original
PDF stays unchanged; the output must use a new path. Reference-font use and
redistribution remain subject to their own licenses.

Same-shape Unicode alternatives stay unresolved by default. After inspecting
the script, `--script Latin`, `--prefer-ascii` or `--canonical-space` may apply
explicit, recorded normalization policies. They are choices, not proof of the
original code point. Remaining glyphs require original-page inspection. A
`--reviewed-map PRIVATE/glyphs.json` file has this form:

```json
{
  "source_sha256": "<SHA-256 of original PDF>",
  "glyphs": [
    {
      "font_xref": 19,
      "cid": 80,
      "unicode": "U+00B5",
      "page": 1,
      "evidence": "Describe the inspected original glyph and its context."
    }
  ]
}
```

These are schema examples, not reusable mappings. The tool checks the source
identity and whether each reviewed glyph occurs on its recorded source page.
It records every glyph decision and reference-font hash. Unsupported or
ambiguous glyphs remain unresolved; never supply words from language-model
completion. The script compares all before/after pages at 72 dpi. Identical
pixels prove unchanged appearance at that resolution, not correct Unicode,
equation topology or a 99% content score. Inspect recovered text against every
source page before translation, including signs, units and reading order.

Record the original and all ancestor hashes on downstream annotation records:

```sh
python3 tools/prepare_structure_annotations.py PRIVATE/recovered-copy.pdf \
  --split train --source-parent-sha256 ORIGINAL_SHA256 \
  --output PRIVATE/recovered-evidence
```

Repeat `--source-parent-sha256` for further ancestors. A repaired/OCR/converted
copy remains the same source family for fitting and evaluation. A previously
analyzed source cannot become a new blind test through repair or conversion.
This provenance field records declared lineage; it cannot discover undisclosed
derivations automatically. Preserve the original failed test and report the
recovered-copy result separately as development evidence.
