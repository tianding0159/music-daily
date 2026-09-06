"""Fetch album neighbours into an explicitly unreviewed listening queue.

This does not write pool.json, artists.json, itunes_cache.json or candidates/.
Apple metadata verifies identity and release membership; it does not verify
melody, BPM, instrumentation, production, taste fit, or Chinese editorial copy.
The ordinary candidate validator remains the publication gate.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import itunes
import picker


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=True, indent=1) + "\n", encoding="ascii")


def album_key(value: str) -> str:
    return itunes._key(value)


def semantic_key(artist: str, title: str) -> str:
    # Compare the underlying work, including old pool entries whose unparenthesized
    # "- 2011 Remaster" suffix would otherwise permit a new Apple ID duplicate.
    title = re.sub(r"[\(（\[【].*?[\)）\]】]", " ", title)
    version = r"(?:remaster(?:ed)?|remix(?:ed)?|live|rework|edit|acoustic|instrumental|demo|reprise|rerecorded|re[- ]recorded|version|mix)"
    title = re.sub(r"\s*[-–—]\s*(?:(?:\d{4}|stereo|mono|original|digitally|album|single|radio|us|uk|lp)\s+)*" + version + r"\b.*$", "", title, flags=re.I)
    title = re.sub(r"\s+(?:(?:\d{4}|stereo|mono|original|digitally|album|single|radio|us|uk|lp)\s+)*" + version + r"\b.*$", "", title, flags=re.I)
    def key(value: str) -> str:
        raw = unicodedata.normalize("NFKD", value).casefold()
        return "".join(c for c in raw if c.isalnum() and not unicodedata.combining(c))
    return key(artist) + "|" + key(title)


def fetch(url: str, cache_dir: Path, throttle: list[float]) -> dict:
    path = cache_dir / (hashlib.sha256(url.encode()).hexdigest() + ".json")
    if path.exists():
        return json.loads(path.read_text(encoding="ascii"))
    for attempt in range(4):
        time.sleep(max(0, 3.1 - (time.monotonic() - throttle[0])))
        throttle[0] = time.monotonic()
        request = urllib.request.Request(url, headers={"User-Agent": "music-daily/catalog-review"})
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                result = json.load(response)
            if not isinstance(result.get("results"), list):
                raise ValueError("missing Apple results array")
            payload = {"url": url, "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(), "response": result}
            write_json(path, payload)
            return payload
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            if attempt == 3:
                raise RuntimeError(f"Apple lookup failed: {url}: {exc}") from exc
            time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, default=1000)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/catalog-expansion-2026-09-07")
    parser.add_argument("--cache", type=Path, default=ROOT / ".backup/catalog-source-2026-09-07")
    args = parser.parse_args()
    if args.target < 1:
        parser.error("target must be positive")
    pool = json.loads((ROOT / "data/pool.json").read_text(encoding="utf-8"))
    bios = json.loads((ROOT / "data/artists.json").read_text(encoding="utf-8"))
    bio_artists = {a["artist"] for a in bios}
    existing_keys = {semantic_key(t["artist"], t["title"]) for t in pool}
    existing_ids = {str(t.get("apple_track_id")) for t in pool if t.get("apple_track_id")}
    seeds: dict[str, list[dict]] = collections.defaultdict(list)
    for track in pool:
        collection = str(track.get("apple_collection_id") or "")
        if collection and track["artist"] in bio_artists and not set(track.get("genres", [])).intersection(picker.BLACKLIST):
            seeds[collection].append(track)
    ids = sorted(seeds)
    selected: list[dict] = []
    selected_sources: dict[str, dict] = {}
    seen = set(existing_keys)
    seen_ids = set(existing_ids)
    artists: collections.Counter = collections.Counter()
    exclusions: collections.Counter = collections.Counter()
    queries: list[dict] = []
    throttle = [0.0]
    # One request returns all tracks belonging to multiple already-curated albums.
    # Respect Apple's approximately 20 requests/minute limit and keep source receipts.
    for offset in range(0, len(ids), 20):
        batch = ids[offset:offset + 20]
        url = "https://itunes.apple.com/lookup?" + urllib.parse.urlencode(
            {"id": ",".join(batch), "entity": "song", "limit": 200, "country": "US"})
        receipt = fetch(url, args.cache, throttle)
        results = receipt["response"]["results"]
        albums = {str(r["collectionId"]): r for r in results if r.get("wrapperType") == "collection"}
        query_hash = hashlib.sha256(json.dumps(receipt, ensure_ascii=True, sort_keys=True).encode()).hexdigest()
        queries.append({"url": url, "fetched_at": receipt["fetched_at"], "result_count": len(results), "receipt_sha256": query_hash})
        for result in results:
            if result.get("kind") != "song":
                continue
            collection_id = str(result.get("collectionId") or "")
            album = albums.get(collection_id)
            if not album:
                exclusions["missing_album_record"] += 1
                continue
            matches = []
            for seed in seeds.get(collection_id, []):
                status, _ = itunes.classify(seed["artist"], result.get("trackName", ""), [result])
                if status == "exact_match" and album_key(seed["album"]) == album_key(album.get("collectionName", "")):
                    matches.append((seed, status))
            if not matches:
                exclusions["seed_artist_or_album_mismatch"] += 1
                continue
            seed, match_status = matches[0]
            title = result.get("trackName", "").strip()
            artist = seed["artist"]
            tid = str(result.get("trackId") or "")
            key = semantic_key(artist, title)
            ak = itunes._key(artist)
            if key in seen or tid in seen_ids:
                exclusions["duplicate_title_or_apple_id"] += 1
                continue
            if artists[ak] >= 3:
                exclusions["artist_cap"] += 1
                continue
            # Reject explicitly variant recordings instead of silently rewriting titles.
            if itunes._versions(title) or re.search(r"\b(intro|outro|interlude|bonus track)\b", title, re.I):
                exclusions["variant_or_interlude"] += 1
                continue
            duration = int(result.get("trackTimeMillis") or 0)
            if duration < 120000 or duration > 480000:
                exclusions["duration_outside_review_range"] += 1
                continue
            if not result.get("previewUrl", "").startswith("https://") or not result.get("trackViewUrl", "").startswith("https://"):
                exclusions["missing_https_preview_or_track_link"] += 1
                continue
            # Track releaseDate can differ from the containing release: use the album
            # object's date, retain both, and label it as the Apple edition's date.
            date = album.get("releaseDate", "")
            if not re.match(r"^\d{4}-\d{2}-\d{2}", date):
                exclusions["missing_collection_release_date"] += 1
                continue
            if len(selected) >= args.target:
                continue
            selected.append({
                "review_id": f"apple:{tid}", "status": "listening_and_editorial_review_required",
                "title": title, "artist": artist, "matched_artist": result["artistName"],
                "album": album["collectionName"], "apple_edition_year": date[:4],
                "apple_collection_release_date": date, "apple_track_release_date": result.get("releaseDate"),
                "apple_track_id": tid, "apple_collection_id": collection_id,
                "track_number": result.get("trackNumber"), "disc_number": result.get("discNumber"),
                "duration_ms": duration, "apple_url": result["trackViewUrl"],
                "preview_url": result["previewUrl"], "artwork_url": result.get("artworkUrl100", "").replace("100x100bb", "600x600bb"),
                "apple_genre": result.get("primaryGenreName", ""),
                "seed_track_id": seed["id"], "seed_title": seed["title"],
                "seed_genres": seed.get("genres", []), "artist_bio_already_present": True,
                "selection_basis": "same_artist_and_same_album_as_existing_curated_track",
                "metadata_verification": {"status": match_status, "source_url": url,
                    "fetched_at": receipt["fetched_at"], "country": "US",
                    "album_membership": "collection_id_and_name_match", "source_receipt_sha256": query_hash},
                "pending_checks": ["melody", "taste_and_blacklist_by_listening", "bpm_range", "instrumentation",
                    "production", "vocal_style", "mood_tags", "distinct_chinese_why_and_scene", "original_album_year"],
            })
            selected_sources[tid] = {"track": result, "collection": album}
            seen.add(key)
            seen_ids.add(tid)
            artists[ak] += 1
        print(f"albums {min(offset + len(batch), len(ids))}/{len(ids)}; review tracks {len(selected)}/{args.target}; artists {len(artists)}", flush=True)
        if len(selected) >= args.target:
            break
    queue = {"schema": 1, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
             "status": "unpublished_listening_queue", "target": args.target,
             "production_pool_count_before": len(pool), "production_pool_changed": False,
             "tracks": selected, "artists": []}
    write_json(args.output / "listening-queue.json", queue)
    write_json(args.output / "apple-source-records.json", selected_sources)
    summary = {"target": args.target, "metadata_verified_tracks": len(selected),
               "formally_imported_tracks": 0, "listening_verified_tracks": 0,
               "unique_artists": len(artists), "max_tracks_per_artist": max(artists.values(), default=0),
               "new_artists_requiring_bios": 0, "missing_existing_bios": 0,
               "duplicates_against_pool_or_queue": 0, "queries": queries, "excluded": dict(exclusions),
               "apple_edition_decades": dict(collections.Counter(t["apple_edition_year"][:3] + "0s" for t in selected)),
               "seed_genres": dict(collections.Counter(g for t in selected for g in t["seed_genres"])),
               "limitations": ["Official metadata is not an audition or a music-production measurement.",
                   "Same-album proximity is a discovery signal, not confirmation of taste fit.",
                   "Apple edition dates do not necessarily establish original release years.",
                   "This queue intentionally lacks fabricated mandatory candidate fields and cannot be auto-merged."]}
    write_json(args.output / "summary.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("queries", "excluded", "seed_genres", "limitations")}, ensure_ascii=False), flush=True)
    return 0 if len(selected) == args.target else 2


if __name__ == "__main__":
    raise SystemExit(main())
