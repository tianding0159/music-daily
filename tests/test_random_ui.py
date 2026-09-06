"""Focused static-render and browser-state regressions. Run: python tests/test_random_ui.py.

The Node fixture exercises shipped JavaScript without networking or a browser.
Real visual and media verification is kept separate from these deterministic checks.
"""
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
from lightbox import lightbox_js  # noqa: E402
from render_random import JS, build_artist_json, build_html  # noqa: E402
from ui_common import UI_JS  # noqa: E402


class RandomUIRegression(unittest.TestCase):
    def test_artist_links_preserve_ids_for_duplicate_titles(self):
        songs = [dict(id="a-id", title="Same name", artist="A"),
                 dict(id="b-id", title="Same name", artist="A")]
        context = json.loads(build_artist_json(songs, {}))["A"]
        self.assertEqual(context["i"], [{"id": "a-id", "title": "Same name"},
                                        {"id": "b-id", "title": "Same name"}])

    def test_navigation_and_native_control_contract(self):
        html = build_html(2169)
        self.assertIn('href="#main"', html)
        self.assertIn('id="main"', html)
        self.assertIn('id="f-search" type="search"', html)
        self.assertIn('id="np-bar" role="slider"', html)
        self.assertIn('aria-current="page">听点别的', html)
        self.assertIn('2,169', html)
        self.assertIn('base_prefix', lightbox_js.__annotations__)

    def test_browser_state_regressions(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for the browser-state fixture")
        script = (Path(__file__).with_name("random_ui_fixture.js")).read_text(encoding="utf-8")
        script = script.replace("__UI_JS__", json.dumps(UI_JS))
        script = script.replace("__RANDOM_JS__", json.dumps(JS))
        script = script.replace("__LIGHTBOX_JS__", json.dumps(lightbox_js(".art", "../")))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "random-ui-regressions.js"
            path.write_text(script, encoding="utf-8")
            result = subprocess.run([node, str(path)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("random UI state regressions: PASS", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
