"""Discovery metadata rendering and client interactions, without browser/network access."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from render_discover import _normalize, _url, build_html  # noqa: E402
from ui_common import UI_JS  # noqa: E402


class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.scripts = []
        self.ids = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "a":
            self.links.append(attributes.get("href", ""))
        if tag == "script":
            self.scripts.append(attributes)
        if attributes.get("id"):
            self.ids.append(attributes["id"])


class DiscoveryUIRegression(unittest.TestCase):
    def test_metadata_urls_and_script_boundaries(self):
        track = {"review_id": 'id"unsafe', "title": '</script><img src=x onerror=alert(1)>',
                 "artist": 'Artist "quote" & Co', "album": "Album <b>literal</b>",
                 "duration_ms": 90000, "apple_genre": "Electronic", "apple_edition_year": 2001,
                 "apple_url": "javascript:alert(1)", "artwork_url": "https://evil.example/image.jpg",
                 "preview_url": "https://audio-ssl.itunes.apple.com/preview.m4a"}
        normalized = _normalize([track])[0]
        self.assertEqual(normalized["apple"], "")
        self.assertEqual(normalized["cover"], "")
        self.assertTrue(normalized["preview"].startswith("https://audio-ssl.itunes.apple.com/"))
        page = build_html([track])
        self.assertNotIn('</script><img src=x', page)
        self.assertIn('&lt;/script&gt;&lt;img src=x onerror=alert(1)&gt;', page)
        parser = LinkCollector()
        parser.feed(page)
        self.assertEqual(len(parser.scripts), 2, "catalog text cannot open a new script")
        self.assertEqual(len(parser.ids), len(set(parser.ids)), "page IDs must be unique")
        self.assertNotIn("", parser.links, "rejected platform URL must not create an empty link")
        self.assertFalse(any(link.startswith("javascript:") for link in parser.links))
        self.assertEqual(_url("https://music.apple.com@evil.example/track", {"music.apple.com"}), "")
        self.assertEqual(_url("https://[invalid", {"music.apple.com"}), "")

    def test_pagination_without_javascript_and_accurate_discovery_copy(self):
        tracks = [{"review_id": str(i), "title": f"Track {i}", "artist": "Artist A",
                   "apple_url": "https://music.apple.com/album/example", "duration_ms": 30000}
                  for i in range(73)]
        page = build_html(tracks)
        self.assertEqual(page.count('<article class="discovery-track"'), 36)
        self.assertIn('1 / 3', page)
        self.assertIn("仍待逐首精选", page)
        self.assertIn('type="application/json"', page)
        self.assertIn('role="slider"', page)

    def test_client_regressions(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for the browser-state fixture")
        base = Path(__file__).with_name("random_ui_fixture.js").read_text(encoding="utf-8-sig").split("function fixture(){", 1)[0]
        script = base + Path(__file__).with_name("discover_ui_fixture.js").read_text(encoding="utf-8-sig")
        script = script.replace("__UI_JS__", json.dumps(UI_JS))
        script = script.replace("__DISCOVER_JS__", json.dumps((ROOT / "scripts/discover_ui.js").read_text(encoding="utf-8")))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "discovery-ui-regressions.js"
            path.write_text(script, encoding="utf-8")
            result = subprocess.run([node, str(path)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("discovery UI regressions: PASS", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
