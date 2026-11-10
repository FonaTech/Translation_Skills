# Source structure model 1.0.3

Copyright 2026 Yufeng Zhan. Original inference code and learned parameters: MIT.

The model proposes roles, paragraph links and spatial regions in native PDF text. It preserves source evidence for review. It does not translate, recover missing words or establish equation/table correctness. The DOM layout ranker is documented separately in [MODEL_CARD.md](MODEL_CARD.md).

## Architecture and execution

The role head has 84 inputs, 192 tanh hidden units and 10 output roles. The adjacent-line head has 46 inputs, 192 hidden units and 2 classes. A contextual region head has 56 inputs, 96 hidden units and 9 classes. Together they contain 34,005 trainable parameters.

Inference uses Python standard-library arithmetic and PyMuPDF for PDF access. Training requires NumPy. No separate model service is needed. The model file records feature revisions, normalization, thresholds and the checkpoint identity. These must remain compatible with the extraction code.

PDF ingestion selects the model by default. `--structure native` selects native extraction; `--tables` in auto mode selects native table-cell extraction. Both routes retain source evidence and require review.

## Source evidence and training

Native row IDs, character boxes, font information and fragment geometry remain available. Geometry rules constrain column jumps, table-cell joins and uncertain links. Predictions and rules remain proposals until checked against the page.

Training combines synthetic fixtures with source-inspected annotations. The model retains training and validation source-family hashes so evaluation tools can reject overlapping sources, including declared repaired or converted copies. These identity records contain no source text or filenames. Source documents and annotations are not distributed. Reproducing the real-data fit requires separately authorized annotations; the trainer can regenerate synthetic fixtures.

The annotation, training and evaluation procedure is described in [structure-training.md](../../references/structure-training.md). Model scores are not calibrated correctness probabilities. Source-authored agent labels should be distinguished from independent human annotations.

## Limits

Missing font maps, scanned text, mathematical topology, image ownership and table semantics need source-based checking. Preserving characters and coordinates does not reconstruct superscripts, fractions or equation meaning. Paragraph links can be individually plausible while producing an incorrect complete group.

Evaluate role, link, exact-group, reading-order and truth-coverage metrics separately on whole sources excluded from fitting and tuning. Native glyph accounting and unit tests do not measure translation accuracy. Keep unresolved content visible and inspect the actual source and rendered pages before delivery.

PDF paths retain native text/font/vector evidence and do not run OCR or agent transcription. Repeated margin furniture is archived separately; unavailable native text and unresolved math/table structures remain explicit findings.
