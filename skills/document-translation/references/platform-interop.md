# Four runtimes, one core

Portable frontmatter has name/description. Helpers use Python/filesystem/shell, not proprietary chat tools. The invoking model translates.

| Runtime | Project install | User install |
|---|---|---|
| Codex | .agents/skills/document-translation | ~/.agents/skills/document-translation; legacy ~/.codex is explicit |
| Claude Code | .claude/skills/document-translation | ~/.claude/skills/document-translation |
| OpenCode | .opencode/skills/document-translation | ~/.config/opencode/skills/document-translation |
| Clouds_Coder | configured skills root, often skills/generated/document-translation | explicit --clouds-root |

Installer defaults to dry-run; --apply copies and backs up existing targets. It never injects standing instructions, grants tools or installs dependencies. Confirm discovery in a new client session. Filesystem tests are not live client tests.

Clouds sidecar agents/clouds-coder.json is merged into frontmatter only in generated Clouds copies. Standard metadata remains for other clients. Full/compact loading keeps the runtime contract. Optional RAG provides a glossary, never source overrides.

Claude manifests exist hidden/visible. Codex openai.yaml is UI metadata. OpenCode follows standard frontmatter. Validation distinguishes static/install tests from actual host sessions. Recheck interfaces before changing adapters.

## Native agent translation loop (all four clients)

No Ollama installation, local model, API key, translation endpoint or platform-specific model tool is required. The model already running inside Codex, Claude Code, OpenCode or Clouds_Coder reads `tasks/*.json`, writes its real semantic translations to response packets, invokes `translate.py apply`, then resumes audit/build/render/review/release. If a task exceeds context, use smaller chunks and persist the remaining IDs; do not stop because an optional service is missing. A helper script cannot impersonate this step.

1. Inspect extracted text and page previews; reconstruct paragraphs/figures before generating final tasks.
2. `tasks PROJECT --language TAG --size 20 --all` emits source hashes and expected IDs.
3. In the current agent loop, translate each item into both editions. Write the actual strings, keeping `language`, `source_hash`, `expected_ids` and `items`; set `translation_provider` to the actual agent/client. Sentence groups are optional, checked exchange data.
4. `apply PROJECT PACKET` validates IDs/coverage/freshness atomically and records the packet hash and applied IDs. Do not mark semantic review complete merely because apply succeeds.
5. Read audit warnings, fix errors, check source against both translations, build, render with source-preserving adjustments, visually inspect pages, record honest reviews and release. Rebuild/review after content changes.

For a real corpus regression use `tools/pdf_corpus_regression.py prepare`, perform the native loop above on each project, then `check`. Preparation reports `AWAITING_CURRENT_AGENT_TRANSLATION`; it never fills edition fields or claims a semantic pass.
