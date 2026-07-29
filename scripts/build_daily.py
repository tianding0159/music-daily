"""每日投递主编排（纯 stdlib，可靠·确定·便宜）。

流程：选曲 → iTunes 补封面/试听/Apple链接 → 渲染网页 → 写 site/ → 更新 history 去重
→（可选）微信推送。GitHub Actions 每天定时跑这个脚本，或本地手动跑预览。

用法：
  python3 scripts/build_daily.py                 # 用北京日期，出网页，不推送
  python3 scripts/build_daily.py --date 2026-07-28
  python3 scripts/build_daily.py --push --url https://<user>.github.io/music-daily/
  python3 scripts/build_daily.py --no-itunes     # 离线：跳过 iTunes（用池里 cover_url 兜底）
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import itunes
import netease
import picker as selector
import push_wechat
import render
import render_grid

RENDERERS = {"light": render, "grid": render_grid}

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = ROOT / "site"


def _beijing_today() -> str:
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=8)).strftime("%Y-%m-%d")


def _load_json(p: Path, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def enrich(tracks: list[dict], use_itunes: bool) -> tuple[list[dict], list[str]]:
    """给每首补 _cover/_preview/_apple。返回 (tracks, iTunes未命中列表)。"""
    misses: list[str] = []
    cache = itunes.load_cache() if use_itunes else {}
    for t in tracks:
        info = itunes.lookup(t["artist"], t["title"], cache) if use_itunes else {"found": False}
        if info.get("found"):
            t["_cover"] = info["artwork"]
            t["_preview"] = info["preview"]
            t["_apple"] = info["apple_url"]
        else:
            t["_cover"] = t.get("cover_url", "")  # 池里若有备用封面则用
            t["_preview"] = ""
            t["_apple"] = ""
            misses.append(f"{t['title']} — {t['artist']}")
    if use_itunes:
        itunes.save_cache(cache)
    return tracks, misses


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=_beijing_today())
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--url", default="")
    ap.add_argument("--no-itunes", action="store_true")
    ap.add_argument("--theme", choices=list(RENDERERS), default="grid")
    ap.add_argument("--out", default="", help="输出文件名（相对 site/），默认 index.html")
    args = ap.parse_args()

    pool = _load_json(DATA / "pool.json", [])
    history = _load_json(DATA / "history.json", {})
    if not pool:
        raise SystemExit("pool.json 为空，先建候选池")

    # 同一天重跑幂等：先摘掉当天自己的记录，避免把本期算进"近期已发"而自我排除
    history.pop(args.date, None)
    picks = selector.select_daily(pool, history, args.date, n=args.n)
    picks, misses = enrich(picks, use_itunes=not args.no_itunes)

    issue_no = len(history) + 1 if args.date not in history else list(history).index(args.date) + 1
    nc_text = netease.build_text(picks)
    html = RENDERERS[args.theme].build_html(args.date, picks, issue_no, nc_text)

    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "archive").mkdir(parents=True, exist_ok=True)
    out_name = args.out or "index.html"
    (SITE / out_name).write_text(html, encoding="utf-8")
    suffix = "" if args.theme == "grid" else f"-{args.theme}"
    (SITE / "archive" / f"{args.date}{suffix}.html").write_text(html, encoding="utf-8")

    history[args.date] = [t["id"] for t in picks]
    (DATA / "history.json").write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"✅ 第 {issue_no} 期 · {args.date} · {len(picks)} 首")
    for i, t in enumerate(picks, 1):
        mark = "" if t.get("_cover") else "  (无封面)"
        print(f"  {i:2d}. {t['title']} — {t['artist']} [{(t.get('genres') or ['?'])[0]}]{mark}")
    if misses:
        print(f"⚠️  iTunes 未命中 {len(misses)} 首（用兜底封面，不影响文字信息）：")
        for m in misses:
            print(f"     - {m}")
    print(f"📄 已写 {SITE/out_name}（theme={args.theme}）")

    if args.push:
        url = args.url or f"file://{SITE/'index.html'}"
        # A 方案低池预警：算还剩多少"未发"存量，不足一期就提醒补池
        sent_dates = sorted(history)
        recent = selector._recent_sent_ids(history, set(sent_dates[-45:]))
        unsent = sum(1 for t in pool if selector.is_eligible(t)[0] and t["id"] not in recent)
        warn = (f"⚠️ 候选池仅剩 {unsent} 首未发（不足一期），该补池了——回 agent 一句「补池」即可。"
                if unsent < args.n else None)
        title, desp = push_wechat.build_desp(args.date, url, picks, warn=warn)
        push_wechat.push(title, desp)


if __name__ == "__main__":
    main()
