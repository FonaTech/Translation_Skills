# Install on four clients

Python 3.10+; shell and local file access. PDF extraction uses PyMuPDF, rendering uses Playwright/Chromium. Optional DOCX fixture tests use python-docx. PyYAML is required for the Clouds overlay. Install dependencies in your preferred virtual environment; the installer does not install them or request tools.

```bash
python3 -m venv .venv
# Activate according to your shell, then:
python3 -m pip install -r requirements-core.txt
python3 -m playwright install chromium
python3 skills/document-translation/scripts/translate.py doctor
```

| Client | Project route | User route | Activation example |
|---|---|---|---|
| Codex | `.agents/skills/document-translation` | `~/.agents/skills/document-translation` | `$document-translation` or plain request |
| Claude Code | `.claude/skills/document-translation` | `~/.claude/skills/document-translation` | `/document-translation` or plain request |
| OpenCode | `.opencode/skills/document-translation` | `~/.config/opencode/skills/document-translation` | ask to load `document-translation` |
| Clouds_Coder | actual configured skills root; suggested `skills/generated/document-translation` | explicit configured root | ask/load `document-translation` |

Run from repository root:

```bash
python3 tools/install.py --targets codex claude opencode --project /path/to/active-project
python3 tools/install.py --targets codex claude opencode --project /path/to/active-project --apply
python3 tools/install.py --targets clouds --clouds-root /path/to/configured/skills --apply
# User installation: omit --project for codex/claude/opencode.
# Only when the active Codex surface requires the legacy location:
python3 tools/install.py --targets codex-legacy --apply
```

Default is dry-run. Existing targets receive timestamped backup directories, and failed copies roll back. Symlink targets are rejected. No standing instructions, settings files, credentials or permissions are changed. Restart/refresh client skill discovery when necessary and confirm the skill appears. Roll back by removing the new copy and renaming the printed backup to its original path.

Clouds metadata remains in `agents/clouds-coder.json` in the canonical source. The installer merges it into generated Clouds frontmatter. Other clients get standard name/description frontmatter and optional UI metadata. The skill does not require Clouds-only tools.

Claude optional plugin: the repository root includes `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` pointing to `./skills/`. You can inspect locally with `claude --plugin-dir /path/to/Translation_Skills` in a compatible Claude Code version. This route is additional to copying a normal skill; actual plugin CLI execution was not part of local tests. Visible mirrors in `claude-plugin/` are documentation copies, not alternate install roots.

Do not install demo projects as standalone skills. Do not create translation output inside the installed skill. External translation or OCR services are optional only when explicitly authorized for the selected documents.

Host versions change. Official references used when preparing adapters: [Claude Code](https://code.claude.com/docs/en/skills), [OpenCode](https://opencode.ai/docs/skills/), [Codex skills](https://developers.openai.com/codex/skills), [Clouds_Coder source](https://github.com/FonaTech/Clouds-Coder). See validation for exact verification limits; these links do not imply live-host certification.
