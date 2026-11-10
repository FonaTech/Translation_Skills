# Resumable invoking-agent workflow

Run `python3 scripts/translate.py workflow PROJECT --advance --browser BROWSER` after init/ingest. `reports/workflow.json` records the current source/content hashes, stage and next action. The controller runs deterministic stages; the model already running in the client performs semantic and visual decisions. No Ollama, API key, auxiliary language model or human-operated intermediate step is required. Continue within the user's authorized scope until `stage: released` and `complete: true`. A task JSON file is an exchange interface, not a completed translation.

## Stage actions

| Stage | Current invoking agent action | Resume |
|---|---|---|
| ingest | Ingest explicitly selected originals; preserve hashes and scope. | workflow --advance |
| source-review | Inspect source previews, model proposals, native evidence and crop context. Return checked generic operations below. | source-review PROJECT --packet CHECKED.json, then workflow --advance |
| translate | Read coherent task packets; write actual faithful and interpretive translations for every expected ID. | apply PROJECT PACKET.json, then workflow --advance |
| build / render | Controller builds and measures source-preserving candidates. | workflow --advance |
| visual-repair | Inspect failed candidate pages, fix the root cause through generic presentation/source exchanges and rerender. Preserve failed evidence. | refine PROJECT PATCH.json, then workflow --advance |
| agent-review | Inspect every enumerated block, both editions and all rendered PDF pages. Complete explicit extraction, semantic and visual evidence checklists. | review PROJECT --kind KIND --reviewer LABEL --scope all --notes OBSERVATIONS --evidence CHECKED.json |
| release-repair | Read reports/release.json; repair exact failing gates and renew affected evidence. | workflow --advance |
| released | Deliver HTML/PDF, alignment and sibling editor, with honest scope/limits. | complete |

No action silently certifies itself. Unreadable source, missing authorized password or unavailable rendering capability must be reported accurately; do not invent content or a pass. Platform permissions still apply. Unexpected exceptions retain their traceback. Recorded failed layout candidates become repair tasks.

## Source review exchange

`source-review PROJECT` prepares context and a blank packet. Return only `schema_version`, `source_hash`, `reviewer`, `evidence` and `operations`. Evidence paths are project-relative, inspected files; the application records their hashes. Every operation needs a substantive `observation`. Applications are atomic and stale source hashes fail. Correct source before translation. Do not generate a per-document repair script, edit finished HTML or reconstruct a plausible source paragraph.

- `correct-unit`: exact `unit_id`, `before` and literal visible `after`; preserves correction history.
- `classify-block`: existing `block_id`, `type` (paragraph/heading/reference), presentation `role`, optional heading `level` 1–6.
- `regroup-units`: exact current `before_ids`, `block_id`, and ordered zero-based `groups`, e.g. `[[0],[1,2],[3]]`. Every unit appears once; concatenation adds spaces only.
- `order-blocks`: `document_id`, `page`, exact current `before_ids` and a complete `after_ids` permutation. No dropping or duplicating blocks.
- `asset-label-policy`: `block_id`, `policy` (retained-original/no-text/translated) and source-based `note`. A translated-label claim requires actual label units; untouched outlines are original labels.
- `transcribe-table`: legacy non-PDF raster sources only; PDF sources are rejected. Inspect the source-bound evidence and supply literal rectangular rows including empty cells. Caption/page ownership must agree; existing tables cannot be duplicated.
- `transcribe-page`: separately selected non-PDF raster inputs only; PDF sources are rejected. Use the original image as evidence and source-pixel geometry. This operation is never a PDF extraction fallback.
- `resolve-issue`: exact `issue_index` and the actual evidence-backed disposition. Resolving a warning does not create missing content or review evidence.

The bundled parser proposes text roles, joins and spatial regions. The figure model proposes caption ownership and source crops; raster ownership isolation avoids including adjacent art while retaining complete owned panels. Crop text/font/coordinates remain archived. The parser layout map is refreshed after checked source changes.

For an inspected continuation across text blocks, use `join-source PROJECT PACKET.json`. The packet contains source_hash, reviewer, reason, inspected evidence paths and merges with ordered unit_ids and observation. Optional separators contains one empty string or single space per boundary, permitting an intact DOI without adding words. Join only one document and one prose/reference family, before translating affected units. The operation retains every contributor/locator, forbids skipping intervening narrative or references, creates a new unit ID and refreshes any existing parser/layout map. Translate the new ID and resume workflow; never concatenate translated HTML by hand.

## Translation and rendering invariants

Faithful output never completes an incomplete source or adds explanations. Interpretive output preserves all supported content. Contradictions and optional context belong in labeled notes outside the prose; alignment preserves these notes too. Protected code, equations, units, blanks and literal N/A remain traceable.

Build and render record a fingerprint of publishing scripts/assets and artifact hashes. Missing/changed outputs or code trigger rebuilding/rerendering. Old completed checklists are archived before replacement when rendered evidence changes. Multipart figures share one atomic group and caption; headings reserve following content and small tables prefer a fresh region to unnecessary fragmentation. Oversized tables/units remain splittable. These rules are measured, not a substitute for inspecting actual pages.

Review source-preserving adjustments first. Only after the invoking agent observes a severe, unadjustable failure may it record layout-review rejection and rank the closest of 24 presets. Rank values are similarity/engineering estimates, not calibrated probabilities of aesthetic quality. Rendering, source pixel gates and semantic/visual review still apply after fallback.

All four adapters load this same contract. Filesystem installation tests do not establish live execution inside four clients; report only exercised environments.
