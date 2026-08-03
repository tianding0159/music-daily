"""媒体健康体检：封面 / 试听 / 版本正确性。

为什么要它（都是真实发生过的）：
1. **页面只显示一个字母** = 该曲 `pool_media.json` 里 `c` 为空，渲染层退化成
   艺人首字母占位。原因多是 iTunes 查询没命中，而不是曲子不存在。
2. **匹到了错版本 / 错艺人还照样展示**。库里曾有 5 首这样的：
   `Ride On Time — Tatsuro Yamashita` 匹到别人的同名曲、两首落到 Remaster/Live 版。
   根子是采纳时只看「有没有 artwork」而不看 `status` 是否在 `itunes.ACCEPT` 里。
   **判据只有一个：status ∈ ACCEPT（exact_match / acceptable_match）。**
3. **坏缓存会永久固化失败**。`not_found` 一旦写进 itunes_cache，后续永远直接返回，
   即使查询逻辑已经修好。所以体检要能区分「真查不到」和「缓存说查不到」，
   并支持 `--refresh` 清掉可疑缓存重查。

用法：
  python3 scripts/media_check.py              # 只体检，列出问题
  python3 scripts/media_check.py --refresh    # 清可疑缓存 + 重查 + 回写 media
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import itunes  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
POOL = DATA / "pool.json"
MEDIA = DATA / "pool_media.json"


def audit() -> dict:
    """返回体检结果。不写盘。"""
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    media = json.loads(MEDIA.read_text(encoding="utf-8")) if MEDIA.exists() else {}
    cache = itunes.load_cache()
    by_id = {t["id"]: t for t in pool}

    rep: dict = {
        "pool": len(pool), "media_entries": len(media),
        "missing_entry": [], "no_cover": [], "no_preview": [],
        "bad_status": [], "orphan_media": [], "cached_not_found": [],
    }
    for t in pool:
        tid = t["id"]
        m = media.get(tid)
        label = f"{t.get('title','')} — {t.get('artist','')}"
        if m is None:
            rep["missing_entry"].append(label)
            continue
        if not m.get("c"):
            rep["no_cover"].append(label)
        if not m.get("p"):
            rep["no_preview"].append(label)
        # 已展示的媒体，其来源 status 必须在 ACCEPT 内
        k = itunes._key(t.get("artist", "")) + "|" + itunes._key(t.get("title", ""))
        ent = cache.get(k)
        if m.get("c") and ent and ent.get("status") not in itunes.ACCEPT:
            rep["bad_status"].append(f"{label}  [{ent.get('status')}]")
        if ent and ent.get("status") == "not_found":
            rep["cached_not_found"].append(label)
    rep["orphan_media"] = [i for i in media if i not in by_id]
    return rep


def refresh(only_missing: bool = True) -> dict:
    """清掉可疑缓存并重查。只采纳 status ∈ ACCEPT 的结果。"""
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    media = json.loads(MEDIA.read_text(encoding="utf-8")) if MEDIA.exists() else {}
    cache = itunes.load_cache()

    targets = []
    for t in pool:
        m = media.get(t["id"]) or {}
        k = itunes._key(t.get("artist", "")) + "|" + itunes._key(t.get("title", ""))
        ent = cache.get(k)
        bad_src = bool(m.get("c")) and ent and ent.get("status") not in itunes.ACCEPT
        if (only_missing and not m.get("c")) or bad_src:
            targets.append((t, k))

    out = {"tried": len(targets), "fixed": 0, "still": [], "rejected": []}
    for t, k in targets:
        cache.pop(k, None)                      # 清掉可能是坏的缓存
        r = itunes.lookup(t.get("artist", ""), t.get("title", ""), cache)
        st = r.get("status")
        label = f"{t.get('title','')} — {t.get('artist','')}"
        if st in itunes.ACCEPT and r.get("artwork"):
            media[t["id"]] = {"c": r["artwork"], "p": r.get("preview", ""),
                              "a": r.get("apple_url", "")}
            out["fixed"] += 1
        else:
            # 判据只有 status，绝不因为「有 artwork」就采纳错版本/错艺人
            media[t["id"]] = {"c": "", "p": "", "a": ""}
            (out["rejected"] if st not in ("not_found",) else out["still"]).append(
                f"{label}  [{st}]")
    itunes.save_cache(cache)
    MEDIA.write_text(json.dumps(media, ensure_ascii=False), encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="清可疑缓存并重查")
    ap.add_argument("--all", action="store_true", help="配合 --refresh：连已有封面的也重查")
    args = ap.parse_args()

    if args.refresh:
        r = refresh(only_missing=not args.all)
        print(f"重查 {r['tried']} 首 → 修好 {r['fixed']}")
        for x in r["rejected"]:
            print(f"  拒绝（版本/艺人不符，宁缺不错）: {x}")
        for x in r["still"][:20]:
            print(f"  仍查不到: {x}")
        print()

    rep = audit()
    print(f"=== media_check === 池 {rep['pool']} 首 · media {rep['media_entries']} 条")
    hard = 0
    for key, title, is_p0 in [
        ("missing_entry", "media 表无记录（从未查过）", True),
        ("bad_status", "展示了非 ACCEPT 的匹配（错版本/错艺人）", True),
        ("orphan_media", "media 有记录但池里没这首", False),
        ("no_cover", "无封面（页面显示艺人首字母）", False),
        ("no_preview", "无试听", False),
    ]:
        v = rep[key]
        if not v:
            continue
        tag = "P0" if is_p0 else "warn"
        if is_p0:
            hard += len(v)
        print(f"  [{tag}] {title}：{len(v)}")
        for x in v[:8]:
            print(f"        {x}")
        if len(v) > 8:
            print(f"        …另 {len(v) - 8} 条")

    cov_c = 100 * (rep["pool"] - len(rep["no_cover"]) - len(rep["missing_entry"])) / max(rep["pool"], 1)
    cov_p = 100 * (rep["pool"] - len(rep["no_preview"]) - len(rep["missing_entry"])) / max(rep["pool"], 1)
    print(f"  覆盖率：封面 {cov_c:.1f}% · 试听 {cov_p:.1f}%")
    print("✅ 媒体无 P0" if not hard else f"❌ {hard} 项媒体 P0")
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
