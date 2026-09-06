"""Daily-page and shared-copy behavior tests. Run: python tests/test_daily_ui.py."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from ui_common import UI_JS  # noqa: E402


class DailyUIRegression(unittest.TestCase):
    def test_browser_state_regressions(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for the browser-state fixture")
        fixture = Path(__file__).with_name("random_ui_fixture.js").read_text(encoding="utf-8-sig")
        shared_dom = fixture.split("function fixture(){", 1)[0]
        script = shared_dom + Path(__file__).with_name("daily_ui_fixture.js").read_text(encoding="utf-8-sig")
        script = script.replace("__UI_JS__", json.dumps(UI_JS))
        script = script.replace("__DAILY_JS__", json.dumps((ROOT / "scripts/daily_ui.js").read_text(encoding="utf-8")))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "daily-ui-regressions.js"
            path.write_text(script, encoding="utf-8")
            result = subprocess.run([node, str(path)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("daily UI state regressions: PASS", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
