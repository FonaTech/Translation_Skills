# Translation batches and rendered review

Use coherent batches, stable source IDs and source-based correction. The invoking client model supplies both translations; no separate translation endpoint is required.

## Before translating

Inspect selected source pages and extraction warnings. Correct reading order, duplicates, broken characters, table cells and figure/caption relationships against the page. Record source corrections separately and preserve legitimate fragments. Establish terminology from the supplied context.

## Packets and meaning

`translate.py tasks PROJECT --language TAG --size 12 --max-chars 6000 --context-chars 1000` emits source hashes, expected IDs, sentence hints and neighboring context. Smaller batches can help difficult material. Context is bounded; selected source units are not truncated. Persist completed IDs and resume pending work.

For each unit, retain actors, actions, conditions, scope, negation, uncertainty, comparisons, quantities, units, named components and references. Compare both editions directly with the source. Preserve printed terms and explicit abbreviation expansions; a source ambiguity belongs in a separate note until the page establishes an extraction error.

Packet claim-scope, quantity and source-edge excerpts help locate possible omissions. They are review prompts rather than a complete semantic inventory. Check the whole unit and its source page. Context can disambiguate a fragment but must not supply missing words or move content between unchanged IDs.

Preserve `source_hash` and `expected_ids`. Apply each expected ID once. A successful apply records text without establishing semantic correctness. Inspect audit and glossary warnings after each section; number differences need explanation rather than automatic replacement.

## Checked source joins

For a sentence or reference split across columns/pages, inspect every contributing source image. `translate.py join-source PROJECT PACKET.json` accepts source_hash, reviewer, reason, inspected evidence and ordered unit_ids. It joins existing untranslated prose, records contributor text/locations in source_segments and creates a new ID. Optional separators choose a space or no space at each boundary, such as within an intact DOI.

The operation rejects cross-document joins and skipped narrative content. It cannot supply missing words. Regenerate tasks, translate the new ID and review alignment. For long merged units, explicit alignment_groups must cover source sentences in order and match both complete translations.

## Render, edit and export

Start with source-adapted design. Inspect actual source and output images, describe a concrete defect, apply a presentation patch, rebuild and reopen the affected pages. A ranked template fallback requires a documented severe defect after a rendered adjustment. Model rankings and geometry scores do not replace page inspection.

Compare generated HTML opened from disk with the editor before and after changes. Check painted element positions, typography, page distribution, table column proportions and figure/caption placement. Manual locks and local formatting must survive optimization and exports. Retain colgroups on continued tables, source locations on split alignment rows and every contributor in merged source units.

Inspect PDF and DOCX exports in their actual readers. Verify text, captions, figure dimensions, fonts and native image fallbacks. Prefer a fresh page to shrinking a readable figure into the remainder of a crowded row. Existing document-title metadata or an explicit display override should guide titles.

Complete the block/unit/page review checklists after inspection. Content, layout or output changes require fresh evidence. Keep unresolved ambiguity attached to its location and report the remaining scope accurately.
