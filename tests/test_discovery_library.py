"""Data-only discovery integration: no network, no template or daily-pool changes."""
from __future__ import annotations

import copy
import hashlib
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
import render_random


def discovery(tid="123", artist="Björk", title="Jóga", **changes):
    result = {"review_id": "apple:" + tid, "apple_track_id": tid,
              "status": "listening_and_editorial_review_required", "artist": artist,
              "title": title, "album": "Homogenic", "apple_edition_year": "1997",
              "apple_genre": "Electronic", "artwork_url": "https://is1-ssl.mzstatic.com/test/600x600bb.jpg",
              "preview_url": "https://audio-ssl.itunes.apple.com/test.m4a",
              "apple_url": "https://music.apple.com/us/album/test/123?i=" + tid}
    result.update(changes)
    return result


def curated(tid="apple:50", **changes):
    result = {"id": tid, "artist": "Original Artist", "title": "Original Track",
              "album": "Original Album", "year": "2001", "genres": ["indie pop"],
              "has_melody": True, "artist_oneliner": "Existing artist text",
              "why": "Existing listening judgment", "scene": "Existing scene",
              "mood_tags": ["warm"], "bpm_band": "80-100", "fit_score": 90,
              "_cover": "existing-cover", "_preview": "existing-preview", "_apple": "existing-link"}
    result.update(changes)
    return result


class DiscoveryLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.data, self.site = self.base / "data", self.base / "site"
        self.data.mkdir()
        self.patches = [patch.object(daily, "DATA", self.data), patch.object(daily, "SITE", self.site),
                        patch.object(daily, "MEDIA", self.data / "pool_media.json"),
                        patch.object(daily, "ISSUES", self.data / "issues")]
        for p in self.patches:
            p.start()
        self.addCleanup(self.tmp.cleanup)
        for p in self.patches:
            self.addCleanup(p.stop)
        self.put("pool.json", [curated()])
        self.put("artists.json", [{"artist": "Björk", "bio": "Existing biography"}])

    def put(self, name, value):
        (self.data / name).write_text(json.dumps(value, ensure_ascii=True), encoding="ascii")

    def queue(self, tracks):
        self.put("discovery.json", {"schema": 1, "status": "discovery_not_curated", "tracks": tracks})

    def site_hashes(self):
        return {str(p.relative_to(self.site)): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.site.rglob("*") if p.is_file()}

    def test_absent_data_retains_original_renderer_output(self):
        original = [curated()]
        self.assertEqual(daily.write_random_assets(original), 1)
        self.assertEqual((self.site / "pool.min.json").read_text(encoding="utf-8"), render_random.build_pool_json(original))
        self.assertEqual((self.site / "random.html").read_text(encoding="utf-8"), render_random.build_html(1))
        self.assertEqual(daily._n_eligible(), 1)

    def test_projection_is_explicit_pending_metadata_and_idempotent(self):
        source = discovery(has_melody=True, fit_score=100, bpm_band="90-100", mood_tags=["warm"], why="Do not inherit", scene="Do not inherit")
        self.queue([source])
        original = [curated()]
        before = copy.deepcopy(original)
        combined = daily._random_catalog_items(original)
        self.assertEqual(original, before)
        self.assertEqual(combined[0], before[0])
        self.assertEqual(daily._random_catalog_items(combined), combined)
        added = combined[-1]
        self.assertEqual(added["id"], source["review_id"])
        self.assertEqual(added["_preview"], source["preview_url"])
        self.assertEqual(added["genres"], ["electronic"])
        self.assertIn("待精选", added["artist_oneliner"])
        self.assertIn("Apple 当前发行版本年份", added["why"])
        self.assertIn("听感仍待核实", added["why"])
        for unknown in ("has_melody", "fit_score", "bpm_band", "mood_tags", "scene", "production_tags"):
            self.assertNotIn(unknown, added)
        self.assertEqual(daily.write_random_assets(original), 2)
        first = self.site_hashes()
        self.assertEqual(daily.write_random_assets(original), 2)
        self.assertEqual(first, self.site_hashes())
        self.assertEqual(daily._n_eligible(), 2)

    def test_promoted_curated_records_win_by_id_apple_id_and_work(self):
        originals = [curated("apple:123", artist="Other", title="Other"),
                     curated("sha1:promoted", apple_track_id="124", artist="Alias", title="Alias"),
                     curated("apple:999", artist="Bjork", title="Joga - 2011 Remaster")]
        self.put("pool.json", originals)
        self.queue([discovery(), discovery("124", title="Alternate"), discovery("125")])
        self.assertEqual(daily._random_catalog_items(originals), originals)
        self.assertEqual(daily.write_random_assets(originals), 3)
        self.assertEqual(daily._n_eligible(), 3)
        # A curated but temporarily ineligible work must not re-enter as discovery.
        self.assertEqual(daily._random_catalog_items([]), [])

    def test_duplicate_queue_records_and_unicode_titles(self):
        self.queue([discovery(), discovery("999", artist="Bjork", title="Joga"),
                    discovery("222", artist="dosii", title="사랑"), discovery("223", artist="dosii", title="밤")])
        added = daily._random_catalog_items([])
        self.assertEqual(len(added), 3)
        self.assertEqual([t["title"] for t in added], ["Jóga", "사랑", "밤"])

    def test_plain_live_title_is_not_a_version_suffix(self):
        real_title = {"artist": "Roy Ayers Ubiquity", "title": "We Live in Brooklyn, Baby"}
        self.assertNotEqual(daily._discovery_work_key(real_title), daily._discovery_work_key(dict(real_title, title="We")))
        self.assertEqual(daily._discovery_work_key(real_title)[1], "weliveinbrooklynbaby")
        self.assertEqual(daily._discovery_work_key(real_title), daily._discovery_work_key(dict(real_title, title="We Live in Brooklyn, Baby Remastered 2011")))

    def test_invalid_future_records_fail_before_any_site_write(self):
        self.queue([discovery()])
        daily.write_random_assets([curated()])
        previous = self.site_hashes()
        bad = [discovery(title="<img src=x onerror=alert(1)>"), discovery(artist=[]),
               discovery(apple_genre={"bad": "genre"}), discovery(apple_edition_year=1997),
               discovery(status="curated"), discovery(review_id="sha1:fake"),
               discovery(preview_url="https://audio-ssl.itunes.apple.com.evil.example/test.m4a"),
               discovery(apple_url="javascript:alert(1)"), discovery(artwork_url="https://[invalid"),
               discovery(apple_url='https://music.apple.com/" onclick="alert(1)')]
        for record in bad:
            with self.subTest(record=record):
                self.queue([record])
                with self.assertRaises(ValueError):
                    daily.write_random_assets([curated()])
                self.assertEqual(previous, self.site_hashes())
        for malformed in ([discovery()], None, {}):
            self.put("discovery.json", malformed)
            with self.assertRaises(ValueError):
                daily.write_random_assets([curated()])
            self.assertEqual(previous, self.site_hashes())

    def test_real_1169_plus_1000_offline_without_daily_data_mutation(self):
        shutil.copytree(ROOT / "data", self.data, dirs_exist_ok=True)
        all_files = list(self.data.rglob("*.json"))
        before = {p.relative_to(self.data).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in all_files}
        pool = json.loads((self.data / "pool.json").read_text(encoding="utf-8"))
        source = json.loads((self.data / "discovery.json").read_text(encoding="utf-8"))["tracks"]
        media = json.loads((self.data / "pool_media.json").read_text(encoding="utf-8"))
        self.assertEqual(len(pool), 1169)
        self.assertEqual(len(source), 1000)
        existing = [dict(t, _cover=media.get(t["id"], {}).get("c", ""),
                         _preview=media.get(t["id"], {}).get("p", ""),
                         _apple=media.get(t["id"], {}).get("a", ""))
                    for t in pool if daily.selector.is_eligible(t)[0]]
        old_projection = json.loads(render_random.build_pool_json(existing))
        with patch("urllib.request.urlopen", side_effect=AssertionError("offline build must not access network")):
            self.assertEqual(daily._build_random(pool, use_itunes=False), 2169)
            self.assertEqual(daily._n_eligible(), 2169)
        visible = json.loads((self.site / "pool.min.json").read_text(encoding="utf-8"))
        self.assertEqual(visible[:1169], old_projection)
        self.assertEqual(len(visible), len({t["id"] for t in visible}))
        for row, raw in zip(visible[1169:], source):
            self.assertEqual(row["id"], raw["review_id"])
            self.assertEqual((row["c"], row["p"], row["a"]), (raw["artwork_url"], raw["preview_url"], raw["apple_url"]))
            self.assertIn("待精选", row["artist_oneliner"])
            self.assertNotIn("bpm_band", row)
            self.assertNotIn("mood_tags", row)
            self.assertNotIn("scene", row)
        self.assertIn("2169", (self.site / "random.html").read_text(encoding="utf-8"))
        self.assertEqual(before, {p.relative_to(self.data).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in all_files})

    def test_all_three_production_paths_share_the_integration(self):
        for name in ("publish-site.yml", "import-bios.yml"):
            source = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            self.assertIn("build_daily.write_random_assets(items)", source)
        source = (ROOT / "scripts/build_daily.py").read_text(encoding="utf-8")
        self.assertIn("return write_random_assets(items)", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
