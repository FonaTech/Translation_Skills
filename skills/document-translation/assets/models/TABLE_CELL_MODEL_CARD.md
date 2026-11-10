# Native table cell links 1.0.3

Copyright 2026 Yufeng Zhan. Original inference code, generated fixtures and learned
parameters: MIT. No source PDF, private annotation text or translated example is
distributed with the model.

## What executes

`table_learning.py` executes a 20-input, 32-hidden-unit, 2-output tanh network
through the shared numerical inference engine. This adds 738 learned parameters.
The model uses native coordinates, baselines, font properties, physical gaps,
numeric/parenthetical text cues, intervening rules and column agreement. Runtime
inference needs no ML framework, network service, OCR or generative model.
The bundled `table-cell-links.json` SHA-256 is
`a65199461da99f5bd3a1bf7bbd0de022d365a053ae1690907aedf468c636ac55`.

Adjacent-line scores propose whether two physical records belong in the same
cell. Scores at or above 0.94 pass the model gate; this is an uncalibrated
decision threshold, not a claim of 94% correctness. The constrained decoder
additionally requires source horizontal rules, recurring column alignment and
complete, unique native-row ownership. A learned join can be vetoed by the full
row geometry. Multi-tier headers and source-supported horizontal/vertical spans
retain separate logical positions. Rejected ruled grids cannot silently pass
through the weaker legacy decoder.

`table_topology.py` independently rejects overlapping owners, orphan covered
positions, nonrectangular merged grids, out-of-bounds spans and merges crossing
the header/data boundary. HTML preserves spans; pagination keeps connected
vertical merges together; DOCX export emits native gridSpan/vMerge elements.
Merged-cell DOCX import and ODT round trips are not certified by this check.

## Training evidence and limits

Seed 20261110 produces 600 original geometric document families. Complete
documents are split into 360 training, 120 validation and 120 generated holdout
documents; rows from one document never cross splits. The shipped checkpoint also uses separately source-inspected development annotations, which are not included. Development measurements do not establish real-world holdout accuracy. Training uses class-balanced cross entropy and a false-join penalty for source separators or disjoint columns; geometry constraints can veto a predicted join.

Hierarchical partial separators and diagonal header arrangements may remain
unresolved. The current conservative route retains the complete source table
as SVG/PNG with native text/font evidence in `reports/native-tables/`, an open
`source-table-topology-unresolved` finding and incomplete-translation status.
That artwork is not represented as a translated editable table. Scanned cell
text is never sent through OCR.

## Reproduce and extend

Run `python tools/train_table_links.py --output MODEL.json --evidence REPORT.json`
with NumPy installed separately. Add `--annotations PATH` only for authorized,
source-inspected training annotations; private annotations remain outside this
repository. Training rejects non-finite parameters before serialization.
Without the private labels this reproduces the original generated-data training
route, not the identical shipped checkpoint. Record a new checkpoint hash when
retraining. Use new complete source documents for real-world holdouts.

`tools/merged_table_regression.py --output OUTPUT_DIR` checks actual browser
pagination and native DOCX spans using an original small fixture. It is a format
regression, not a cell-recognition benchmark. Independent topology rejection
tests are in `tests/test_table_topology.py`.
