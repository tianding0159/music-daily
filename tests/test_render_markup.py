"""Inspect rendered HTML semantics rather than checking template source strings."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import render_grid


class Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent

    def has_class(self, name):
        return name in self.attrs.get("class", "").split()

    def ancestors(self):
        current = self.parent
        while current:
            yield current
            current = current.parent


class Document(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.nodes, self.stack = [], []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.stack[-1] if self.stack else None)
        self.nodes.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)


def fixture(**overrides):
    return {"id": "apple:42", "title": "A Song", "artist": "Artist", "album": "Album", "year": "2020",
            "genres": ["dream pop"], "mood_tags": ["tender"], "artist_oneliner": "An artist.",
            "why": "A recommendation.", "scene": "A scene.", "bpm_band": "80–100",
            "source": "Source", "source_url": "https://example.test/source",
            "_cover": "https://example.test/cover.jpg", "_preview": "https://example.test/preview.m4a",
            "_apple": "https://music.apple.com/test/42", **overrides}


class RenderMarkupTests(unittest.TestCase):
    def setUp(self):
        context = patch.object(render_grid, "ARTIST_CTX", {})
        context.start()
        self.addCleanup(context.stop)

    def daily(self, item=None, **kwargs):
        return render_grid.build_html("2020-01-03", [item or fixture()], 2,
                                      "Fixture Playlist\nA Song - Artist", **kwargs)

    def assert_navigation(self, html, base, active_path):
        document = Document(html)
        nav_links = [node for node in document.nodes if node.tag == "a" and
                     any(parent.tag == "nav" and parent.has_class("site-nav") for parent in node.ancestors())]
        resolved = {urljoin(base, node.attrs.get("href", "")) for node in nav_links}
        site = "https://example.test/music-daily/"
        self.assertTrue({site + path for path in ("index.html", "daily.html", "random.html", "archive/index.html")}.issubset(resolved))
        current = [node for node in nav_links if node.attrs.get("aria-current") == "page"]
        self.assertEqual(len(current), 1)
        self.assertEqual(urljoin(base, current[0].attrs["href"]), site + active_path)
        ids = {node.attrs["id"] for node in document.nodes if "id" in node.attrs}
        self.assertEqual(sum(node.tag == "main" and node.attrs.get("id") == "main" for node in document.nodes), 1)
        for node in document.nodes:
            href = node.attrs.get("href", "")
            if node.tag == "a" and href.startswith("#"):
                self.assertIn(href[1:], ids)

    def test_daily_navigation_and_previous_issue_links(self):
        html = self.daily(prev_date="2020-01-02")
        base = "https://example.test/music-daily/daily.html"
        self.assert_navigation(html, base, "daily.html")
        previous = next(node for node in Document(html).nodes if node.attrs.get("rel") == "prev")
        self.assertEqual(urljoin(base, previous.attrs["href"]), "https://example.test/music-daily/archive/2020-01-02.html")

    def test_archive_issue_links_resolve_within_correct_directories(self):
        html = self.daily(archive_href="index.html", random_href="../random.html",
                          prev_date="2020-01-02", next_date="2020-01-04")
        base = "https://example.test/music-daily/archive/2020-01-03.html"
        self.assert_navigation(html, base, "archive/index.html")
        document = Document(html)
        for relation, day in (("prev", "2020-01-02"), ("next", "2020-01-04")):
            link = next(node for node in document.nodes if node.attrs.get("rel") == relation)
            self.assertEqual(urljoin(base, link.attrs["href"]), f"https://example.test/music-daily/archive/{day}.html")
        manifest = next(node for node in document.nodes if node.attrs.get("rel") == "manifest")
        self.assertEqual(urljoin(base, manifest.attrs["href"]), "https://example.test/music-daily/manifest.webmanifest")

    def test_archive_index_navigation_and_issue_links(self):
        html = render_grid.build_archive_index([{"date": "2020-01-03", "issue_no": 2, "n": 30, "playlist_title": "A Playlist"}])
        base = "https://example.test/music-daily/archive/index.html"
        self.assert_navigation(html, base, "archive/index.html")
        row = next(node for node in Document(html).nodes if node.has_class("archive-row"))
        self.assertEqual(urljoin(base, row.attrs["href"]), "https://example.test/music-daily/archive/2020-01-03.html")

    def test_untrusted_metadata_stays_text_and_attribute_values(self):
        payload = '\"><img data-injected="yes" src="x" onerror="alert(1)"></script><script data-injected="yes">bad()</script>&'
        item = fixture(title=payload, artist=payload, album=payload, why=payload, scene=payload,
                       artist_oneliner=payload, source=payload, genres=[payload],
                       _cover="https://example.test/" + payload,
                       _preview="https://example.test/" + payload,
                       _apple="https://example.test/" + payload)
        document = Document(self.daily(item))
        self.assertFalse(any("data-injected" in node.attrs for node in document.nodes))
        self.assertFalse(any(key.lower().startswith("on") for node in document.nodes for key in node.attrs))
        opener = next(node for node in document.nodes if node.has_class("cover-open"))
        self.assertEqual(opener.attrs["data-title"], payload)
        self.assertEqual(opener.attrs["data-artist"], payload)
        self.assertIn(payload, next(node.attrs["content"] for node in document.nodes
                      if node.tag == "meta" and node.attrs.get("property") == "og:description"))
        archive = Document(render_grid.build_archive_index([{"date": "2020-01-03", "issue_no": 1, "n": 1, "playlist_title": payload}]))
        self.assertFalse(any("data-injected" in node.attrs for node in archive.nodes))

    def test_cover_and_preview_are_separate_native_controls(self):
        document = Document(self.daily())
        opener = next(node for node in document.nodes if node.has_class("cover-open"))
        preview = next(node for node in document.nodes if node.has_class("pbtn"))
        self.assertEqual((opener.tag, opener.attrs.get("type")), ("button", "button"))
        self.assertEqual((preview.tag, preview.attrs.get("type")), ("button", "button"))
        self.assertIs(opener.parent, preview.parent)
        self.assertTrue(opener.attrs.get("aria-label"))
        self.assertTrue(preview.attrs.get("aria-label"))
        def interactive(node):
            return node.tag in {"a", "button", "input", "select", "textarea", "summary"} or node.attrs.get("role") == "button"
        for node in document.nodes:
            if interactive(node):
                self.assertFalse(any(interactive(parent) for parent in node.ancestors()),
                                 f"Nested interactive control: {node.tag} {node.attrs}")


if __name__ == "__main__":
    unittest.main()
