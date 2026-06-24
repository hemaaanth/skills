import json
import os
import stat
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from http.cookiejar import Cookie, MozillaCookieJar

from monarch_client.session import has_auth, load_token, load_web_session, normalize_token, save_token, save_web_session, session_file, web_session_file


class SessionTests(unittest.TestCase):
    def test_normalize_token_strips_token_prefix(self):
        self.assertEqual(normalize_token("Token abc123\n"), "abc123")

    def test_normalize_token_rejects_empty_values(self):
        with self.assertRaises(ValueError):
            normalize_token("Token   ")

    def test_save_and_load_token_with_override_path(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "session.json"
            saved = save_token("Token secret", path)
            self.assertEqual(saved, path)
            self.assertEqual(load_token(path), "secret")
            self.assertEqual(json.loads(path.read_text()), {"token": "secret"})
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_session_file_honors_environment_override(self):
        with TemporaryDirectory() as tmp:
            expected = Path(tmp) / "session.json"
            old = os.environ.get("MONARCH_SESSION_FILE")
            os.environ["MONARCH_SESSION_FILE"] = str(expected)
            try:
                self.assertEqual(session_file(), expected)
            finally:
                if old is None:
                    os.environ.pop("MONARCH_SESSION_FILE", None)
                else:
                    os.environ["MONARCH_SESSION_FILE"] = old

    def test_save_and_load_web_session_with_cookie_jar(self):
        with TemporaryDirectory() as tmp:
            meta = Path(tmp) / "web_session.json"
            cookies = Path(tmp) / "cookies.txt"
            old_meta = os.environ.get("MONARCH_WEB_SESSION_FILE")
            old_cookies = os.environ.get("MONARCH_COOKIE_FILE")
            os.environ["MONARCH_WEB_SESSION_FILE"] = str(meta)
            os.environ["MONARCH_COOKIE_FILE"] = str(cookies)
            try:
                jar = MozillaCookieJar()
                jar.set_cookie(Cookie(
                    version=0,
                    name="csrftoken",
                    value="csrf-secret",
                    port=None,
                    port_specified=False,
                    domain="api.monarch.com",
                    domain_specified=True,
                    domain_initial_dot=False,
                    path="/",
                    path_specified=True,
                    secure=True,
                    expires=None,
                    discard=False,
                    comment=None,
                    comment_url=None,
                    rest={},
                    rfc2109=False,
                ))
                saved = save_web_session(jar, device_uuid="device-1", client_version="test-version")
                self.assertEqual(saved, meta)
                loaded = load_web_session(meta)
                self.assertIsNotNone(loaded)
                assert loaded is not None
                self.assertEqual(loaded["device_uuid"], "device-1")
                self.assertEqual(loaded["client_version"], "test-version")
                self.assertEqual(loaded["csrf_token"], "csrf-secret")
                self.assertIn("csrftoken=csrf-secret", loaded["cookie_header"])
                self.assertTrue(has_auth())
                if os.name == "posix":
                    self.assertEqual(stat.S_IMODE(meta.stat().st_mode), 0o600)
                    self.assertEqual(stat.S_IMODE(cookies.stat().st_mode), 0o600)
            finally:
                if old_meta is None:
                    os.environ.pop("MONARCH_WEB_SESSION_FILE", None)
                else:
                    os.environ["MONARCH_WEB_SESSION_FILE"] = old_meta
                if old_cookies is None:
                    os.environ.pop("MONARCH_COOKIE_FILE", None)
                else:
                    os.environ["MONARCH_COOKIE_FILE"] = old_cookies


if __name__ == "__main__":
    unittest.main()
