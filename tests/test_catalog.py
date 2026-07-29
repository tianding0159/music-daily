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

import merge_candidates as mcand  # noqa: E402
import migrate_catalog as mc  # noqa: E402
import picker  # noqa: E402

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
    cands = [{"title": "X", "artist": "Y", "genres": ["festival edm"], "has_melody": True}]
    _, stats = mcand.merge(cands, [dict(t) for t in POOL], validate=False)
    assert stats["badgenre"] == 1 and stats["added"] == 0


def test_picker_deterministic_and_dedup():
    a = [t["id"] for t in picker.select_daily([dict(x) for x in POOL], HISTORY, "2026-08-10", 20)]
    b = [t["id"] for t in picker.select_daily([dict(x) for x in POOL], HISTORY, "2026-08-10", 20)]
    assert a == b, "同一天选曲应确定性一致"
    assert len(a) == len(set(a)), "同一期不应重复"


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
