"""把并行 agent 重写出的 artist_oneliner / scene 合并回 data/pool.json。

一次性工具（重写任务用完即可删），但把三道校验固化在这里，因为这三处都真的翻过车：
  1. 只认带 artist_oneliner 键的产物 —— 上一轮扫到同名目录里"改 why"那批旧文件，
     它们只有 id+why，静默合并后实际改动 0/856，指标纹丝不动。
  2. 按 id 对账（缺失 / 越界 / 重复覆盖），不按文件名 —— agent 会自行二次分片改文件名。
  3. 验"真的改了"：逐条比新旧值，统计逐字相同的条数，抓"抄回输入"。

用法：
  python3 tools/merge_copy_rewrite.py --dry-run      # 只体检，不写
  python3 tools/merge_copy_rewrite.py --apply
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT / "data" / "pool.json"
SRC_GLOBS = ("/tmp/rw/out[0-9]*.json", "/tmp/rw2/out*.json")
FIELDS = ("artist_oneliner", "scene")

BLACKLIST = ("慵懒", "空灵", "治愈", "封神", "天籁", "氛围感",
             "宝藏", "单曲循环", "温暖的旋律", "娓娓道来")


def load_rewrites() -> tuple[dict[str, dict], list[str]]:
    """收集所有分片产物。只认含 artist_oneliner 的文件，其余原因记进 skipped。"""
    rows: dict[str, dict] = {}
    skipped: list[str] = []
    for pat in SRC_GLOBS:
        for f in sorted(glob.glob(pat)):
            try:
                d = json.loads(Path(f).read_text(encoding="utf-8"))
            except Exception as e:
                skipped.append(f"{f}（解析失败 {e}）")
                continue
            if not d:
                skipped.append(f"{f}（空）")
                continue
            keys = set().union(*(set(r.keys()) for r in d))
            if "artist_oneliner" not in keys:
                skipped.append(f"{f}（不是本轮产物，键={sorted(keys)}）")
                continue
            for r in d:
                rows[r["id"]] = r
    return rows, skipped


def audit(rows: dict[str, dict], pool: list[dict]) -> dict:
    by = {t["id"]: t for t in pool}
    covered = set(rows) & set(by)
    rep = {
        "wanted": len(pool),
        "got": len(rows),
        "covered": len(covered),
        "missing": [t["id"] for t in pool if t["id"] not in rows],
        "alien": sorted(set(rows) - set(by)),
    }
    # 真的改了吗
    for fld in FIELDS:
        rep[f"same_as_old_{fld}"] = sum(
            1 for i in covered
            if (rows[i].get(fld) or "").strip() == (by[i].get(fld) or "").strip())
        rep[f"empty_{fld}"] = sum(1 for i in covered if not (rows[i].get(fld) or "").strip())
    # 文风指标
    ol = [rows[i]["artist_oneliner"] for i in covered]
    sc = [rows[i]["scene"] for i in covered]
    n = max(len(ol), 1)
    rep["dash_pct"] = round(100 * sum(1 for v in ol if "——" in v or "—" in v) / n, 1)
    rep["renling_cnt"] = sum(1 for v in ol if "让人" in v or "令人" in v)
    top = collections.Counter(v[-4:] for v in sc).most_common(1)
    rep["scene_top_tail"] = (top[0][0], round(100 * top[0][1] / n, 1)) if top else ("", 0)
    hits = collections.Counter()
    for v in ol + sc:
        for w in BLACKLIST:
            if w in v:
                hits[w] += 1
    rep["blacklist"] = dict(hits)
    rep["dup_scene"] = sum(c - 1 for c in collections.Counter(sc).values() if c > 1)
    rep["dup_oneliner"] = sum(c - 1 for c in collections.Counter(ol).values() if c > 1)
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--allow-partial", action="store_true",
                    help="允许没写满 856 也合并（默认拒绝：半池会让新旧文风混在同一期里）")
    args = ap.parse_args()

    pool = json.loads(POOL.read_text(encoding="utf-8"))
    rows, skipped = load_rewrites()
    rep = audit(rows, pool)

    print(f"产物 {rep['got']} 条 · 覆盖 {rep['covered']}/{rep['wanted']} · 仍缺 {len(rep['missing'])}")
    for s in skipped:
        print(f"  跳过 {s}")
    if rep["alien"]:
        print(f"  ⚠ 池里查不到的 id {len(rep['alien'])}: {rep['alien'][:5]}")
    for fld in FIELDS:
        print(f"  {fld}: 与旧值逐字相同 {rep[f'same_as_old_{fld}']} · 空值 {rep[f'empty_{fld}']}")
    print(f"  破折号 {rep['dash_pct']}%（配额 ≤25）· 让人/令人 {rep['renling_cnt']}（应 0）")
    print(f"  scene 最高收尾「{rep['scene_top_tail'][0]}」{rep['scene_top_tail'][1]}%（配额 ≤25）")
    print(f"  黑名单 {rep['blacklist'] or '无'} · scene 重复 {rep['dup_scene']} · oneliner 重复 {rep['dup_oneliner']}")

    blockers = []
    if rep["missing"] and not args.allow_partial:
        blockers.append(f"未写满（缺 {len(rep['missing'])} 首）")
    for fld in FIELDS:
        if rep[f"same_as_old_{fld}"]:
            blockers.append(f"{fld} 有 {rep[f'same_as_old_{fld}']} 条与旧值逐字相同")
        if rep[f"empty_{fld}"]:
            blockers.append(f"{fld} 有 {rep[f'empty_{fld}']} 条为空")
    if rep["alien"]:
        blockers.append(f"{len(rep['alien'])} 个 id 不在池里")
    if rep["blacklist"]:
        blockers.append(f"黑名单命中 {sum(rep['blacklist'].values())} 处")

    if not args.apply:
        print("\n（dry-run，未写盘）" + ("  阻塞项: " + "；".join(blockers) if blockers else "  无阻塞项"))
        return 0
    if blockers:
        print("\n❌ 拒绝写盘：" + "；".join(blockers))
        return 1

    changed = 0
    for t in pool:
        r = rows.get(t["id"])
        if not r:
            continue
        for fld in FIELDS:
            if r.get(fld) and r[fld].strip() != (t.get(fld) or "").strip():
                t[fld] = r[fld].strip()
                changed += 1
    POOL.write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 已写入 {POOL}：{changed} 处字段更新（{changed // 2} 首 × 2 段）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
