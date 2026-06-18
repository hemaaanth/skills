"""Session-token storage helpers for Monarch Money."""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_SESSION_FILE = Path.home() / ".monarchmoney" / "session.json"


def session_file() -> Path:
    """Return the configured Monarch session file path."""
    override = os.getenv("MONARCH_SESSION_FILE")
    return Path(override).expanduser() if override else DEFAULT_SESSION_FILE


def normalize_token(token: str) -> str:
    """Normalize a token copied from a browser Authorization header."""
    token = (token or "").strip()
    if token.lower() == "token":
        token = ""
    elif token.lower().startswith("token "):
        token = token.split(" ", 1)[1].strip()
    if not token:
        raise ValueError("empty Monarch token")
    return token


def save_token(token: str, path: Path | None = None) -> Path:
    """Save a Monarch API token with restrictive filesystem permissions."""
    path = path or session_file()
    token = normalize_token(token)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    path.write_text(json.dumps({"token": token}) + "\n")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def load_token(path: Path | None = None) -> str | None:
    """Load a saved Monarch API token, or return None if unavailable."""
    path = path or session_file()
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    token = data.get("token")
    return normalize_token(token) if token else None
