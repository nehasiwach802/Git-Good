"""Read Gemini settings from environment or the project's .env without executing it."""

import os
from pathlib import Path
import re

from .core import CandidateError


ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
SETTING_NAMES = {"GEMINI_API_KEY", "GEMINI_MODEL"}


def load_dotenv(path=None):
    """Small deliberate dotenv subset: KEY=value, optional export, quotes/comments.

    Only Gemini settings are read. No shell execution, variable expansion, escapes
    or multiline strings. Values are never included in error messages.
    """
    path = Path(path) if path is not None else ENV_FILE
    if not path.exists():
        return {}
    result = {}
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, separator, value = line.partition("=")
        name = name.strip()
        if name not in SETTING_NAMES:
            continue
        value = value.strip()
        if not separator:
            raise CandidateError(f"Invalid Gemini setting in .env at line {number}; use KEY=value")
        if not value or value.startswith("#"):
            result[name] = ""
            continue
        match = re.fullmatch(r'''(?:'([^']*)'|"([^"]*)"|([^\s'"#]+))(?:\s+#.*)?\s*''', value)
        if match is None:
            raise CandidateError(f"Invalid Gemini setting in .env at line {number}; check quotes")
        result[name] = next(item for item in match.groups() if item is not None)
    return result


def gemini_settings():
    """Process environment takes precedence; never copy file secrets into os.environ."""
    # When both are supplied externally, an unrelated local file cannot interfere.
    local = {} if SETTING_NAMES <= os.environ.keys() else load_dotenv()
    return {name: os.environ.get(name, local.get(name, "")) for name in SETTING_NAMES}
