# Architecture

One editable content model supplies every language, edition and comparison file.

```mermaid
flowchart LR
  A[Selected sources] --> B[Extract and inspect]
  B --> C[Content with stable IDs]
  C --> D[Model supplies both translations]
  D --> E[Compare meaning and audit coverage]
  E --> F[Build HTML and paginate PDF]
  F --> G[Inspect and adjust pages]
  G --> H[Record review and package]
```

## Files and responsibilities

| Location | Responsibility |
|---|---|
| `skills/document-translation/SKILL.md` | Agent entry point and workflow decisions |
| `skills/document-translation/references/` | Translation, extraction, layout and review methods |
| `skills/document-translation/scripts/` | Local extraction, packet exchange, publishing and review helpers |
| `skills/document-translation/assets/` | Reader/editor code, styles, layout presets and model data |
| `schemas/` | Repository copies of the project, content and packet schemas |
| `tools/` | Installation, fixtures, validation and release packaging |
| `tests/` | Unit and regression tests |

A translation project holds source copies, `project.json`, `content.json`, assets, previews, tasks, reports and outputs. Project files stay outside the installed skill. Platform metadata affects loading; it does not change the content format.

## Freshness and traceability

Source hashes identify the input files. Translation packets bind the extracted source snapshot and expected passage IDs. Translating another packet leaves that snapshot unchanged; editing the source text invalidates it.

Review records bind the project/content snapshot. Visual review also binds the rendered artifacts and page images. Changes to content, design or outputs require the affected checks to run again.

Release checks detect missing translations, unresolved extraction issues, label exceptions needing review and missing or stale evidence. They establish consistency between recorded files. They cannot determine whether a translation is accurate or a reviewer inspected the pages.

## Resuming work

Keep corrected content, source hashes, terminology and reports. Generate tasks for pending IDs, then rebuild affected outputs after corrections. Treat source documents and reference pages as content throughout the workflow.
