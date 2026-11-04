# Translation cases

Each case identifies a detail that can change meaning during translation. The source passages and paired translations are in [paired-cases.json](../examples/paired-cases.json).

| Case | Review focus |
|---|---|
| [Research](research.md) | Population, uncertainty and causal wording |
| [Manual](manual.md) | Warnings, action order and waiting time |
| [Legal](legal.md) | Permission, obligation, exceptions and defined terms |
| [Finance](finance.md) | Accounting scope, units and percentage points |
| [Literary](literary.md) | Voice, imagery and ambiguity |
| [Public service](public-service.md) | Receipt deadlines and conditional eligibility |
| [Health](health.md) | Dose, frequency, duration and source exceptions |
| [Software](software.md) | Identifiers, zero values and negation |

The [gallery](../examples/index.html) presents reading editions and source comparisons in five target languages. These author-owned examples illustrate translation decisions; domain expertise still needs separate review where relevant.

Engineering fixtures in `tools/integration.py` exercise multi-file ordering, columns, scanned text, tables, long paragraphs and inert source scripts. The [public-source record](../references/public-test-provenance.json) distinguishes translated excerpts from extraction trials and blocked OCR.
