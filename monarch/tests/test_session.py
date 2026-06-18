import json
import os
import stat
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from monarch_client.session import load_token, normalize_token, save_token, session_file


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


if __name__ == "__main__":
    unittest.main()
