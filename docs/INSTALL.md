# Installation

[中文快速开始](../README_zh-CN.md#开始使用) · [Workflow](WORKFLOW.md)

Install the Python dependencies once, then copy the skill to the client you use. The installer handles the copy and backups. It leaves client settings, standing instructions and permissions unchanged.

## 1. Prepare the environment

From the repository root, using Python 3.10 or later:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-core.txt
python3 -m playwright install chromium
python3 skills/document-translation/scripts/translate.py doctor
```

Use `.venv\Scripts\Activate.ps1` to activate the environment in Windows PowerShell. The client must use this environment, or another Python environment with the same dependencies, when it runs skill scripts.

For PDF output, install Chromium as shown above or supply an existing browser with `--browser` when building/rendering. `TRANSLATION_BROWSER` can also hold its executable path. PDF routes do not use OCR. Legacy recognition helpers for separately selected non-PDF rasters need Tesseract or macOS Vision. See [format support](SUPPORT.md).

## 2. Choose an installation location

| Client | Project installation | User installation | Invocation |
|---|---|---|---|
| Codex | `.agents/skills/document-translation` | `~/.agents/skills/document-translation` | `$document-translation` or a document translation request |
| Claude Code | `.claude/skills/document-translation` | `~/.claude/skills/document-translation` | `/document-translation` or a document translation request |
| OpenCode | `.opencode/skills/document-translation` | `~/.config/opencode/skills/document-translation` | Ask to load `document-translation` |
| Clouds_Coder | The project's configured skills root | An explicitly configured skills root | Ask to load `document-translation` |

For a project installation, choose `codex`, `claude` or `opencode`:

```bash
python3 tools/install.py --targets codex --project /path/to/project
python3 tools/install.py --targets codex --project /path/to/project --apply
```

The first command prints the destination. The second copies the files. To install in more than one client, use `--targets codex claude opencode`. To install for your user account, omit `--project`.

For Clouds_Coder, use its configured skills directory:

```bash
python3 tools/install.py --targets clouds --clouds-root /path/to/skills
python3 tools/install.py --targets clouds --clouds-root /path/to/skills --apply
```

The installer adds the Clouds metadata from `agents/clouds-coder.json` only to the Clouds copy. The other copies retain standard skill frontmatter. `codex-legacy` is available for a Codex installation that specifically requires `.codex/skills`.

## 3. Confirm discovery

Refresh or restart the client's skill discovery, then confirm that `document-translation` is available. Ask it to translate a small file before starting a large collection. Save translation projects outside the installed skill folder.

Existing destinations are renamed to timestamped backups. Failed copies restore the backup. To roll back later, remove the new copy and rename the printed backup to its original name. The installer rejects a symlink destination.

## Optional Claude Code plugin

The repository includes `.claude-plugin/plugin.json` and a marketplace manifest. In a compatible Claude Code version, load the repository with:

```bash
claude --plugin-dir /path/to/Translation_Skills
```

The files in `claude-plugin/` mirror those manifests for browsing. The repository root is the plugin directory. This route is optional; copying the standard skill is sufficient.

## Compatibility checks

Repository tests cover installation paths, backups and metadata. They do not establish interactive compatibility with every client version. See [reproducible checks](REPRODUCIBILITY.md).

Client references: [Codex](https://developers.openai.com/codex/skills), [Claude Code](https://code.claude.com/docs/en/skills), [OpenCode](https://opencode.ai/docs/skills/), [Clouds_Coder](https://github.com/FonaTech/Clouds-Coder).

## Windows encoding

The CLI configures UTF-8 streams and inherited Python processes. Internal JSON, HTML and resource I/O uses explicit UTF-8, independent of a GBK/CP936 locale. Custom launchers should use `python -X utf8` and decode captured output as UTF-8. The system locale remains unchanged.
