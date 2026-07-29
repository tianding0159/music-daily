"""离线确定性测试（无需网络/pytest）。运行：python3 tests/test_catalog.py

覆盖：pool 数据完整性、canonical id 稳定性/去重、版本错配检测、fit 百分制、
黑名单过滤、picker 同一天稳定 + 去重。任一失败 → 退出码 1。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import itunes  # noqa: E402
import merge_candidates as mcand  # noqa: E402
import migrate_catalog as mc  # noqa: E402
import picker  # noqa: E402
import validate_candidates as vc  # noqa: E402


def _good_cand(**over):
    t = {"title": "So Many Details", "artist": "Toro y Moi", "year": "2013",
         "album": "Anything in Return", "genres": ["indietronica", "dream pop"],
         "mood_tags": ["城市夜晚", "颗粒感"], "production_tags": ["soft compression"],
         "instrumentation": ["synth"], "vocal_style": "气声", "bpm_band": "90–100",
         "has_melody": True, "familiarity": "likely-unheard",
         "scene": "深夜末班地铁靠窗，玻璃把你映成陌生人的那十分钟",
         "artist_oneliner": "南加州 chillwave 代表人物之一", "why": "合成器铺出雾面，人声浮在上面。",
         "source": "Bandcamp", "source_url": "https://example.com/x"}
    t.update(over)
    return t


def test_itunes_classify_statuses():
    assert itunes.classify("Bibio", "Lovers' Carvings",
                           [{"artistName": "Bibio", "trackName": "Lovers' Carvings"}])[0] == "exact_match"
    assert itunes.classify("aus", "Halo",
                           [{"artistName": "Aus", "trackName": "Halo (Ulrich Schnauss Remix of Aus)"}])[0] == "version_mismatch"
    assert itunes.classify("aus", "Halo",
                           [{"artistName": "Beyoncé", "trackName": "Halo"}])[0] == "artist_mismatch"
    assert itunes.classify("X", "Y", [{"artistName": "Z", "trackName": "W"}])[0] == "not_found"
    assert itunes.classify("Beach House", "Space Song",
                           [{"artistName": "Beach House feat. Q", "trackName": "Space Song"}])[0] == "acceptable_match"


def test_validate_track_good_and_bad():
    assert vc.validate_track(_good_cand()) == []
    assert vc.validate_track(_good_cand(year="2010s"))
    assert vc.validate_track(_good_cand(has_melody=False))
    assert vc.validate_track(_good_cand(familiarity="unknown"))
    assert vc.validate_track(_good_cand(source_url="http://x"))
    assert vc.validate_track(_good_cand(scene="通勤时听"))
    assert vc.validate_track(_good_cand(bpm_band="fast"))


def test_validate_batch_caps():
    classic = [_good_cand(artist=f"A{i}", title=f"T{i}", familiarity="classic-known") for i in range(4)]
    valid, invalid = vc.validate_batch(classic)
    assert len(valid) == 2 and len(invalid) == 2  # classic-known 全批最多 2
    same = [_good_cand(artist="Solo", title=f"S{i}") for i in range(5)]
    valid2, invalid2 = vc.validate_batch(same)
    assert len(valid2) == 3  # 单艺人最多 3/批

POOL = json.loads((ROOT / "data" / "pool.json").read_text(encoding="utf-8"))
HISTORY = json.loads((ROOT / "data" / "history.json").read_text(encoding="utf-8"))


def test_pool_parses_and_nonempty():
    assert isinstance(POOL, list) and len(POOL) > 0


def test_ids_unique():
    ids = [t["id"] for t in POOL]
    assert len(ids) == len(set(ids)), "pool 存在重复 id"


def test_fit_all_0_100():
    for t in POOL:
        f = t.get("fit_score")
        assert isinstance(f, (int, float)) and 0 <= f <= 100, f"fit 越界: {t['id']}={f}"


def test_years_four_digit():
    for t in POOL:
        y = t.get("year")
        if y:
            assert len(str(y)) == 4 and str(y).isdigit(), f"year 非法: {t['id']}={y}"


def test_canonical_fields_present():
    for t in POOL:
        for c in ("artist_key", "title_key", "version", "album_key", "legacy_ids"):
            assert c in t, f"{t['id']} 缺 canonical 字段 {c}"


def test_history_ids_exist():
    pool_ids = {t["id"] for t in POOL}
    for date, ids in HISTORY.items():
        for i in ids:
            assert i in pool_ids, f"history[{date}] 指向不存在 id {i}"


def test_canonical_id_stable_and_variant_merges():
    a = mc.canonical_id({"artist": "Takako Minekawa", "title": "Milk Rock", "album": "Cloudy Cloud Calculator"})
    b = mc.canonical_id({"artist": "Takako Minekawa (嶺川貴子)", "title": "Milk Rock", "album": "Cloudy Cloud Calculator"})
    assert a == b, "括号变体艺人名应归并为同一 canonical id"
    c = mc.canonical_id({"artist": "Takako Minekawa", "title": "Different Song", "album": "X"})
    assert a != c
    d = mc.canonical_id({"artist": "X", "title": "Y", "album": "Z", "apple_track_id": "123"})
    assert d == "apple:123", "有 apple id 时应优先用 apple:<id>"


def test_version_mismatch_detected():
    assert mcand._version_mismatch("Halo", "Halo (Ulrich Schnauss Remix of Aus)")
    assert not mcand._version_mismatch("Halo", "Halo")
    assert mcand._version_mismatch("Song", "Song (Live)")
    assert not mcand._version_mismatch("Live Forever", "Live Forever")  # 主标题含 live 但两边都有→不算错配


def test_fit_score_scale_and_direction():
    hi = mcand._fit_score(5, "likely-unheard")
    lo = mcand._fit_score(3, "classic-known")
    assert 0 <= lo <= hi <= 95
    assert hi > lo


def test_blacklist_filtered_in_merge():
    cands = [_good_cand(artist="ZZBlack", title="EDM Thing", genres=["festival edm"])]
    _, rep = mcand.merge(cands, [dict(t) for t in POOL], validate=False)
    assert rep["counts"]["blacklist"] == 1 and rep["counts"]["added"] == 0


def test_picker_deterministic_and_dedup():
    a = [t["id"] for t in picker.select_daily([dict(x) for x in POOL], HISTORY, "2026-08-10", 20)]
    b = [t["id"] for t in picker.select_daily([dict(x) for x in POOL], HISTORY, "2026-08-10", 20)]
    assert a == b, "同一天选曲应确定性一致"
    assert len(a) == len(set(a)), "同一期不应重复"


def test_picker_no_dup_artist_or_album_in_issue():
    picks = picker.select_daily([dict(x) for x in POOL], HISTORY, "2026-08-11", 30)
    aks = [t.get("artist_key") for t in picks]
    alks = [t.get("album_key") for t in picks if t.get("album_key")]
    assert len(aks) == len(set(aks)), "同一期出现重复艺人"
    assert len(alks) == len(set(alks)), "同一期出现重复专辑"


def test_blacklist_never_relaxed_and_melody_required():
    assert not picker.is_eligible({"has_melody": False, "genres": ["dream pop"]})[0]
    assert not picker.is_eligible({"has_melody": True, "genres": ["metal"]})[0]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed, failed = 0, []
    for fn in fns:
        try:
            fn()
            passed += 1
            print(f"  PASS {fn.__name__}")
        except Exception as e:
            failed.append((fn.__name__, e))
            print(f"  FAIL {fn.__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
