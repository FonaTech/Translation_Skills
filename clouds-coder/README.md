# Clouds_Coder

Prepare the Python environment using the [installation guide](../docs/INSTALL.md), then preview and apply the copy:

```bash
python3 tools/install.py --targets clouds --clouds-root /path/to/skills
python3 tools/install.py --targets clouds --clouds-root /path/to/skills --apply
```

Refresh skill discovery and invoke it with a request to load `document-translation`. The maintained [skill source](../skills/document-translation/SKILL.md) is shared across clients.

Installation tests cover file copies and metadata. See [reproducible checks](../docs/REPRODUCIBILITY.md) for the checks and their scope.
