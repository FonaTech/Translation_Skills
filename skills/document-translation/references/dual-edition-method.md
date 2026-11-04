# Two editions from one source

Read coherent sections with adjacent definitions/captions/tables. Establish faithful meaning first, then interpretive prose against both source and faithful edition. Factual corrections propagate to every language and edition.

Faithful retains actor/action/object, modality, negation, causal versus correlational wording, magnitude, time, conditions, exclusions, definitions and uncertainty. Natural grammar is welcome. Retain quotations and attribution. Do not remove repetition merely for elegance.

Interpretive may explain source-supported terms, break long attribution chains and clarify referents. Reorganize cause/process/result only if supported. Keep all examples/warnings/qualifications. External context requires a labeled sourced note, separate from the author's claim.

Tone follows content: poems retain imagery; contracts retain defined terms/obligations; manuals retain warning levels/order; reports retain accounting scope; research retains populations/uncertainty. No domain has special privileges in the pipeline.

For consequential clauses retain the translated clause then explain separately. Never modify dosage, rights, tax conditions or safety thresholds for friendliness. Do not add advice.

Alignment preserves IDs across one-to-many sentence renderings. Merge/split edits record covered IDs and reset reviews. Back-translation can expose ambiguity but is not correctness proof. Number parity is triage: dates, spelled numbers and localized notation need review.

## Source boundaries and complete sentences

The faithful edition translates only the visible selected source. Never finish an unfinished sentence, infer missing text from a later section, repair an author's argument, or add explanatory prose to otherwise readable content. Preserve a visible fragment as a fragment and identify the selected scope. Fix extraction errors only by comparison with the original page and keep a separate before/after correction record. Keep any translator observation outside the translated prose, labeled as a note. The interpretive edition may reorganize supported wording; it must not silently complete or expand sound source text either.

For sentence alignment, task items include numbered source sentence hints. The agent may return `alignment_groups` with `sentences` (one-based indices), `faithful` and `interpretive`. Use a group when several source sentences become one target sentence or vice versa. Every source sentence must appear once in order; concatenated group translations must equal the full target without omissions or repeated paragraphs. `apply` validates these invariants. Groups support traceability, not automatic semantic certification. Inspect abbreviations and source segmentation before choosing groups.
