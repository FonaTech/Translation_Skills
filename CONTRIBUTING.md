# Contributing

Keep the shared translation workflow usable across clients and document types. Add domain examples when they explain a concrete translation decision; avoid domain-specific branches in the core unless extraction genuinely requires them.

Preserve selected scope, source locations, stable IDs and both complete editions. Fix the editable content or generator rather than generated outputs. Use author-owned test material, or document the rights and exact excerpt scope.

Before submitting:

```bash
python3 -m pip install -r requirements-optional.txt
python3 tools/validate.py
python3 -m unittest discover -s tests -v
python3 tools/checksums.py --write
python3 tools/checksums.py
```

For extraction or pagination changes, run the relevant fixture in a fresh external work directory and inspect the affected source and rendered pages. Describe the test environment, actual checks and remaining failures. Record semantic or visual review only after performing it.

Keep private sources, credentials, machine-specific paths, downloaded runtimes and temporary outputs out of the repository. Preserve third-party notices for any material you add. See [reproducible checks](docs/REPRODUCIBILITY.md) for format, browser and corpus tests.
