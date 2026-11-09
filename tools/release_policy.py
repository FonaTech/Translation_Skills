"""Shared public-release inventory; private runs and delivery notes stay local."""
from pathlib import Path

PUBLIC_DIRECTORIES = frozenset({
    '.claude-plugin', '.github', 'claude-plugin', 'clouds-coder', 'codex',
    'docs', 'opencode', 'schemas', 'skills', 'tests', 'tools',
})
PUBLIC_ROOT_FILES = frozenset({
    '.gitattributes', '.gitignore', 'CHANGELOG.md',
    'CONTRIBUTING.md', 'LICENSE', 'README.md', 'README_zh-CN.md',
    'SHA256SUMS.txt', 'THIRD_PARTY_NOTICES.md', 'VERSION',
    'requirements-core.txt', 'requirements-optional.txt',
})
PUBLIC_DOCUMENTATION = frozenset({
    'docs/ARCHITECTURE.md', 'docs/INSTALL.md', 'docs/REPRODUCIBILITY.md',
    'docs/SUPPORT.md', 'docs/WORKFLOW.md',
})
EXCLUDED_PARTS = frozenset({
    'ACKNOWLEDGMENTS.md',
    'examples', 'demos', 'outputs', '.git', '__pycache__', '.venv', 'node_modules', '.DS_Store', '__MACOSX',
    '.pytest_cache', '.mypy_cache', '.ruff_cache', '.cache', 'work', 'validation',
    'private', 'delivery', 'reports', 'screenshots', '.env',
    'UPLOAD_zh-CN.md', '译校与交付说明.md', 'DELIVERY_NOTES.md', 'delivery-notes.md',
    '交付说明.md', 'recipient-notes.md', 'standalone-explanation.md',
    'notes-for-recipient.md',
    'public-test-provenance.json',
})
EXCLUDED_PARTS_CASEFOLD = frozenset(part.casefold() for part in EXCLUDED_PARTS)
EXCLUDED_SUFFIXES = frozenset({'.pyc', '.pyo', '.tmp', '.log', '.bak', '.swp'})


def public_files(root, *, include_manifest=True):
    """Return the same sorted inventory for checksums and archive creation."""
    root = Path(root).resolve()
    result = []
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if not path.is_file() or path.is_symlink():
            continue
        if any(parent.is_symlink() for parent in path.parents if parent != root):
            continue
        if any(part.casefold() in EXCLUDED_PARTS_CASEFOLD for part in relative.parts):
            continue
        if path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        if len(relative.parts) == 1:
            if path.name not in PUBLIC_ROOT_FILES:
                continue
        elif relative.parts[0] not in PUBLIC_DIRECTORIES:
            continue
        if relative.parts[0] == 'docs' and relative.as_posix() not in PUBLIC_DOCUMENTATION:
            continue
        if not include_manifest and relative.as_posix() == 'SHA256SUMS.txt':
            continue
        result.append(path)
    return result
