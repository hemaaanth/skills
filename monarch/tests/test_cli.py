import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "monarch.py"


class CliHelpTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_top_level_help_works_without_monarchmoney_dependency(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Monarch Money CLI", result.stdout)
        self.assertIn("login", result.stdout)
        self.assertIn("refresh", result.stdout)

    def test_refresh_requires_confirm(self):
        result = self.run_cli("refresh")
        self.assertNotEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["type"], "confirmation_required")

    def test_high_risk_write_requires_env_gate_after_confirm(self):
        result = self.run_cli("delete-transaction", "tx_123", "--confirm")
        self.assertNotEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["type"], "write_not_enabled")


if __name__ == "__main__":
    unittest.main()
