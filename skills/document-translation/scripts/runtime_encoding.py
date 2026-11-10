"""Explicit UTF-8 boundaries for portable document commands.

Copyright 2026 Yufeng Zhan. MIT.
Files must still specify their encoding at each read/write boundary. This helper
configures CLI streams and inherited Python processes; it never guesses source
document encodings or changes the process locale.
"""
from __future__ import annotations

import io
import os
import sys


def utf8_environment(environment=None):
    """Copy an environment and override stale GBK/CP936 Python settings."""
    result = dict(os.environ if environment is None else environment)
    result.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    return result


def configure_utf8():
    """Configure real CLI streams, including pipes on non-UTF-8 Windows.

    Capturing hosts may provide StringIO, no stream, or already-read stdin.
    Preserve those streams instead of replacing/closing their underlying buffers.
    Diagnostic surrogates are escaped; valid document text remains lossless UTF-8.
    """
    os.environ.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    for name in ('stdin', 'stdout', 'stderr'):
        stream = getattr(sys, name, None)
        reconfigure = getattr(stream, 'reconfigure', None)
        if not callable(reconfigure) or getattr(stream, 'closed', False):
            continue
        try:
            reconfigure(encoding='utf-8', errors='strict' if name == 'stdin' else 'backslashreplace')
        except (ValueError, io.UnsupportedOperation):
            # An embedding host may already have read stdin or disallow changes.
            # Explicit file I/O and child environments remain independent of it.
            continue
