"""Landing navigation and rendering regressions. Runs without browser or network."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import render_landing


class Page(HTMLParser):
    def __init__(self, source: str):
        super().__init__()
        self.elements = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class LandingNavigationTests(unittest.TestCase):
    def setUp(self):
        self.html = render_landing.build_html(42, 2169, "2026-09-07")
        self.page = Page(self.html)

    def test_all_destinations_are_native_links_without_javascript(self):
        """The old start button was unusable without JS and swallowed Enter anywhere."""
        links = [attrs for tag, attrs in self.page.elements if tag == "a"]
        self.assertTrue({"daily.html", "random.html", "archive/index.html"}.issubset(
            {link.get("href") for link in links}))
        start = next(link for link in links if link.get("id") == "pw")
        self.assertEqual(start["href"], "daily.html")
        self.assertNotIn("onclick", start)
        self.assertNotIn("keydown", render_landing.LANDING_JS)
        self.assertNotIn("location.href", render_landing.LANDING_JS)
        self.assertNotIn("preventDefault", render_landing.LANDING_JS)

    def test_skip_link_and_heading_targets_exist(self):
        ids = {attrs.get("id") for _, attrs in self.page.elements if attrs.get("id")}
        for tag, attrs in self.page.elements:
            if tag == "a" and attrs.get("href", "").startswith("#"):
                self.assertIn(attrs["href"][1:], ids)
            if "aria-labelledby" in attrs:
                for target in attrs["aria-labelledby"].split():
                    self.assertIn(target, ids)
        self.assertEqual(sum(tag == "h1" for tag, _ in self.page.elements), 1)
        self.assertEqual(sum(tag == "main" for tag, _ in self.page.elements), 1)

    def test_latest_date_is_text_even_inside_vinyl_svg(self):
        """Dates feed SVG text, metadata and visible text; none should create tags."""
        source = render_landing.build_html(1, 30, '<img src=x onerror="alert(1)">')
        parsed = Page(source)
        self.assertFalse(any(tag == "img" for tag, _ in parsed.elements))
        self.assertFalse(any("onerror" in attrs for _, attrs in parsed.elements))

    def test_metadata_keeps_pool_count_distinct_from_daily_count(self):
        description = next(attrs["content"] for tag, attrs in self.page.elements
                           if tag == "meta" and attrs.get("property") == "og:description")
        self.assertIn("曲池 2169 首", description)
        self.assertIn("每天精选 30 首", self.html)
        self.assertIn('datetime="2026-09-07"', self.html)
        self.assertIn("08:11", self.html)

    def test_turntable_geometry_does_not_depend_on_content_height(self):
        css = render_landing._turntable_css() + render_landing.LANDING_CSS
        self.assertIn(".tt .arm", css)
        self.assertIn(".deckbox.tt{container-type:normal", css)
        self.assertIn("aspect-ratio:1", css)
        self.assertIn("prefers-reduced-motion:reduce", css)
        self.assertNotIn("body.go", render_landing.LANDING_CSS)


if __name__ == "__main__":
    unittest.main()
