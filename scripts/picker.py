"""每日选曲：黑名单硬过滤 + 旋律必须 + 打分排序 + 气质多样性挑 15 首。

选曲依据用户的 music taste profile（气质+制作+旋律，非流派配额）。所有美学判断已在
发现阶段写进 pool.json，这里是确定性的纯逻辑：过滤 → 打分 → 按 mood 多样性挑选。
同一天日期做种子，结果稳定；跨天用 history 去重轮播。
"""
from __future__ import annotations

import hashlib

# 黑名单流派/制作标签（命中即排除）——profile 明确不喜欢的
BLACKLIST = {
    "hyperpop", "tiktok pop", "festival edm", "edm", "dubstep", "big room",
    "hardstyle", "metal", "folk metal", "progressive house", "future bass",
    "phonk", "lo-fi hip hop", "lofi hip hop", "study beats", "drone", "noise",
    "math rock", "jazz fusion", "trap",
}
# 制作雷区标签
BLACKLIST_PROD = {
    "heavy sidechain", "edm drop", "808 heavy", "harsh highs", "sharp lead",
}


def _norm(s: str) -> str:
    return str(s).strip().lower()


def _tagset(track: dict, *fields: str) -> set[str]:
    out: set[str] = set()
    for f in fields:
        for v in track.get(f, []) or []:
            out.add(_norm(v))
    return out


def is_eligible(track: dict) -> tuple[bool, str]:
    """(是否可选, 原因)。用于测试与调试。"""
    if not track.get("has_melody", False):
        return False, "no_melody"
    genres = _tagset(track, "genres")
    if genres & BLACKLIST:
        return False, f"blacklist_genre:{sorted(genres & BLACKLIST)}"
    prod = _tagset(track, "production_tags")
    if prod & BLACKLIST_PROD:
        return False, f"blacklist_prod:{sorted(prod & BLACKLIST_PROD)}"
    return True, "ok"


def _recent_sent_ids(history: dict, cutoff_dates: set[str]) -> set[str]:
    """history: {date: [id,...]}。返回在 cutoff 日期集合内已发的 id。"""
    ids: set[str] = set()
    for d, id_list in history.items():
        if d in cutoff_dates:
            ids.update(id_list)
    return ids


def _last_sent(history: dict) -> dict[str, str]:
    """每个 id 最近一次被发的日期（用于池耗尽时挑最久没发的）。"""
    last: dict[str, str] = {}
    for d in sorted(history.keys()):
        for tid in history[d]:
            last[tid] = d
    return last


def _seeded_key(track: dict, date_str: str) -> float:
    """按日期 + id 的确定性伪随机，用于同分候选的每日轮换。"""
    h = hashlib.sha256(f"{date_str}:{track.get('id','')}".encode()).hexdigest()
    return int(h[:12], 16) / 0xFFFFFFFFFFFF


def score(track: dict) -> float:
    """fit_score(0-100) + genre_stars 加权。genre_stars: 5/4/3。"""
    return float(track.get("fit_score", 60)) + 4.0 * float(track.get("genre_stars", 3))


def _primary_mood(track: dict) -> str:
    moods = track.get("mood_tags") or ["其他"]
    return _norm(moods[0])


def select_daily(pool: list[dict], history: dict, date_str: str, n: int = 15,
                 recency_days: int = 45) -> list[dict]:
    """选出当天 n 首：气质多样性优先，跨天不重样。"""
    # 1) 硬过滤
    eligible = [t for t in pool if is_eligible(t)[0]]

    # 2) 排除近 recency_days 已发（history 的键是 YYYY-MM-DD，按字符串近似取最近 N 个发过的日期）
    sent_dates = sorted(history.keys())
    cutoff = set(sent_dates[-recency_days:]) if sent_dates else set()
    recent = _recent_sent_ids(history, cutoff)
    fresh = [t for t in eligible if t.get("id") not in recent]

    # 3) 池耗尽兜底：不足 n 首则把最久没发的补回来
    if len(fresh) < n:
        last = _last_sent(history)
        backfill = sorted(
            [t for t in eligible if t.get("id") in recent],
            key=lambda t: (last.get(t.get("id"), ""), _seeded_key(t, date_str)),
        )
        fresh = fresh + backfill

    # 4) 打分 + 每日轮换扰动
    fresh.sort(key=lambda t: (score(t) + _seeded_key(t, date_str) * 3), reverse=True)

    # 5) 气质多样性挑选：按 primary mood 分桶，round-robin 轮取，保证一期里气质错落
    buckets: dict[str, list[dict]] = {}
    for t in fresh:
        buckets.setdefault(_primary_mood(t), []).append(t)
    # 桶按内部最高分排序，轮流各取一首
    ordered_moods = sorted(
        buckets, key=lambda m: score(buckets[m][0]), reverse=True
    )
    picked: list[dict] = []
    while len(picked) < n and any(buckets[m] for m in ordered_moods):
        for m in ordered_moods:
            if buckets[m]:
                picked.append(buckets[m].pop(0))
                if len(picked) >= n:
                    break
    return picked[:n]


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    data = Path(__file__).resolve().parent.parent / "data"
    pool = json.loads((data / "pool.json").read_text(encoding="utf-8"))
    hist_path = data / "history.json"
    history = json.loads(hist_path.read_text(encoding="utf-8")) if hist_path.exists() else {}
    date_str = sys.argv[1] if len(sys.argv) > 1 else "2026-07-28"
    for i, t in enumerate(select_daily(pool, history, date_str), 1):
        print(f"{i:2d}. [{t.get('genres',['?'])[0]:<16}] {t['title']} — {t['artist']}"
              f"  ({'/'.join(t.get('mood_tags',[])[:2])})")
