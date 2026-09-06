"""Independently check queue provenance/deduplication and optionally probe previews.

Media probes read at most 64 bytes per response. A valid M4A container header
proves that a preview was retrievable, not that it was listened to or reviewed.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

from build_catalog_review import ROOT, semantic_key, write_json

sys.path.insert(0, str(ROOT / "scripts"))
import itunes


def probe(track: dict) -> dict:
    url = track["preview_url"]
    result = {"review_id": track["review_id"], "url": url, "checked_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"Range": "bytes=0-63", "User-Agent": "music-daily/catalog-audit"})
            with urllib.request.urlopen(request, timeout=15) as response:
                head = response.read(64)
                result.update({"http_status": response.status, "content_type": response.headers.get("Content-Type", ""),
                    "content_range": response.headers.get("Content-Range", ""), "header_hex": head.hex(),
                    "final_url": response.url})
            result["retrievable_audio_container"] = result["http_status"] in (200, 206) and result["content_type"].startswith("audio/") and head[4:8] == b"ftyp"
            result["listening_verified"] = False
            if result["retrievable_audio_container"]:
                return result
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
        if attempt < 2:
            time.sleep(1 + attempt)
    result["retrievable_audio_container"] = False
    result["listening_verified"] = False
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / "reports/catalog-expansion-2026-09-07")
    parser.add_argument("--probe-media", action="store_true")
    args = parser.parse_args()
    base = args.directory
    queue = json.loads((base / "listening-queue.json").read_text(encoding="ascii"))
    tracks = queue["tracks"]
    source = json.loads((base / "apple-source-records.json").read_text(encoding="ascii"))
    pool_bytes = (ROOT / "data/pool.json").read_bytes()
    pool = json.loads(pool_bytes)
    bios = {b["artist"] for b in json.loads((ROOT / "data/artists.json").read_text(encoding="utf-8"))}
    failures = []
    keys = [semantic_key(t["artist"], t["title"]) for t in tracks]
    pool_keys = {semantic_key(t["artist"], t["title"]) for t in pool}
    ids = [t["apple_track_id"] for t in tracks]
    pool_ids = {str(t.get("apple_track_id") or "") for t in pool}
    artists = collections.Counter(itunes._key(t["artist"]) for t in tracks)
    if len(tracks) != 1000:
        failures.append("track_count_not_1000")
    if len(set(keys)) != len(keys) or pool_keys.intersection(keys):
        failures.append("semantic_duplicate")
    if len(set(ids)) != len(ids) or pool_ids.intersection(ids):
        failures.append("apple_id_duplicate")
    if max(artists.values(), default=0) > 3:
        failures.append("artist_cap")
    seed_by_id = {t["id"]: t for t in pool}
    for track in tracks:
        tid = track["apple_track_id"]
        record = source[tid]
        song, album = record["track"], record["collection"]
        checks = {
            "source_title": track["title"] == song["trackName"],
            "source_track_id": tid == str(song["trackId"]),
            # Apple capitalizes Suchmos' album as THE KIDS on the collection
            # object and The Kids on individual song objects. Preserve the
            # collection spelling, accept case equivalence across its children.
            "source_album_name": track["album"] == album["collectionName"] and track["album"].casefold() == song["collectionName"].casefold(),
            "source_album_id": track["apple_collection_id"] == str(song["collectionId"]) == str(album["collectionId"]),
            "source_edition_date": track["apple_collection_release_date"] == album["releaseDate"],
            "source_preview": track["preview_url"] == song["previewUrl"],
            "source_apple_url": track["apple_url"] == song["trackViewUrl"],
            "exact_artist_and_title": itunes.classify(track["artist"], track["title"], [song])[0] == "exact_match",
            "existing_bio": track["artist"] in bios,
            "existing_seed": track["seed_track_id"] in seed_by_id,
            "explicit_review_state": track["status"] == "listening_and_editorial_review_required" and bool(track["pending_checks"]),
            "no_fabricated_listening_metadata": not {"has_melody", "bpm_band", "why", "scene", "instrumentation", "production_tags", "mood_tags"}.intersection(track),
            "https_preview": urllib.parse.urlsplit(track["preview_url"]).scheme == "https" and urllib.parse.urlsplit(track["preview_url"]).hostname == "audio-ssl.itunes.apple.com",
            "https_apple_link": urllib.parse.urlsplit(track["apple_url"]).scheme == "https" and urllib.parse.urlsplit(track["apple_url"]).hostname == "music.apple.com",
            "no_control_characters_in_titles": all(unicodedata.category(c) not in {"Cc", "Cf"} for c in track["title"] + track["artist"] + track["album"]),
        }
        failures.extend(f"{tid}:{name}" for name, ok in checks.items() if not ok)
    probes = []
    if args.probe_media:
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            tasks = [executor.submit(probe, t) for t in tracks]
            for count, task in enumerate(concurrent.futures.as_completed(tasks), 1):
                probes.append(task.result())
                if count % 100 == 0:
                    print(f"media {count}/{len(tracks)}; retrievable {sum(r['retrievable_audio_container'] for r in probes)}", flush=True)
        probes.sort(key=lambda r: r["review_id"])
        write_json(base / "media-probes.json", probes)
        failures.extend(r["review_id"] + ":preview_unavailable" for r in probes if not r["retrievable_audio_container"])
    elif (base / "media-probes.json").exists():
        probes = json.loads((base / "media-probes.json").read_text(encoding="ascii"))
        if {p["review_id"] for p in probes} != {t["review_id"] for t in tracks}:
            failures.append("stale_media_probe_inventory")
        failures.extend(r["review_id"] + ":preview_unavailable" for r in probes if not r["retrievable_audio_container"])
    report = {"checked_at": dt.datetime.now(dt.timezone.utc).isoformat(), "status": "PASS" if not failures else "FAIL",
              "metadata_verified": len(tracks), "exact_match": len(tracks) - sum("exact_artist" in f for f in failures),
              "unique_artists": len(artists), "max_tracks_per_artist": max(artists.values(), default=0),
              "source_records": len(source), "source_title_and_album_checked": True,
              "semantic_duplicate_count": len(keys) - len(set(keys)) + len(pool_keys.intersection(keys)),
              "apple_id_duplicate_count": len(ids) - len(set(ids)) + len(pool_ids.intersection(ids)),
              "preview_containers_retrievable": sum(p["retrievable_audio_container"] for p in probes),
              "listening_verified": 0, "formally_imported": 0, "failures": failures,
              "production_pool_count": len(pool), "production_pool_sha256": hashlib.sha256(pool_bytes).hexdigest()}
    write_json(base / "audit.json", report)
    paths = sorted(p for p in base.iterdir() if p.is_file() and p.name != "SHA256SUMS.txt")
    (base / "SHA256SUMS.txt").write_text("\n".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name for p in paths) + "\n", encoding="ascii")
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
