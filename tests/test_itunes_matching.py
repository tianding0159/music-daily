"""Offline regression tests for precise iTunes identity and version matching."""
from __future__ import annotations

from pathlib import Path
import sys
import unicodedata
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import itunes


def record(title: str, artist: str = "Artist") -> dict:
    return {"artistName": artist, "trackName": title, "trackId": 42,
            "artworkUrl100": "https://example.test/100x100bb.jpg"}


class IdentityTests(unittest.TestCase):
    def test_embedded_version_fragments_are_plain_titles(self):
        for title in ("Deliver", "Believe", "Meditation", "Mixed Feelings", "Uncovered"):
            with self.subTest(title=title):
                self.assertEqual(itunes._versions(title), set())
                self.assertEqual(itunes.classify("Artist", title, [record(title)])[0], "exact_match")

    def test_embedded_fragments_cannot_cancel_real_versions(self):
        for title, version in (("Deliver", "Live"), ("Meditation", "Edit"),
                               ("Mixed Feelings", "Mix"), ("Uncovered", "Cover")):
            with self.subTest(title=title):
                self.assertEqual(itunes.classify("Artist", title,
                                 [record(f"{title} ({version})")])[0], "version_mismatch")

    def test_versions_are_checked_in_both_directions(self):
        for version in ("Live", "Remix", "Remastered", "Radio Edit", "Single Edit",
                        "Acoustic", "Instrumental", "Demo", "Extended", "Karaoke"):
            with self.subTest(version=version):
                original, variant = "A Song", f"A Song ({version})"
                self.assertEqual(itunes.classify("Artist", original, [record(variant)])[0], "version_mismatch")
                self.assertEqual(itunes.classify("Artist", variant, [record(original)])[0], "version_mismatch")
                self.assertEqual(itunes.classify("Artist", variant, [record(variant)])[0], "exact_match")

    def test_equivalent_version_wording_and_punctuation(self):
        for candidate, actual in (("A Song (Remastered)", "A Song (Remaster)"),
                                  ("A Song (Remixed)", "A Song (Remix)"),
                                  ("A Song (Re-recorded)", "A Song (Rerecorded)"),
                                  ("A Song (Acoustic Version)", "A Song (Acoustic)"),
                                  ("A Song (Live)", "A Song — Live"),
                                  ("A Song （Radio Edit）", "A Song – Radio Edit")):
            with self.subTest(candidate=candidate, actual=actual):
                self.assertEqual(itunes.classify("Artist", candidate, [record(actual)])[0], "exact_match")
        self.assertEqual(itunes.classify("Artist", "A Song (Radio Edit)",
                         [record("A Song (Single Edit)")])[0], "version_mismatch")

    def test_nonversion_hyphen_suffix_is_still_part_of_title(self):
        self.assertEqual(itunes.classify("Artist", "A Song", [record("A Song - Another Song")])[0], "not_found")
        self.assertEqual(itunes.classify("Artist", "Live Forever", [record("Live Forever")])[0], "exact_match")

    def test_nonversion_parentheses_keep_meaningful_title_words(self):
        self.assertEqual(itunes.classify("Artist", "A Song", [record("A Song (For You)")])[0], "not_found")
        self.assertEqual(itunes.classify("Artist", "A Song (For You)", [record("A Song (For You)")])[0], "exact_match")

    def test_korean_identity_is_preserved_and_normalized(self):
        artist, title = "검정치마", "기다린 만큼, 더"
        self.assertTrue(itunes._key(artist))
        self.assertEqual(itunes._key(artist), artist)
        self.assertEqual(itunes.classify(artist, title, [record(title, artist)])[0], "exact_match")
        self.assertEqual(itunes._key(title), itunes._key(unicodedata.normalize("NFD", title)))
        self.assertEqual(itunes.classify("Artist", "사랑", [record("행복")])[0], "not_found")

    def test_non_latin_names_do_not_collapse_or_impersonate_latin_names(self):
        for name in ("검정치마", "Молчат Дома", "محمد", "अनुष्का"):
            with self.subTest(name=name):
                self.assertTrue(itunes._key(name))
                self.assertEqual(itunes.classify("Artist", "A Song", [record("A Song", name)])[0], "artist_mismatch")
                self.assertEqual(itunes.classify(name, "A Song", [record("A Song", name)])[0], "exact_match")
        self.assertNotEqual(itunes._key("が"), itunes._key("か"))

    def test_aliases_and_latin_accents_still_match(self):
        self.assertEqual(itunes.classify("The Black Skirts (검정치마)", "A Song",
                         [record("A Song", "검정치마")])[0], "exact_match")
        self.assertEqual(itunes._key("Björk"), itunes._key("Bjork"))
        self.assertEqual(itunes._key("María También"), itunes._key("Maria Tambien"))
        self.assertEqual(itunes.classify("Beach House", "A Song",
                         [record("A Song", "Beach House feat. X")])[0], "acceptable_match")

    def test_empty_or_too_short_substrings_do_not_pass_artist_gate(self):
        for actual in ("", "!", "A", "Art"):
            with self.subTest(actual=actual):
                self.assertEqual(itunes.classify("Artist", "A Song", [record("A Song", actual)])[0], "artist_mismatch")
        self.assertEqual(itunes.classify("Artist", "!", [record("?")])[0], "not_found")
        self.assertEqual(itunes.classify("!", "A Song", [record("A Song")])[0], "not_found")
        self.assertEqual(itunes.classify("A", "A Song", [record("A Song", "A")])[0], "exact_match")


class CachedLookupTests(unittest.TestCase):
    def test_cached_original_cannot_satisfy_live_request_or_the_reverse(self):
        for cached, wanted in (("A Song", "A Song (Live)"), ("A Song (Live)", "A Song")):
            with self.subTest(cached=cached):
                entry = itunes._mk("exact_match", record(cached), "US")
                cache = {"artist|asong": entry}
                with patch.object(itunes, "_query", return_value=[record(wanted)]) as query:
                    found = itunes.lookup("Artist", wanted, cache)
                query.assert_called_once()
                self.assertEqual(found["matched_title"], wanted)
                self.assertEqual(found["status"], "exact_match")

    def test_valid_cached_media_remains_offline(self):
        entry = itunes._mk("exact_match", record("A Song"), "US")
        with patch.object(itunes, "_query", side_effect=AssertionError("must stay offline")):
            found = itunes.lookup("Artist", "A Song", {"artist|asong": entry})
        self.assertEqual(found["track_id"], 42)

    def test_stale_accepted_wrong_artist_is_requeried(self):
        entry = itunes._mk("acceptable_match", record("A Song", "검정치마"), "US")
        with patch.object(itunes, "_query", return_value=[record("A Song")]) as query:
            found = itunes.lookup("Artist", "A Song", {"artist|asong": entry})
        query.assert_called_once()
        self.assertEqual(found["matched_artist"], "Artist")

    def test_negative_cache_only_reused_for_same_request(self):
        cache = {}
        with patch.object(itunes, "_query", return_value=[]) as query:
            self.assertEqual(itunes.lookup("Artist", "A Song (Live)", cache)["status"], "not_found")
            first_calls = query.call_count
            itunes.lookup("Artist", "A Song (Live)", cache)
            self.assertEqual(query.call_count, first_calls)
        with patch.object(itunes, "_query", return_value=[record("A Song")]) as query:
            self.assertEqual(itunes.lookup("Artist", "A Song", cache)["status"], "exact_match")
        query.assert_called_once()

    def test_title_only_fallback_requires_exact_artist(self):
        with patch.object(itunes, "_query", side_effect=[[], [], [record("A Song", "Artist feat. Other")]]):
            self.assertEqual(itunes.lookup("Artist", "A Song", {})["status"], "not_found")

    def test_invalid_identity_never_queries_or_caches_empty_keys(self):
        cache = {}
        with patch.object(itunes, "_query", side_effect=AssertionError("invalid identity")):
            self.assertEqual(itunes.lookup("!", "?", cache)["status"], "not_found")
        self.assertEqual(cache, {})


if __name__ == "__main__":
    unittest.main()
