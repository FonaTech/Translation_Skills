# Reliable translation with limited model capacity

The quality floor comes from small coherent batches, explicit source boundaries and verified repair. Mechanical checks cannot certify translation accuracy. Use the invoking client model; no separate translation service is required.

## Inspect before translation

Inspect every selected source page and extraction warning. Repair damaged reading order, duplicated table text, broken characters and figure/caption placement against the page. Record source corrections separately; never improve the author's argument during extraction repair. Preserve legitimate fragments. Establish a small project glossary from the supplied context.

## Bounded packets

`translate.py tasks PROJECT --language TAG --size 12 --max-chars 6000 --context-chars 1000` emits source hashes, expected IDs, sentence hints and edition contracts. For complex material, lower the size to 3–6 units and read the surrounding paragraph. Larger coherent batches are possible for capable models, with the same checks. The task index supports resuming only pending IDs. Context-only neighbors are clipped to the context budget; selected source units are never truncated. A single oversized unit is emitted intact rather than summarized. Do not summarize a long unit to fit context.

1. Identify actor, action, object, conditions, scope, negation and uncertainty. Verify numbers, signs, units, names and references.
2. Translate faithfully from the visible source. Do not complete fragments, supplement reasoning or explain sound prose. Put source uncertainties in separate notes.
3. Write the interpretive edition from the same facts and qualifications. Improve expression without summarizing, omitting or inventing.
4. Compare both strings back to the source. Resolve added explanations, omitted conditions, changed agents, reversed comparisons and strengthened claims before applying.
5. Retain the source hash and expected IDs; apply every expected ID once. Apply success is not semantic review.

Run audit and optional glossary checks after each section. A number warning requests inspection, not automatic correction. Save progress by IDs and resume missing work. Never fill incomplete translation by copying source text or inserting placeholders. The task generator does not attest review.

## Render and repair

Start with the source-adapted design. The offline model ranks measured presentation candidates; independent hard gates reject text loss and overflow. The current agent opens actual source/output images, identifies concrete defects, applies presentation-only refinements, rerenders and reinspects. Only severe documented defects with no safe remaining adjustment permit ranked template fallback. Select the closest compatible template.

The final gate enumerates every selected source block, translated unit and delivered page. Missing or stale evidence blocks release. If ambiguity cannot be resolved, report the exact incomplete scope. Describe the remaining uncertainty with its source location.
