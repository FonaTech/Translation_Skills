# Review and release

Evidence-based stages: selected, extracted, translated, checked, built, visually reviewed, released. Unreadable content stays unresolved.

Extraction review covers all selected pages, ordering, running furniture, cells, crops and low-text warnings. Semantic review compares every original with both versions: omissions/additions, scope, modality, negation, numbers/signs/units/ranges, denominator/population, caveats, attribution, names, terms and references. Record legitimate localization differences. Do not auto-correct number warnings.

Mechanical audit checks IDs, source hashes, language completeness, row references, asset paths and manifest. Missing translations block release. Keep unresolved OCR/table/vector issues with locators. A selected excerpt is valid if labeled with full source count and exact scope; never call it a full translation.

Render all pages; inspect contacts and difficult full pages for invisible glyphs, clipped figures/tables, orphan headings, footers, blank pages and HTML/PDF parity. Visual review binds current artifact hashes. Release needs fresh full-scope extraction/semantic/visual records plus machine/layout checks. A review record is not a semantic guarantee.

Hand off formats, alignment, coverage and actual limits. Agent review is not human/certified/expert review. Tests cover fixtures, not universal performance. Do not publish or mutate global installation without instruction.

Prepare blank, snapshot-bound checklists with `scripts/review_evidence.py`. The invoking model must fill per-block extraction observations, both-edition observations for each unit, and per-page visual findings after opening source and rendered images. Release rejects a placeholder, count-only attestation or stale evidence. Do not infer universal certification from examples.
