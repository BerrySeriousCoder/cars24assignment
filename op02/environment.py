"""Read local API settings without shell execution, interpolation, or logging secrets."""
import os
import shlex
from pathlib import Path
from . import paths

ALLOWED = {"LLM_API_KEY", "OPENAI_API_KEY", "LLM_BASE_URL", "LLM_EXTRA_HEADERS", "LLM_TIMEOUT"}


def load_environment(path=None):
    path = Path(path) if path else paths.ROOT / ".env"
    if not path.is_file():
        return
    seen = set()
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or key not in ALLOWED or key in seen:
            raise ValueError(f"unsupported or duplicate setting in .env on line {number}")
        seen.add(key)
        try:
            tokens = shlex.split(value, comments=True)
        except ValueError:
            raise ValueError(f"invalid quoting in .env on line {number}") from None
        if len(tokens) > 1:
            raise ValueError(f"quote values containing spaces in .env on line {number}")
        os.environ.setdefault(key, tokens[0] if tokens else "")
    if not os.getenv("LLM_API_KEY") and os.getenv("OPENAI_API_KEY"):
        os.environ["LLM_API_KEY"] = os.environ["OPENAI_API_KEY"]
