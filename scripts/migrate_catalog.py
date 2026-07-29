"""一次性目录迁移（P1-3 + P1-4）：
  1. fit_score 统一百分制：0<=x<=1 的 ×100，全部 clamp 到 0..100。
  2. 建立 canonical identity：artist_key / title_key / version / album_key + 稳定 id
     （有 apple_track_id 用 `apple:<id>`，否则 `sha1:<sha256(artist_key|title_key|version|album_key)>`）。
  3. 去重：canonical id 相同的合并成一条（保留字段最全/评分最高者，合并 legacy_ids）。
  4. history.json 里的旧 id 重映射到新 canonical id。
  5. 输出迁移报告（前后数量 / 重复 / 合并 / unresolved），并保证 len(ids)==len(set(ids))。

幂等：已是 canonical 的再跑不炸。写盘前自动备份到 .backup/。
用法：python3 scripts/migrate_catalog.py [--apply]   （不带 --apply 为 dry-run）
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BK = ROOT / ".backup"

VERSION_WORDS = ("remix", "remixed", "remaster", "remastered", "live", "rework", "edit",
                 "acoustic", "instrumental", "demo", "reprise", "radio edit", "extended",
                 "re recorded", "rerecorded", "cover", "karaoke", "version")

_PARENS = re.compile(r"[\(\（\[【].*?[\)\）\]】]")
_KEEP = re.compile(r"[^0-9a-z一-鿿぀-ヿ]+")


def strip_parens(s: str) -> str:
    return _PARENS.sub(" ", s or "")


def keyify(s: str) -> str:
    """规范化 key：去括号内容、小写、只留字母数字 + CJK/日文假名。"""
    return _KEEP.sub("", strip_parens(s or "").lower())


def detect_version(title: str) -> str:
    t = " " + keyify(title) + " "  # 注意 keyify 去了空格，这里用原串更稳
    raw = (title or "").lower()
    for w in VERSION_WORDS:
        if w in raw:
            return w
    return ""


def canonical_id(track: dict) -> str:
    if track.get("apple_track_id"):
        return f"apple:{track['apple_track_id']}"
    ak = keyify(track.get("artist", ""))
    tk = keyify(track.get("title", ""))
    ver = detect_version(track.get("title", ""))
    alk = keyify(track.get("album", ""))
    h = hashlib.sha256(f"{ak}|{tk}|{ver}|{alk}".encode("utf-8")).hexdigest()[:16]
    return f"sha1:{h}"


def migrate_fit(v) -> float:
    try:
        v = float(v)
    except (TypeError, ValueError):
        v = 60.0
    if 0 <= v <= 1:
        v *= 100
    return round(min(max(v, 0), 100), 1)


_COMPLETE_FIELDS = ["why", "artist_oneliner", "scene", "source_url", "album", "genres",
                    "mood_tags", "production_tags", "instrumentation", "familiarity", "vocal_style"]


def completeness(t: dict) -> int:
    return sum(1 for f in _COMPLETE_FIELDS if t.get(f) not in (None, "", []))


def enrich(t: dict) -> dict:
    t = dict(t)
    t["fit_score"] = migrate_fit(t.get("fit_score"))
    t.setdefault("apple_track_id", "")
    t.setdefault("apple_collection_id", "")
    t["artist_display"] = t.get("artist", "")
    t["title_display"] = t.get("title", "")
    t["artist_key"] = keyify(t.get("artist", ""))
    t["title_key"] = keyify(t.get("title", ""))
    t["version"] = detect_version(t.get("title", ""))
    t["album_key"] = keyify(t.get("album", ""))
    return t


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正写盘（否则 dry-run）")
    args = ap.parse_args()

    pool = json.loads((DATA / "pool.json").read_text(encoding="utf-8"))
    hist_path = DATA / "history.json"
    history = json.loads(hist_path.read_text(encoding="utf-8")) if hist_path.exists() else {}
    before = len(pool)

    # 1) fit + canonical fields
    enriched = [enrich(t) for t in pool]

    # 2) 分组去重（按新 canonical id）
    groups: dict[str, list[dict]] = {}
    for t in enriched:
        groups.setdefault(canonical_id(t), []).append(t)

    dup_old_ids = [k for k, c in
                   {i: sum(1 for x in enriched if x.get("id") == i) for i in {x.get("id") for x in enriched}}.items()
                   if c > 1]

    id_remap: dict[str, str] = {}   # 旧 id -> 新 canonical id
    merged_report = []
    unresolved = []
    new_pool = []
    for cid, rows in groups.items():
        best = max(rows, key=lambda t: (completeness(t), t.get("fit_score", 0), len(str(t.get("why", "")))))
        legacy = []
        for r in rows:
            for lid in ([r["id"]] if r.get("id") else []) + list(r.get("legacy_ids", [])):
                if lid and lid != cid and lid not in legacy:
                    legacy.append(lid)
            id_remap[r.get("id", "")] = cid
        rec = dict(best)
        rec["id"] = cid
        rec["legacy_ids"] = legacy
        new_pool.append(rec)
        if len(rows) > 1:
            merged_report.append({
                "canonical": cid,
                "kept": f"{best['artist']} - {best['title']}",
                "merged_from": [f"{r['artist']} - {r['title']} (id={r.get('id')})" for r in rows],
            })
            # 冲突提示：合并组内 album/year 不一致
            if len({r.get("album", "") for r in rows}) > 1 or len({r.get("year", "") for r in rows}) > 1:
                unresolved.append({"canonical": cid,
                                   "albums": sorted({r.get("album", "") for r in rows}),
                                   "years": sorted({str(r.get("year", "")) for r in rows})})

    # 3) history 重映射（每天内去重）
    new_history = {}
    for date, ids in history.items():
        seen, out = set(), []
        for old in ids:
            nid = id_remap.get(old, old)
            if nid not in seen:
                seen.add(nid); out.append(nid)
        new_history[date] = out

    ids = [t["id"] for t in new_pool]
    fits = [t["fit_score"] for t in new_pool]
    report = {
        "before_count": before,
        "after_count": len(new_pool),
        "duplicate_old_ids": dup_old_ids,
        "merged_groups": len(merged_report),
        "unresolved_conflicts": len(unresolved),
        "fit_all_0_100": all(0 <= f <= 100 for f in fits),
        "ids_unique": len(ids) == len(set(ids)),
        "history_dates": len(new_history),
    }
    print("=== 迁移报告 ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if merged_report:
        print("--- 合并明细 ---")
        for m in merged_report:
            print(f"  keep [{m['kept']}]  <=  {m['merged_from']}")
    if unresolved:
        print("--- 需人工确认(album/year 冲突, 已保留最全者) ---")
        for u in unresolved:
            print(f"  {u}")

    assert report["ids_unique"], "迁移后仍有重复 id！"
    assert report["fit_all_0_100"], "迁移后仍有非 0..100 的 fit_score！"

    if not args.apply:
        print("\n(dry-run，未写盘；加 --apply 生效)")
        return

    BK.mkdir(exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S")
    (BK / f"pool.premigrate.{stamp}.json").write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")
    (BK / f"history.premigrate.{stamp}.json").write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA / "pool.json").write_text(json.dumps(new_pool, ensure_ascii=False, indent=2), encoding="utf-8")
    hist_path.write_text(json.dumps(new_history, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA / "migration_report.json").write_text(
        json.dumps({"report": report, "merged": merged_report, "unresolved": unresolved},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 已写盘。备份 .backup/*.premigrate.{stamp}.json，报告 data/migration_report.json")


if __name__ == "__main__":
    main()
