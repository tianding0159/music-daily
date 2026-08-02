"""把 pool.json 里的三段文案回填进已生成的 issue 快照。

为什么需要它：快照(data/issues/*.json)是不可变的——build_daily 当天生成后就复用，
所以池里改了文案，已发布的往期页不会自己更新。之前手动回填过一次，
结果 rebase 从远端带下来两期新快照又漏了（08-01 / 08-02 全 30 首停在旧文案）。
一次性脚本必然重复漏，故固化成可重跑工具 + 接进测试。

只回填文案三段（artist_oneliner / why / scene），不动选曲、不动 issue_no、不动日期——
快照的「哪天发了哪 30 首」这个事实仍然不可变，改的只是同一首歌的描述文字。
netease_text 里嵌了歌单文本，也跟着重建。

用法：
  python3 tools/refresh_snapshot_copy.py            # 体检：列出哪几期滞后
  python3 tools/refresh_snapshot_copy.py --apply    # 回填 + 重建 site/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

POOL = ROOT / "data" / "pool.json"
ISSUES = ROOT / "data" / "issues"
FIELDS = ("artist_oneliner", "why", "scene")


def scan() -> tuple[list[tuple[str, int, int]], int]:
    """返回 [(date, 滞后曲目数, 滞后字段数)]，以及总滞后字段数。"""
    pool = {t["id"]: t for t in json.loads(POOL.read_text(encoding="utf-8"))}
    out, total = [], 0
    for p in sorted(ISSUES.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        tracks, fields = 0, 0
        for t in d["tracks"]:
            src = pool.get(t["id"])
            if not src:
                continue
            n = sum(1 for f in FIELDS if src.get(f) and t.get(f) != src[f])
            if n:
                tracks += 1
                fields += n
        if fields:
            out.append((d["date"], tracks, fields))
            total += fields
    return out, total


def apply() -> int:
    import netease

    pool = {t["id"]: t for t in json.loads(POOL.read_text(encoding="utf-8"))}
    total = 0
    for p in sorted(ISSUES.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        n = 0
        for t in d["tracks"]:
            src = pool.get(t["id"])
            if not src:
                continue
            for f in FIELDS:
                if src.get(f) and t.get(f) != src[f]:
                    t[f] = src[f]
                    n += 1
        if n:
            # 歌单文本里也嵌了曲目信息，一起重建（标题保持不变——它是那期的身份）
            d["netease_text"] = netease.build_text(d["tracks"], d.get("playlist_title", ""))
            p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  {d['date']}: 回填 {n} 处")
            total += n
    return total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    lag, total = scan()
    if not lag:
        print("✅ 全部快照文案与 pool.json 一致，无需回填")
        return 0
    print(f"{len(lag)} 期滞后，共 {total} 处：")
    for date, tr, fl in lag:
        print(f"  {date}  {tr} 首 / {fl} 处")
    if not args.apply:
        print("\n（未写盘，加 --apply 回填）")
        return 0

    print()
    n = apply()
    import build_daily

    build_daily._rebuild_site()
    print(f"\n✅ 回填 {n} 处并重建 site/")
    lag2, _ = scan()
    if lag2:
        print(f"⚠ 仍有 {len(lag2)} 期滞后：{[d for d, _, _ in lag2]}")
        return 1
    print("复检：全部一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
