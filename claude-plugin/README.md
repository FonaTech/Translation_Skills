# Claude Code

Prepare the Python environment using the [installation guide](../docs/INSTALL.md), then preview and apply the copy:

```bash
python3 tools/install.py --targets claude --project /path/to/project
python3 tools/install.py --targets claude --project /path/to/project --apply
```

Refresh skill discovery and invoke it with `/document-translation`. The maintained [skill source](../skills/document-translation/SKILL.md) is shared across clients.

The root `.claude-plugin/` directory provides the optional plugin route. The manifests here are browsing copies.

Installation tests cover file copies and metadata. See [reproducible checks](../docs/REPRODUCIBILITY.md) for the checks and their scope.
