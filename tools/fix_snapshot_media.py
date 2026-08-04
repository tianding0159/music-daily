"""洗掉期号快照里冻着的非 ACCEPT 媒体（错版本 / 错艺人的封面与试听）。

为什么需要一个专门工具：
`_rebuild_site()` 是从 `data/issues/*.json` 渲染的，媒体在快照生成当天就被
【冻】进去了。后来修好 `enrich()` 的判据、洗干净 `pool_media.json`，都动不了
已有快照 —— 归档页会一直挂着那张错封面。

全仓确认（2026-08-04 审计）：写 `data/issues` 的只有 `build_daily._write_snapshot`；
`tools/refresh_snapshot_copy.py` 只管 `artist_oneliner/why/scene/mood_tags/genres`
这五个文案字段，**没有任何工具会重写快照媒体**。所以补这一个。

**为什么不删快照让 backfill 重建**：`_backfill_snapshots` 会重新生成
`playlist_title`，2026-07-29 那期的《木头、旧磁带和一点灰》会被换掉。
只改媒体三字段，其余一个字不动。

判据与 `itunes.ACCEPT` 完全一致（唯一 SSOT）。非 ACCEPT 的一律清空成 ""，
让页面回退到「艺人首字母」占位 —— 宁缺不错。

默认只体检，`--apply` 才写盘，写完自动复检。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import itunes  # noqa: E402

ISSUES = ROOT / "data" / "issues"
MEDIA_FIELDS = ("_cover", "_preview", "_apple")


def scan() -> list[tuple[Path, dict, str]]:
    """返回 [(快照文件, 曲目 dict, status)]，只列真正需要清的。"""
    cache = itunes.load_cache()
    out = []
    for f in sorted(ISSUES.glob("*.json")):
        try:
            snap = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"⚠️ {f.name} 解析失败：{e}")
            continue
        for t in snap.get("tracks", []):
            if not any(t.get(k) for k in MEDIA_FIELDS):
                continue
            k = itunes._key(t.get("artist", "")) + "|" + itunes._key(t.get("title", ""))
            ent = cache.get(k)
            if ent and ent.get("status") not in itunes.ACCEPT:
                out.append((f, t, ent.get("status")))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="写盘（默认只体检）")
    args = ap.parse_args()

    hits = scan()
    print(f"扫 {len(list(ISSUES.glob('*.json')))} 期快照 → {len(hits)} 处非 ACCEPT 媒体")
    for f, t, st in hits:
        print(f"  {f.stem} · {st:17} {t.get('artist','')} — {t.get('title','')}")
    if not hits:
        print("✅ 没有需要洗的")
        return 0
    if not args.apply:
        print(f"\n（体检模式，未写盘；加 --apply 清掉这 {len(hits)} 处的封面/试听）")
        return 0

    # 按文件分组写回：只动 MEDIA_FIELDS，其余字段与键序保持原样
    byfile: dict[Path, list[dict]] = {}
    for f, t, _ in hits:
        byfile.setdefault(f, []).append(t)
    for f, targets in byfile.items():
        snap = json.loads(f.read_text(encoding="utf-8"))
        ids = {id(x) for x in targets}          # 同一对象无法跨 load 匹配，改用键匹配
        keys = {(t.get("id") or (t.get("artist"), t.get("title"))) for t in targets}
        n = 0
        for t in snap.get("tracks", []):
            k = t.get("id") or (t.get("artist"), t.get("title"))
            if k in keys:
                for fld in MEDIA_FIELDS:
                    if t.get(fld):
                        t[fld] = ""
                n += 1
        f.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  ✓ {f.name}：清了 {n} 首的媒体字段")
        del ids

    again = scan()
    print(f"\n复检：残留 {len(again)} 处 " + ("✓" if not again else str(again[:2])))
    print("接着跑：python3 -c \"import sys;sys.path.insert(0,'scripts');"
          "import build_daily;build_daily._rebuild_site()\" 重新渲染归档页")
    return 1 if again else 0


if __name__ == "__main__":
    raise SystemExit(main())
