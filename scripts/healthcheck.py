"""仓库数据健康自检。P0（数据完整性）问题 → 退出码非零；库存等 → 仅告警。

用法：python3 scripts/healthcheck.py
覆盖：池可解析 / id 唯一 / fit 0-100 / year 合理 / 必填字段 / 黑名单漏网 /
history 与 pool 一致 / canonical 字段 / 库存与可支撑天数（告警）/
文案口径（copy_check：文案黑名单词、圣经范例句被入库、跨歌重复、模板集中度）。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import copy_check  # noqa: E402
import media_check  # noqa: E402
import picker  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
REQUIRED = ["id", "title", "artist", "year", "album", "genres", "mood_tags", "has_melody",
            "familiarity", "scene", "artist_oneliner", "why", "fit_score"]
CANON = ["artist_key", "title_key", "version", "album_key", "legacy_ids"]
N_PER_ISSUE = 30


def main() -> int:
    p0: list[str] = []
    warn: list[str] = []

    try:
        pool = json.loads((DATA / "pool.json").read_text(encoding="utf-8"))
    except Exception as e:
        print(f"P0: pool.json 无法解析：{e}")
        return 2
    history = json.loads((DATA / "history.json").read_text(encoding="utf-8")) if (DATA / "history.json").exists() else {}

    ids = [t.get("id") for t in pool]
    if len(ids) != len(set(ids)):
        dups = [i for i in set(ids) if ids.count(i) > 1]
        p0.append(f"重复 id {len(dups)} 个：{dups[:5]}")

    bad_fit = [t["id"] for t in pool if not isinstance(t.get("fit_score"), (int, float))
               or not (0 <= t["fit_score"] <= 100)]
    if bad_fit:
        p0.append(f"fit_score 越界(非 0-100) {len(bad_fit)} 首：{bad_fit[:5]}")

    bad_year = [t.get("id") for t in pool if t.get("year") and not re.fullmatch(r"\d{4}", str(t.get("year")))]
    if bad_year:
        warn.append(f"year 非四位年份 {len(bad_year)} 首")

    miss = {}
    for t in pool:
        for f in REQUIRED:
            if t.get(f) in (None, "", []):
                miss[f] = miss.get(f, 0) + 1
    if miss:
        warn.append(f"必填字段缺失：{miss}")
    canon_miss = sum(1 for t in pool if any(c not in t for c in CANON))
    if canon_miss:
        p0.append(f"canonical 字段缺失 {canon_miss} 首（需跑 migrate_catalog.py）")

    leak = [t.get("id") for t in pool if not picker.is_eligible(t)[0]]
    if leak:
        warn.append(f"当前池含 {len(leak)} 首不合格(黑名单/无旋律)——picker 会过滤，但建议清理")

    pool_ids = set(ids)
    dangling = {d: [i for i in lst if i not in pool_ids] for d, lst in history.items()}
    dangling = {d: v for d, v in dangling.items() if v}
    if dangling:
        p0.append(f"history 指向不存在的 id：{ {d: v[:3] for d, v in list(dangling.items())[:3]} }")

    # 文案（口径来自 docs/style_bible.md，见 copy_check.py）
    c_p0, c_warn, c_m = copy_check.check_copy(pool)
    p0 += c_p0
    warn += c_warn

    # 库存（告警）
    eligible = [t for t in pool if picker.is_eligible(t)[0]]
    sent_dates = sorted(history)
    recent = picker._recent_sent_ids(history, set(sent_dates[-45:]))
    fresh = sum(1 for t in eligible if t.get("id") not in recent)
    days = fresh // N_PER_ISSUE
    stock = {"total": len(pool), "eligible": len(eligible), "recently_sent": len(recent),
             "fresh": fresh, "est_days_supply": days}
    if len(eligible) < 900:
        warn.append(f"库存偏低(合格 {len(eligible)}，目标≥1350)——靠每周补库补足")

    print("=== healthcheck ===")
    print("stock:", json.dumps(stock, ensure_ascii=False))
    print("copy: ", json.dumps({k: c_m[k] for k in (
        "blacklist_hits", "example_verbatim", "oneliner_dash_pct",
        "scene_top_tail_pct", "scene_timeword_pct") if k in c_m}, ensure_ascii=False))
    # 媒体（封面/试听/版本正确性，见 media_check.py）
    try:
        mrep = media_check.audit()
        n = max(mrep["pool"], 1)
        print("media:", json.dumps({
            "no_cover": len(mrep["no_cover"]), "no_preview": len(mrep["no_preview"]),
            "bad_status": len(mrep["bad_status"]), "missing_entry": len(mrep["missing_entry"]),
            "cover_pct": round(100 * (n - len(mrep["no_cover"]) - len(mrep["missing_entry"])) / n, 1),
        }, ensure_ascii=False))
        # 展示了非 ACCEPT 的匹配 = 页面上挂着错版本/错艺人，属 P0
        if mrep["bad_status"]:
            p0.append(f"媒体来源非 ACCEPT（错版本/错艺人）{len(mrep['bad_status'])} 首："
                      f"{mrep['bad_status'][:3]}")
        if mrep["missing_entry"]:
            p0.append(f"media 表缺记录 {len(mrep['missing_entry'])} 首（从未查过封面）")
        if mrep["no_cover"]:
            warn.append(f"{len(mrep['no_cover'])} 首无封面（页面显示艺人首字母）"
                        f"——跑 python3 scripts/media_check.py --refresh 重查")
    except Exception as e:
        warn.append(f"媒体体检跳过：{type(e).__name__}: {e}")
    for w in warn:
        print("  [warn]", w)
    for e in p0:
        print("  [P0]  ", e)
    if p0:
        print(f"\n❌ 发现 {len(p0)} 项 P0 数据完整性问题")
        return 1
    print("\n✅ 无 P0 问题" + (f"（{len(warn)} 项告警）" if warn else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
