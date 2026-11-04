# OpenCode

Prepare the Python environment using the [installation guide](../docs/INSTALL.md), then preview and apply the copy:

```bash
python3 tools/install.py --targets opencode --project /path/to/project
python3 tools/install.py --targets opencode --project /path/to/project --apply
```

Refresh skill discovery and invoke it with a request to load `document-translation`. The maintained [skill source](../skills/document-translation/SKILL.md) is shared across clients.

Installation tests cover file copies and metadata. See [validation scope](../skills/document-translation/references/validation-summary.md) for what was exercised.
