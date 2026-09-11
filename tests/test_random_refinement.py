"""Regression checks for refinement of the existing industrial random-page UI."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from render_random import JS, EXTRA_CSS, build_html, build_artist_json  # noqa: E402
from render_landing import _turntable_css  # noqa: E402


class RandomRefinementTests(unittest.TestCase):
    def test_original_visual_and_artist_contracts_stay_intact(self):
        self.assertIn('/* ── 唱盘：先摆一个正方形', EXTRA_CSS)
        self.assertIn('/* 落针冲击', EXTRA_CSS)
        self.assertIn('right:3%; bottom:5.6%', _turntable_css())
        self.assertNotIn(':root', EXTRA_CSS, 'random refinement must not replace the shared color system')
        page = build_html(2169)
        self.assertIn('今天听点别的', page)
        self.assertIn('class="cat-wrap"', page)
        self.assertIn('Space+Mono', page)
        self.assertIn('class="site-links"', page)
        data = json.loads(build_artist_json([{'id':'a', 'artist':'A', 'title':'First'}, {'id':'b', 'artist':'A', 'title':'Second'}], {}))
        self.assertEqual(data['A']['i'], ['First', 'Second'])

    def test_search_and_loading_have_native_labels(self):
        page = build_html(2169)
        for text in ('for="f-search"', 'for="f-mood"', 'for="f-genre"', 'for="f-decade"',
                     'id="f-search" type="search"', 'role="slider"', 'id="play-status" role="status"',
                     'id="search-results" hidden', 'id="roll" type="button" disabled'):
            self.assertIn(text, page)
        self.assertNotIn('localStorage', JS)

    def test_client_state_and_playback_regressions(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node.js required for deterministic JavaScript state tests')
        harness = Path(__file__).with_name('random_refinement_fixture.js').read_text(encoding='utf-8-sig')
        harness = harness.replace('__SOURCE__', json.dumps(JS))
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / 'random-refinement.js'
            script.write_text(harness, encoding='utf-8')
            result = subprocess.run([node, str(script)], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS: random refinement regressions', result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
