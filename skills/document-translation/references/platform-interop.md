# Client integration

The shared skill uses standard name/description frontmatter and local Python/file tools. The model running in the client supplies the translations.

| Client | Project location | User location |
|---|---|---|
| Codex | `.agents/skills/document-translation` | `~/.agents/skills/document-translation` |
| Claude Code | `.claude/skills/document-translation` | `~/.claude/skills/document-translation` |
| OpenCode | `.opencode/skills/document-translation` | `~/.config/opencode/skills/document-translation` |
| Clouds_Coder | Configured skills root, often `skills/generated/document-translation` | Explicit `--clouds-root` |

The installer previews destinations by default. `--apply` copies the skill and backs up an existing destination. It does not install Python dependencies or alter client instructions and permissions. Refresh discovery after installation. The explicit `codex-legacy` target supports clients that require `.codex/skills`.

Clouds metadata in `agents/clouds-coder.json` is merged into generated Clouds copies. Its runtime contract and entrypoints remain available during full or compact loading. Other clients receive standard frontmatter. `agents/openai.yaml` supplies Codex display metadata. Claude plugin manifests offer an additional loading route from the repository root.

## Translation loop

1. Inspect extracted text and source previews. Correct reading order, tables and figure/caption relationships before generating final tasks.
2. Generate task packets with `tasks PROJECT --language TAG --size 12`. They include source hashes and expected IDs.
3. Translate each item into both editions in the current client. Retain `language`, `source_hash`, `expected_ids` and `items`. Record the actual client/model as `translation_provider` when supplied.
4. Apply each packet, compare the translations with the source, inspect audit warnings, then build, render and review.

No separate translation endpoint is required. Use smaller packets and persist pending IDs when context is limited. Optional glossary retrieval can inform terminology without overriding the selected source.

For a corpus regression, `tools/pdf_corpus_regression.py prepare` creates tasks with empty edition fields. Complete the same loop before running `check`. Isolated installation tests establish copy/metadata behavior; they do not establish interactive compatibility with every client version.
