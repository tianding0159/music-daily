"""每日投递主编排（纯 stdlib，可靠·确定·便宜）。

流程：选曲 → iTunes 补封面/试听 → 写不可变 issue 快照(data/issues/YYYY-MM-DD.json)
→ 从所有快照全量重建 site/archive/*.html + 最新一期 site/index.html → 更新 history 去重索引
→ 写 data/latest.json（供部署成功后的通知步骤用）。
微信推送在 CI 里由部署成功后的 notify_after_deploy.py 负责（本脚本 --push 仅供本地）。

用法：
  python3 scripts/build_daily.py                 # 北京日期，出网页
  python3 scripts/build_daily.py --date 2026-07-28
  python3 scripts/build_daily.py --force-rebuild  # 重新生成当期快照（否则当天幂等复用）
  python3 scripts/build_daily.py --no-itunes      # 离线：跳过 iTunes
  python3 scripts/build_daily.py --push --url <PAGES_URL>   # 本地顺带发微信
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

import itunes
import netease
import picker as selector
import push_wechat
import render_grid
import render_landing
import render_random

RENDERERS = {"grid": render_grid}

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = ROOT / "site"
ISSUES = DATA / "issues"


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
        # 判据是 status ∈ ACCEPT，不是 found —— lookup 在拿不到 exact/acceptable 时
        # 会退回 best_nonexact（version_mismatch / artist_mismatch）并且 found 仍为真。
        # 用 found 采纳等于把别人的歌挂上封面和试听：实测缓存 1297 条里有 44 条
        # 命中这种情况，含 bigthief|paul 这类 artist_mismatch。
        # media_check.py 早就用对了判据，这里是同一个 bug 的漏网处（2026-08-04 审计）。
        if info.get("found") and info.get("status") in itunes.ACCEPT:
            t["_cover"], t["_preview"], t["_apple"] = info["artwork"], info["preview"], info["apple_url"]
        else:
            t["_cover"], t["_preview"], t["_apple"] = t.get("cover_url", ""), "", ""
            misses.append(f"{t['title']} — {t['artist']}")
    if use_itunes:
        itunes.save_cache(cache)
    return tracks, misses


def _write_snapshot(date: str, issue_no: int, theme: str, picks: list[dict],
                    title: str, nc_text: str) -> dict:
    snap = {
        "issue_no": issue_no, "date": date,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "theme": theme, "playlist_title": title, "netease_text": nc_text, "tracks": picks,
    }
    ISSUES.mkdir(parents=True, exist_ok=True)
    (ISSUES / f"{date}.json").write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    return snap


def _recent_titles(before: str = "", extra: dict[str, str] | None = None, k: int = 6) -> list[str]:
    """近 k 期已用过的歌单名（去掉尾部日期括号），用于避开重名。
    before 非空时只看该日期之前的期；extra 是还没落盘的 {date: title}（backfill 累积用）。"""
    got: list[tuple[str, str]] = []
    for pth in ISSUES.glob("*.json"):
        if before and pth.stem >= before:
            continue
        try:
            got.append((pth.stem, json.loads(pth.read_text(encoding="utf-8")).get("playlist_title", "")))
        except Exception:
            pass
    for d, t in (extra or {}).items():
        if not before or d < before:
            got.append((d, t))
    out = []
    for _d, t in sorted(got)[-k:]:
        base = re.sub(r"（[^）]*）\s*$", "", t)
        if base:
            out.append(base)
    return out


def _backfill_snapshots(history: dict, pool: list[dict], skip_date: str = "",
                        use_itunes: bool = True) -> None:
    """给还没有快照的历史日期补一份，避免历史 archive 丢失。
    也补 iTunes 封面/试听（多数走缓存），否则补出来的 archive 页会没有封面和试听。
    跳过 skip_date（当前正在正常构建的日期，由主流程新鲜生成）。"""
    by_id = {t["id"]: t for t in pool}
    ISSUES.mkdir(parents=True, exist_ok=True)
    made: dict[str, str] = {}                     # 本轮已补的 {date: title}，链式累积避免互相撞名
    for i, date in enumerate(sorted(history), 1):
        if date == skip_date or (ISSUES / f"{date}.json").exists():
            continue
        picks = [dict(by_id[i2]) for i2 in history[date] if i2 in by_id]
        if not picks:
            continue
        picks, _ = enrich(picks, use_itunes=use_itunes)   # 补封面/试听，别产出空封面快照
        title = netease.playlist_title(picks, date,
                                       recent_titles=_recent_titles(before=date, extra=made))
        made[date] = title
        _write_snapshot(date, i, "grid", picks, title, netease.build_text(picks, title))


def _n_eligible() -> int:
    """池里合格曲目数（落地页自检要显示，与随机页同一口径）。"""
    pool = _load_json(DATA / "pool.json", [])
    return sum(1 for t in pool if selector.is_eligible(t)[0])


def _artist_ctx(pool: list[dict]) -> dict[str, dict]:
    """每位艺人的浮层上下文：bio（来自 data/artists.json）+ 年代跨度 + 本站收录曲目。

    bio 缺失不影响其它字段——artists.json 是逐步补齐的，缺的那位浮层就只少一段。
    """
    import collections
    bios = {a["artist"]: a.get("bio", "")
            for a in _load_json(DATA / "artists.json", [])}
    by: dict[str, list[dict]] = collections.defaultdict(list)
    for t in pool:
        by[t.get("artist", "")].append(t)
    out: dict[str, dict] = {}
    for a, ts in by.items():
        yrs = sorted(str(t.get("year", "")) for t in ts if t.get("year"))
        out[a] = {
            "bio": bios.get(a, ""),
            "years": (yrs[0] if yrs[0] == yrs[-1] else f"{yrs[0]}–{yrs[-1]}") if yrs else "",
            "inpool": [t.get("title", "") for t in ts][:8],
        }
    return out


def _rebuild_site() -> None:
    """清空 archive，从所有 issue 快照全量重建 archive/*.html 与最新一期 index.html。"""
    arch = SITE / "archive"
    if arch.exists():
        for f in arch.glob("*.html"):
            f.unlink()
    arch.mkdir(parents=True, exist_ok=True)
    snaps = sorted((json.loads(p.read_text(encoding="utf-8")) for p in ISSUES.glob("*.json")),
                   key=lambda s: s["date"])
    # 浮层的艺人上下文按全池算（不只当期），这样「本站收录」能列出该艺人的全部曲目
    render_grid.ARTIST_CTX = _artist_ctx(_load_json(DATA / "pool.json", []))
    for s in snaps:
        r = RENDERERS.get(s.get("theme", "grid"), render_grid)
        html = r.build_html(s["date"], s["tracks"], s["issue_no"], s["netease_text"], archive_href="index.html", random_href="../random.html")
        (arch / f"{s['date']}.html").write_text(html, encoding="utf-8")
    if snaps:
        idx = render_grid.build_archive_index([
            {"date": s2["date"], "issue_no": s2["issue_no"],
             "playlist_title": s2.get("playlist_title", ""), "n": len(s2["tracks"])}
            for s2 in reversed(snaps)])
        (arch / "index.html").write_text(idx, encoding="utf-8")
        latest = snaps[-1]
        r = RENDERERS.get(latest.get("theme", "grid"), render_grid)
        # 日报本体在 daily.html；index.html 让给开机自检落地页（站点入口）
        (SITE / "daily.html").write_text(
            r.build_html(latest["date"], latest["tracks"], latest["issue_no"], latest["netease_text"]),
            encoding="utf-8")
        (SITE / "index.html").write_text(
            render_landing.build_html(
                n_issues=len(snaps), n_tracks=_n_eligible(),
                latest_date=latest["date"]),
            encoding="utf-8")


MEDIA = DATA / "pool_media.json"          # id -> {c,p,a} 封面/试听/Apple 链接，增量累积
_MEDIA_BUDGET = 60                        # 单次最多现查多少首（CI 时长可控；其余下次继续）


def write_random_assets(items: list[dict]) -> None:
    """写随机页的三件产物：pool.min.json / artists.min.json / random.html。

    **抽成函数是因为已经漂移过两次**：import-bios.yml 里内联复制了这一段，
    2026-08-03 漏了 artists.min.json（导入简介后随机页浮层看不到新简介，
    要等次日 daily 才自愈），2026-08-04 审计又发现它仍然漏着。
    补一行只会抄成第三份，下次这里增写第四个文件时会以同样方式再漏。
    workflow 与 build_daily 都调这个函数 —— 一处增写，两边同时生效。

    入参 items 必须已经补好媒体字段（_cover/_preview/_apple）；
    iTunes 查询留在调用侧，别把网络调用带进 workflow 链路。
    """
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "pool.min.json").write_text(
        render_random.build_pool_json(items), encoding="utf-8")
    # 艺人上下文侧表：随机页浮层的 bio / 年代 / 本站收录都从这里取。
    # 日报是把 ARTIST_CTX 内联进 HTML，随机页数据是异步加载的，所以单独出一份。
    bios = {a["artist"]: a.get("bio", "")
            for a in _load_json(DATA / "artists.json", [])}
    (SITE / "artists.min.json").write_text(
        render_random.build_artist_json(items, bios), encoding="utf-8")
    (SITE / "random.html").write_text(
        render_random.build_html(len(items)), encoding="utf-8")


def _build_random(pool: list[dict], use_itunes: bool) -> int:
    """生成随机页 + 精简池 JSON。媒体字段增量补：只查还没有的，单次上限 _MEDIA_BUDGET 首。"""
    media = _load_json(MEDIA, {})
    items = [dict(t) for t in pool if selector.is_eligible(t)[0]]
    todo = [t for t in items if t["id"] not in media]
    if use_itunes and todo:
        cache = itunes.load_cache()
        for t in todo[:_MEDIA_BUDGET]:
            info = itunes.lookup(t["artist"], t["title"], cache)
            media[t["id"]] = ({"c": info["artwork"], "p": info["preview"], "a": info["apple_url"]}
                              if info.get("found") and info.get("status") in itunes.ACCEPT
                              else {"c": "", "p": "", "a": ""})   # 判据同 enrich()：ACCEPT 才采纳
        itunes.save_cache(cache)
        MEDIA.write_text(json.dumps(media, ensure_ascii=False), encoding="utf-8")
        print(f"🎧 媒体增量补 {min(len(todo), _MEDIA_BUDGET)} 首（剩 {max(0, len(todo) - _MEDIA_BUDGET)} 首下次继续）")
    for t in items:
        m = media.get(t["id"], {})
        t["_cover"], t["_preview"], t["_apple"] = m.get("c", ""), m.get("p", ""), m.get("a", "")
    write_random_assets(items)
    return len(items)


def _low_pool_warn(pool: list[dict], history: dict, n: int) -> str | None:
    recent = selector._recent_sent_ids(history, set(sorted(history)[-45:]))
    unsent = sum(1 for t in pool if selector.is_eligible(t)[0] and t["id"] not in recent)
    return (f"⚠️ 候选池仅剩 {unsent} 首未发（不足一期），该补池了。" if unsent < n else None)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=_beijing_today())
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--theme", choices=list(RENDERERS), default="grid")
    ap.add_argument("--force-rebuild", action="store_true", help="重生成当期快照（否则当天幂等复用）")
    ap.add_argument("--no-itunes", action="store_true")
    ap.add_argument("--push", action="store_true", help="本地顺带发微信（CI 用 notify_after_deploy）")
    ap.add_argument("--url", default="")
    args = ap.parse_args()

    pool = _load_json(DATA / "pool.json", [])
    history = _load_json(DATA / "history.json", {})
    if not pool:
        raise SystemExit("pool.json 为空，先建候选池")

    _backfill_snapshots(history, pool, skip_date=args.date, use_itunes=not args.no_itunes)
    snap_path = ISSUES / f"{args.date}.json"

    if snap_path.exists() and not args.force_rebuild:
        snap = json.loads(snap_path.read_text(encoding="utf-8"))
        print(f"↻ 复用当期快照 第 {snap['issue_no']} 期 · {args.date} · {len(snap['tracks'])} 首（幂等）")
        fresh = False
    else:
        fresh = True
        history.pop(args.date, None)
        picks = selector.select_daily(pool, history, args.date, n=args.n)
        picks, misses = enrich(picks, use_itunes=not args.no_itunes)
        existing = sorted(p.stem for p in ISSUES.glob("*.json"))
        # 守卫：往【已有期号区间内部】补一期会编出错号。
        # 新日期一律拿「现有期数+1」，不管时间上排第几；而 _backfill_snapshots
        # 用 enumerate(sorted(history),1) 按时间序编 —— 两套规则不一致。
        # 实测 --date 2026-07-25 得「第 9 期」，archive 里它排在最末却标 009，
        # 而它前面的 2026-07-28 是 001。
        #
        # 触发条件是 args.date 不在 existing 里【且】小于 max(existing)：
        # 当前 8 期日期连续，所以此刻只有 < 首期才会撞；但一旦漏跑形成空档
        # （如 08-04、08-06 已有而补 08-05），中间那天就是触发点 —— 这才是
        # 运维里真会遇到的形态。
        #
        # 不自动重编号：既有快照永不重编（_backfill_snapshots 对已有的 continue、
        # refresh_snapshot_copy 也明确不动 issue_no），只改新期算法必然撞号 ——
        # 实测「sorted(existing+[date]).index()+1」会把「顺序错」换成「编号重复」。
        # 所以这里只拦住，让人显式处理。
        if existing and args.date not in existing and args.date < max(existing):
            raise SystemExit(
                f"❌ 拒绝生成：{args.date} 落在已有期号区间内部"
                f"（现有 {existing[0]} … {existing[-1]}，共 {len(existing)} 期）。\n"
                f"   直接生成会编成第 {len(existing) + 1} 期，与日期顺序矛盾；\n"
                f"   而既有快照不会重编号，自动按时间序编又会与已有期号撞车。\n"
                f"   需要人工处理：先决定这一期占哪个号，再把该号及其后所有快照的\n"
                f"   issue_no 一起重排（data/issues/*.json 的 issue_no 字段），\n"
                f"   然后跑 _rebuild_site() 重建。没有现成命令能替你做这件事。")
        issue_no = existing.index(args.date) + 1 if args.date in existing else len(existing) + 1
        title = netease.playlist_title(picks, args.date,
                                       recent_titles=_recent_titles(before=args.date))
        snap = _write_snapshot(args.date, issue_no, args.theme, picks, title,
                               netease.build_text(picks, title))
        history[args.date] = [t["id"] for t in picks]
        (DATA / "history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ 第 {issue_no} 期 · {args.date} · {len(picks)} 首")
        for i, t in enumerate(picks, 1):
            print(f"  {i:2d}. {t['title']} — {t['artist']} [{(t.get('genres') or ['?'])[0]}]"
                  f"{'' if t.get('_cover') else '  (无封面)'}")
        if misses:
            print(f"⚠️  iTunes 未命中 {len(misses)} 首（用兜底封面）")
        if selector.LAST_RELAX:
            print(f"⚠️  选曲放宽软约束: {selector.LAST_RELAX}")

    _rebuild_site()
    n_rand = _build_random(pool, use_itunes=not args.no_itunes)
    print(f"🎲 随机页已生成（{n_rand} 首可摇）")
    warn = _low_pool_warn(pool, history, args.n)
    (DATA / "latest.json").write_text(json.dumps({
        "date": snap["date"], "issue_no": snap["issue_no"], "playlist_title": snap["playlist_title"],
        "tracks_brief": [{"title": t["title"], "artist": t["artist"]} for t in snap["tracks"][:6]],
        "n": len(snap["tracks"]), "low_pool_warn": warn, "relax": selector.LAST_RELAX,
        "fresh_build": fresh,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"📄 已重建 site/（archive {len(list(ISSUES.glob('*.json')))} 期 + index）")

    if args.push:
        url = args.url or f"file://{SITE / 'index.html'}"
        title, desp = push_wechat.build_desp(snap["date"], url, snap["tracks"], warn=warn)
        push_wechat.push(title, desp)


if __name__ == "__main__":
    main()
