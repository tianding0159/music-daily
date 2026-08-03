"""删掉 bio 里两个汉字之间的多余空格。

来源：GPT 把英文地名换成中文时（placefix 那批），没把原英文两侧的空格一起删。
「出生于 Tulsa，」→「出生于 塔尔萨，」—— 英文没了，空格留下了。

判据严格限定「汉字 空格 汉字」：
- 中英之间的空格（`1010benja 本名 Benjamin`）是全库一致的风格，**不动**
  （2368 处涉及 398 位，那是风格决策不是错误）。
- 只删汉字之间的，这种在中文排版里没有任何合法用途。

默认只体检，--apply 才写盘；写完自动复检。
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTISTS = ROOT / "data" / "artists.json"

# 汉字—空格—汉字。用 finditer 逐个替换而不是一次 sub，因为相邻案例会重叠
# （「洛杉矶 后开始」里 `矶 后` 和前面的 `到 洛` 共享边界）
PAT = re.compile(r"(?<=[一-鿿]) +(?=[一-鿿])")


def clean(s: str) -> str:
    # 循环到不再变化 —— 一次 sub 无法处理连续重叠的情况
    prev = None
    while prev != s:
        prev, s = s, PAT.sub("", s)
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="写盘（默认只体检）")
    args = ap.parse_args()

    rows = json.loads(ARTISTS.read_text(encoding="utf-8"))
    hits = []
    for a in rows:
        new = clean(a["bio"])
        if new != a["bio"]:
            hits.append((a["artist"], a["bio"], new))

    print(f"扫描 {len(rows)} 位 → {len(hits)} 位的 bio 有汉字间空格")
    for artist, old, new in hits:
        for m in re.finditer(r"[一-鿿] +[一-鿿]", old):
            print(f"  {artist:24} 「{m.group(0)}」→「{m.group(0).replace(' ', '')}」")

    if not hits:
        print("✅ 没有需要修的")
        return 0
    if not args.apply:
        print(f"\n（体检模式，未写盘；加 --apply 修 {len(hits)} 位）")
        return 0

    by = {a["artist"]: a for a in rows}
    for artist, _, new in hits:
        by[artist]["bio"] = new
    ARTISTS.write_text(json.dumps(sorted(by.values(), key=lambda x: x["artist"]),
                                  ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n✅ 已修 {len(hits)} 位")

    # 复检：写完立刻再扫一遍，不靠「我改过了」这句话
    again = [a["artist"] for a in json.loads(ARTISTS.read_text(encoding="utf-8"))
             if clean(a["bio"]) != a["bio"]]
    print(f"复检：残留 {len(again)} 处 {'✓' if not again else again}")
    return 1 if again else 0


if __name__ == "__main__":
    raise SystemExit(main())
