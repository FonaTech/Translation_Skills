# Cases and boundary fixtures

| Case | Review focus |
|---|---|
| [Research](research.md) | evidence strength, uncertainty and population |
| [Manual](manual.md) | warnings, ordering and thresholds |
| [Legal](legal.md) | obligations, permissions, exceptions and terms |
| [Finance](finance.md) | units, accounting scope and percentage points |
| [Literary](literary.md) | voice and imagery without invented detail |
| [Public service](public-service.md) | receipt deadlines and conditional eligibility |
| [Health](health.md) | source dosage/frequency/exception preservation |
| [Software](software.md) | code identifiers, zero and negation |

[Paired author-owned examples](../examples/paired-cases.json) supply eight independent passages in five target languages. The [gallery](../examples/index.html) shows full dual-edition and alignment artifacts.

Additional engineering fixtures in `tools/integration.py` cover a multi-file collection, two-column PDF, scanned PDF, DOCX table, inert source script, 90-row CSV, prolonged paragraph, 0/N/A, and repeated headers. Public-PDF tests include native text, a six-page form with six selected translated excerpts, and unreadable historical handwriting whose translation remains blocked. See repository validation for evidence; these are not a universal language benchmark.

For a new field, identify its consequential semantic features, prepare a small representative source/translation pair with provenance, and run the same extraction, dual-edition, layout and review contract. Do not fork the core into field-specific assumptions.
