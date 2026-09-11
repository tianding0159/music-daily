"""The preview command must render production UI without touching daily data."""
from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_daily as daily


def hashes(directory: Path) -> dict[str, str]:
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob("*") if p.is_file()}


class RenderOnlyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.data, self.site = self.base / "data", self.base / "site"
        shutil.copytree(ROOT / "data", self.data)
        self.site.mkdir()
        # Existing assets and arbitrary local files must survive a page rebuild.
        (self.site / "icon-180.png").write_bytes(b"existing-static-icon")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in (("DATA", self.data), ("SITE", self.site), ("ISSUES", self.data / "issues"),
                            ("MEDIA", self.data / "pool_media.json")):
            self.stack.enter_context(patch.object(daily, name, value))
        self.data_before = hashes(self.data)

    def forbidden_operations(self):
        stack = ExitStack()
        for module, name in ((daily, "_backfill_snapshots"), (daily, "_write_snapshot"),
                             (daily, "enrich"), (daily.selector, "select_daily"),
                             (daily.itunes, "lookup"), (daily.itunes, "save_cache"),
                             (daily.push_wechat, "build_desp"), (daily.push_wechat, "push")):
            stack.enter_context(patch.object(module, name, side_effect=AssertionError(f"render-only must not call {name}")))
        stack.enter_context(patch("urllib.request.urlopen", side_effect=AssertionError("render-only must be offline")))
        return stack

    def run_cli(self, *arguments):
        output = io.StringIO()
        with patch.object(sys, "argv", ["build_daily.py", *arguments]), redirect_stdout(output):
            daily.main()
        return output.getvalue()

    def test_real_cli_keeps_all_data_and_2169_tracks_without_daily_side_effects(self):
        with self.forbidden_operations():
            # Even a date that has no snapshot cannot enter normal daily generation.
            output = self.run_cli("--render-only", "--date", "2099-12-31")
        self.assertIn("2169", output)
        self.assertEqual(self.data_before, hashes(self.data))
        self.assertFalse((self.data / "issues/2099-12-31.json").exists())
        for name in ("index.html", "daily.html", "random.html", "pool.min.json", "artists.min.json", "archive/index.html"):
            self.assertTrue((self.site / name).is_file(), name)
        expected_dates = {p.stem for p in (self.data / "issues").glob("*.json")}
        actual_dates = {p.stem for p in (self.site / "archive").glob("*.html") if p.stem != "index"}
        self.assertEqual(expected_dates, actual_dates)
        pool = json.loads((self.site / "pool.min.json").read_text(encoding="utf-8"))
        self.assertEqual(len(pool), 2169)
        self.assertEqual(len({t["id"] for t in pool}), 2169)
        discoveries = json.loads((self.data / "discovery.json").read_text(encoding="utf-8"))["tracks"]
        by_id = {t["id"]: t for t in pool}
        self.assertEqual(len(discoveries), 1000)
        for source in discoveries:
            track = by_id[source["review_id"]]
            self.assertIn("待精选", track["artist_oneliner"])
            self.assertEqual(track["p"], source["preview_url"])
        self.assertEqual((self.site / "icon-180.png").read_bytes(), b"existing-static-icon")

    def test_output_matches_production_render_chain_and_is_idempotent(self):
        with self.forbidden_operations():
            self.run_cli("--render-only")
            first = hashes(self.site)
            self.run_cli("--render-only", "--no-itunes")
            self.assertEqual(first, hashes(self.site))
            # Compare with the same production rebuild functions, not a second template.
            production_site = self.base / "production-site"
            production_site.mkdir()
            (production_site / "icon-180.png").write_bytes(b"existing-static-icon")
            with patch.object(daily, "SITE", production_site):
                daily._rebuild_site()
                original_pool = json.loads((self.data / "pool.json").read_text(encoding="utf-8"))
                self.assertEqual(daily._build_random(original_pool, use_itunes=False), 2169)
            self.assertEqual(first, hashes(production_site))
        self.assertEqual(self.data_before, hashes(self.data))

    def test_conflicting_mutation_flags_are_rejected_before_rendering(self):
        before_site = hashes(self.site)
        for flag in ("--push", "--force-rebuild"):
            with self.subTest(flag=flag), self.forbidden_operations(), patch.object(daily, "_render_only", side_effect=AssertionError("invalid CLI must not render")), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    self.run_cli("--render-only", flag)
                self.assertEqual(error.exception.code, 2)
        self.assertEqual(before_site, hashes(self.site))
        self.assertEqual(self.data_before, hashes(self.data))

    def test_missing_snapshots_preserve_existing_site_and_never_backfill(self):
        before_site = hashes(self.site)
        with self.forbidden_operations(), patch.object(daily, "ISSUES", self.base / "no-snapshots"):
            with self.assertRaisesRegex(SystemExit, "不会创建新日报"):
                self.run_cli("--render-only")
        self.assertEqual(before_site, hashes(self.site))
        self.assertEqual(self.data_before, hashes(self.data))


if __name__ == "__main__":
    unittest.main(verbosity=2)
