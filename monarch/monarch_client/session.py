"""Session storage helpers for Monarch Money.

Supports both the legacy API token used by the unofficial ``monarchmoney``
package and the newer web cookie session used by Monarch's current web app.
"""

from __future__ import annotations

import http.cookiejar
import json
import os
from pathlib import Path
from typing import Any

DEFAULT_SESSION_DIR = Path.home() / ".monarchmoney"
DEFAULT_SESSION_FILE = DEFAULT_SESSION_DIR / "session.json"
DEFAULT_WEB_SESSION_FILE = DEFAULT_SESSION_DIR / "web_session.json"
DEFAULT_COOKIE_FILE = DEFAULT_SESSION_DIR / "cookies.txt"
DEFAULT_CLIENT_VERSION = "v1.0.2840"


def _chmod_private(path: Path, mode: int = 0o600) -> None:
    try:
        path.chmod(mode)
    except OSError:
        pass


def _ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _chmod_private(path, 0o700)


def session_file() -> Path:
    """Return the configured legacy Monarch token session file path."""
    override = os.getenv("MONARCH_SESSION_FILE")
    return Path(override).expanduser() if override else DEFAULT_SESSION_FILE


def web_session_file() -> Path:
    """Return the configured Monarch web-cookie session metadata path."""
    override = os.getenv("MONARCH_WEB_SESSION_FILE")
    return Path(override).expanduser() if override else DEFAULT_WEB_SESSION_FILE


def cookie_file() -> Path:
    """Return the configured Monarch web cookie-jar path."""
    override = os.getenv("MONARCH_COOKIE_FILE")
    return Path(override).expanduser() if override else DEFAULT_COOKIE_FILE


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
    """Save a legacy Monarch API token with restrictive filesystem permissions."""
    path = path or session_file()
    token = normalize_token(token)
    _ensure_private_dir(path.parent)
    path.write_text(json.dumps({"token": token}) + "\n")
    _chmod_private(path)
    return path


def load_token(path: Path | None = None) -> str | None:
    """Load a saved legacy Monarch API token, or return None if unavailable."""
    path = path or session_file()
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    token = data.get("token")
    return normalize_token(token) if token else None


def save_web_session(cookies: http.cookiejar.MozillaCookieJar, *, device_uuid: str, client_version: str = DEFAULT_CLIENT_VERSION, metadata: dict[str, Any] | None = None) -> Path:
    """Persist Monarch web cookies and non-secret session metadata."""
    cookie_path = cookie_file()
    meta_path = web_session_file()
    _ensure_private_dir(meta_path.parent)
    cookies.filename = str(cookie_path)
    cookies.save(str(cookie_path), ignore_discard=True, ignore_expires=True)
    _chmod_private(cookie_path)
    data: dict[str, Any] = {
        "auth_type": "web_cookie",
        "device_uuid": device_uuid,
        "client_version": client_version,
        "cookie_file": str(cookie_path),
    }
    if metadata:
        for key in ("session_expires_at", "tokenExpiration"):
            if metadata.get(key):
                data[key] = metadata[key]
    meta_path.write_text(json.dumps(data, indent=2) + "\n")
    _chmod_private(meta_path)
    return meta_path


def load_web_session(path: Path | None = None) -> dict[str, Any] | None:
    """Load Monarch web-cookie session metadata and cookies."""
    path = path or web_session_file()
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    cookie_path = Path(data.get("cookie_file") or cookie_file()).expanduser()
    if not cookie_path.exists():
        return None
    jar = http.cookiejar.MozillaCookieJar(str(cookie_path))
    jar.load(ignore_discard=True, ignore_expires=True)
    csrf = next((cookie.value for cookie in jar if cookie.name == "csrftoken"), None)
    cookie_header = "; ".join(f"{cookie.name}={cookie.value}" for cookie in jar)
    if not cookie_header:
        return None
    return {
        **data,
        "cookies": jar,
        "cookie_header": cookie_header,
        "csrf_token": csrf,
        "device_uuid": data.get("device_uuid") or os.getenv("MONARCH_DEVICE_UUID") or "hermes-monarch",
        "client_version": data.get("client_version") or DEFAULT_CLIENT_VERSION,
    }


def has_auth() -> bool:
    """Return True when either legacy token auth or web-cookie auth is saved."""
    try:
        if load_token():
            return True
    except Exception:
        pass
    try:
        return bool(load_web_session())
    except Exception:
        return False
