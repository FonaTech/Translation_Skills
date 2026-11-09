# DOM candidate ranker 1.0.1

Copyright 2026 Yufeng Zhan. Original fixtures, weights and inference code: MIT.

This trained pairwise neural ranker has 24 normalized numeric inputs, 12 tanh hidden units and one scalar output. Offline JavaScript inference uses ordinary arithmetic without libraries, network requests or a model server. Its inference code and weights are embedded in translation HTML and the single-file editor.

## Intended use

Rank up to 24 conservative adjustments of a source-adapted layout from measured geometry: paragraph/heading spacing, line spacing, type size, column gap and table padding. Page shape, column count, noncontiguous source boundaries and text remain fixed by the candidate generator. Manual parameter locks exclude edited controls from automatic optimization. Hard gates independently check text preservation, overflow and empty pages. Model scores never authorize template fallback.

## Training and evaluation

The bundled training-data.json contains 80 original synthetic fixtures and 1,920 actual browser-rendered candidate measurements: 64 standard fixtures, 8 long two-column fixtures and 8 three-column source/translation alignment fixtures. They vary Chinese, English, mixed text, Arabic, page sizes, one to three columns, headings, synthetic figures and tables. No private source documents are bundled. The seeded, family-stratified document-level split has 60 training and 20 held-out documents; 15,802 preference pairs train for 1,800 Adam steps with seed 173. Training candidates span 1 to 56 pages. Retraining requires NumPy; inference does not. Training uses explicit NumPy contractions, rejects non-finite features, gradients and weights, and treats divide/overflow/invalid numerical errors as failures before export.

Targets come from the disclosed utility() function in tools/train_layout_model.py: engineering preferences for valid text, moderate density, legibility, balance, limited source deviation and restrained pagination. They are not human aesthetic labels. This model learns an approximation of those preferences rather than semantic or human design expertise.

The stored evaluation records document IDs, fixture families, choices and regret. On the current synthetic holdout, pairwise teacher agreement is 0.976235382874387 and mean teacher regret is 0.00609705. This is not a 97.6% probability that arbitrary real documents look good. All collected synthetic candidates passed geometry checks; invalid cases are guarded by independent checks rather than a demonstrated learned invalidity classifier.

## Reproduce

Run `python tools/train_layout_model.py --dataset skills/document-translation/assets/models/training-data.json`, then `python tools/build_editor.py` from the repository root. To recollect, add `--collect --documents 80 --seed 173 --browser PATH_TO_CHROMIUM`. Browser and font changes affect measurements; stored data permit repeatable training. The recorded dataset SHA-256 is 9fce33b71bcfa2d5a4b0415360805d4b4dffd7820f3aac547bab344e13e74893.

## Limits

The model sees geometry features rather than page images or meaning. It cannot judge glyph quality, translation accuracy, figure labels or visual aesthetics and provides no calibrated confidence. Scans, complex floats, forms, equations, unusual tables, fonts and long-document structure still need actual source/output review. Ranking may retain the original layout. Never fabricate review from scores.
