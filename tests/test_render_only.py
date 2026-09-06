"""Exercise the real render-only CLI against disposable data and output folders."""
from __future__ import annotations

from contextlib import ExitStack, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_daily


def track(identifier: str, title: str, **overrides) -> dict:
    return {"id": identifier, "title": title, "artist": "Test Artist", "album": "Test Album",
            "year": "2020", "genres": ["dream pop"], "mood_tags": ["tender", "warm"],
            "has_melody": True, "bpm_band": "80–100", "fit_score": 90,
            "artist_oneliner": "A fixture artist.", "why": "A fixture recommendation.",
            "scene": "A fixture scene.", "source": "Fixture", "source_url": "https://example.test/source",
            **overrides}


class RenderOnlyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="music-daily-render-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = self.root / "data"
        self.site = self.root / "site"
        self.issues = self.data / "issues"
        self.issues.mkdir(parents=True)
        (self.site / "archive").mkdir(parents=True)
        self.media_path = self.data / "pool_media.json"
        self.pool = [track("apple:1", "Cached Song", _cover="https://ignored.test/pool.jpg"),
                     track("apple:2", "Uncached Song"),
                     track("apple:3", "Excluded Song", has_melody=False)]
        self.write(self.data / "pool.json", self.pool)
        # A missing old snapshot is intentional: render-only must not backfill it.
        self.write(self.data / "history.json", {"2020-01-01": ["apple:1"],
                   "2020-01-02": ["apple:1"], "2020-01-03": ["apple:2"]})
        self.write(self.data / "latest.json", {"date": "2020-01-03", "notified": True,
                   "notification_proof": "must remain byte-for-byte unchanged"})
        self.write(self.media_path, {"apple:1": {"c": "https://cached.test/cover.jpg",
                   "p": "https://cached.test/preview.m4a", "a": "https://music.apple.com/test/1"}})
        self.write(self.data / "artists.json", [{"artist": "Test Artist", "bio": "Fixture biography."}])
        self.write(self.data / "itunes_cache.json", {"do-not-rewrite": True})
        for number, date, item in ((1, "2020-01-02", self.pool[0]), (2, "2020-01-03", self.pool[1])):
            snapshot_track = dict(item, _cover=f"https://snapshot.test/{number}.jpg",
                                  _preview="", _apple="")
            self.write(self.issues / f"{date}.json", {"date": date, "issue_no": number,
                       "theme": "grid", "playlist_title": f"Fixture issue {number}",
                       "netease_text": f"Fixture issue {number}\n{item['title']} - Test Artist",
                       "tracks": [snapshot_track], "generated_at": "2020-01-03T00:00:00Z"})
        self.static_assets = {"manifest.webmanifest": b'{"name":"static fixture"}',
                              "icon-192.png": b"static-icon-fixture"}
        for name, content in self.static_assets.items():
            (self.site / name).write_bytes(content)
        (self.site / "archive" / "stale.html").write_text("old generated output", encoding="utf-8")
        self.patches = ExitStack()
        self.addCleanup(self.patches.close)
        self.patches.enter_context(patch.multiple(build_daily, ROOT=self.root, DATA=self.data,
                                  SITE=self.site, ISSUES=self.issues, MEDIA=self.media_path))
        self.patches.enter_context(patch.object(build_daily.render_grid, "ARTIST_CTX", {}))
        # These are external or editorial boundaries, not renderer implementations.
        for target, method in ((build_daily.itunes, "lookup"), (build_daily.itunes, "save_cache"),
                               (build_daily.selector, "select_daily"), (build_daily.push_wechat, "push")):
            self.patches.enter_context(patch.object(target, method,
                side_effect=AssertionError(f"render-only crossed forbidden boundary: {method}")))
        self.patches.enter_context(patch("urllib.request.urlopen",
            side_effect=AssertionError("render-only made a network request")))

    @staticmethod
    def write(path: Path, value) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def files(folder: Path, with_mtime: bool = False) -> dict:
        return {str(path.relative_to(folder)): (path.read_bytes(), path.stat().st_mtime_ns)
                if with_mtime else path.read_bytes()
                for path in folder.rglob("*") if path.is_file()}

    def run_cli(self, *arguments) -> str:
        output = io.StringIO()
        with patch.object(sys, "argv", ["build_daily.py", "--render-only", *arguments]), redirect_stdout(output):
            build_daily.main()
        return output.getvalue()

    def test_renders_existing_issues_without_advancing_or_rewriting_data(self):
        before = self.files(self.data, with_mtime=True)
        self.run_cli("--date", "2099-12-31")
        self.assertEqual(self.files(self.data, with_mtime=True), before)
        expected = {"index.html", "daily.html", "random.html", "pool.min.json", "artists.min.json",
                    "archive/index.html", "archive/2020-01-02.html", "archive/2020-01-03.html"}
        generated = {path.relative_to(self.site).as_posix() for path in self.site.rglob("*") if path.is_file()}
        self.assertTrue(expected.issubset(generated))
        self.assertNotIn("archive/2099-12-31.html", generated)
        self.assertNotIn("archive/2020-01-01.html", generated)
        self.assertNotIn("archive/stale.html", generated)
        self.assertIn("Uncached Song", (self.site / "daily.html").read_text(encoding="utf-8"))
        self.assertIn("https://snapshot.test/2.jpg", (self.site / "daily.html").read_text(encoding="utf-8"))
        for name, content in self.static_assets.items():
            self.assertEqual((self.site / name).read_bytes(), content)

    def test_random_library_uses_existing_media_and_does_not_fill_missing_entries(self):
        self.run_cli()
        items = {item["id"]: item for item in json.loads((self.site / "pool.min.json").read_text(encoding="utf-8"))}
        self.assertEqual(set(items), {"apple:1", "apple:2"})
        self.assertEqual((items["apple:1"]["c"], items["apple:1"]["p"], items["apple:1"]["a"]),
                         ("https://cached.test/cover.jpg", "https://cached.test/preview.m4a", "https://music.apple.com/test/1"))
        self.assertEqual((items["apple:2"]["c"], items["apple:2"]["p"], items["apple:2"]["a"]), ("", "", ""))
        self.assertEqual(set(json.loads(self.media_path.read_text(encoding="utf-8"))), {"apple:1"})
        bios = json.loads((self.site / "artists.min.json").read_text(encoding="utf-8"))
        self.assertEqual(bios["Test Artist"]["b"], "Fixture biography.")

    def test_repeated_render_is_deterministic_and_does_not_clear_notified_state(self):
        self.run_cli()
        output = self.files(self.site)
        before = self.files(self.data, with_mtime=True)
        self.run_cli()
        self.assertEqual(self.files(self.site), output)
        self.assertEqual(self.files(self.data, with_mtime=True), before)

    def test_conflicting_flags_fail_before_data_or_site_changes(self):
        for flag in ("--push", "--force-rebuild"):
            with self.subTest(flag=flag):
                before = self.files(self.root, with_mtime=True)
                with self.assertRaises(SystemExit):
                    self.run_cli(flag)
                self.assertEqual(self.files(self.root, with_mtime=True), before)


if __name__ == "__main__":
    unittest.main()
