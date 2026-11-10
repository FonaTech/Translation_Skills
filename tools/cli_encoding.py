"""Use the installed kernel's encoding policy for repository commands. MIT."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/document-translation/scripts'))
from runtime_encoding import configure_utf8, utf8_environment
