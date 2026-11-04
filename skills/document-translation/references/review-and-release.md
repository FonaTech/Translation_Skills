# Review and release

Review extraction, translation meaning and rendered pages before packaging a project. Keep unreadable or ambiguous content attached to its source location.

## Extraction

Compare every selected source block with the extraction. Check reading order, repeated headers and footers, table cells, figure crops, formulas and low-text warnings. A selected excerpt is valid when its exact scope and full source page count are recorded.

## Meaning

Compare each source unit with both editions. Look for omissions, additions, changed scope, modality, negation, numbers, units, conditions, uncertainty and attribution. Explain legitimate localization differences and number warnings rather than changing text simply to clear the audit.

## Rendered pages

Open source previews and every delivered PDF page. Check visible glyphs, figure details, table continuation, headings, footers, page edges and HTML/PDF consistency. Inspect the source crops and final figure placements alongside `reports/asset-fidelity.json`.

Build/render compare retained-original PDF graphics with source crops and check PNG compatibility fallbacks. Missing, stale or failing figure evidence prevents release. Intentionally translated graphics and non-PDF sources still need native-source comparison.

## Record the findings

Prepare blank checklists with `scripts/review_evidence.py`. Fill block-level extraction observations, observations for both editions of every unit, and source/output page observations after inspection. Record them with `translate.py review --evidence FILE`.

The visual helper currently gathers source images from PDF previews. Non-PDF sources need additional native-source visual evidence; projects without PDF previews cannot complete the current helper. Report this limitation when it prevents release.

Release checks require current extraction, semantic and visual records, complete translations/alignment, resolved source issues and current layout/asset reports. Content changes invalidate review snapshots; changed outputs invalidate visual evidence. Checklist completeness establishes recorded coverage, not translation accuracy.

Deliver the requested files with the selected scope, reviewer identity and unresolved limits. Publication or upload requires user authorization.
