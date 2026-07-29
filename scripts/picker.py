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


LAST_RELAX: list[str] = []   # 上次选曲放宽了哪些软约束（供 build_daily 记录）


def _akey(t: dict) -> str:
    return t.get("artist_key") or _norm(t.get("artist", ""))


def _alkey(t: dict) -> str:
    return t.get("album_key") or _norm(t.get("album", ""))


def _fill(cands, n, date_str, picked, uid, uartist, ualbum, allow_artist_repeat=False) -> int:
    """按气质多样性 round-robin 填充；硬守 同期同艺人/同专辑/canonical id 不重复。"""
    ranked = sorted(cands, key=lambda t: score(t) + _seeded_key(t, date_str) * 6, reverse=True)
    buckets: dict[str, list[dict]] = {}
    for t in ranked:
        buckets.setdefault(_primary_mood(t), []).append(t)
    moods = sorted(buckets, key=lambda m: score(buckets[m][0]), reverse=True)
    start = len(picked)
    advanced = True
    while advanced and len(picked) < n:
        advanced = False
        for m in moods:
            if len(picked) >= n:
                break
            b = buckets[m]
            while b:
                t = b.pop(0)
                ak, alk = _akey(t), _alkey(t)
                if t["id"] in uid:
                    continue
                if not allow_artist_repeat and ak in uartist:
                    continue
                if alk and alk in ualbum:
                    continue
                picked.append(t)
                uid.add(t["id"]); uartist.add(ak)
                if alk:
                    ualbum.add(alk)
                advanced = True
                break
    return len(picked) - start


def select_daily(pool: list[dict], history: dict, date_str: str, n: int = 30,
                 recency_days: int = 45, artist_gap_issues: int = 6) -> list[dict]:
    """分阶段约束选曲：硬规则(旋律/黑名单/同期同艺人同专辑/canonical 去重/近 45 期不重复)优先，
    库存不足时按固定顺序逐条放宽软约束并记录 LAST_RELAX。旋律与黑名单永不放宽。"""
    global LAST_RELAX
    LAST_RELAX = []
    by_id = {t["id"]: t for t in pool if t.get("id")}
    eligible = [t for t in pool if is_eligible(t)[0]]           # 硬过滤：旋律 + 黑名单
    sent_dates = sorted(history)
    recent_ids = _recent_sent_ids(history, set(sent_dates[-recency_days:]))
    recent_artists = set()
    for d in sent_dates[-artist_gap_issues:]:
        for tid in history.get(d, []):
            tr = by_id.get(tid)
            if tr:
                recent_artists.add(_akey(tr))
    last = _last_sent(history)
    picked: list[dict] = []
    uid: set = set()
    uartist: set = set()
    ualbum: set = set()

    def stage(cands, tag, allow_artist_repeat=False):
        if len(picked) >= n:
            return
        added = _fill(cands, n, date_str, picked, uid, uartist, ualbum, allow_artist_repeat)
        if added and tag:
            LAST_RELAX.append(f"{tag}(+{added})")

    fresh = [t for t in eligible if t["id"] not in recent_ids]
    stage([t for t in fresh if _akey(t) not in recent_artists], "")             # 1 最严
    stage(fresh, "放宽跨期艺人间隔")                                             # 2
    backfill = sorted([t for t in eligible if t["id"] in recent_ids],
                      key=lambda t: (last.get(t["id"], ""), _seeded_key(t, date_str)))
    stage(backfill, "回填最久未发(池不足)")                                      # 3
    stage(sorted(eligible, key=lambda t: (last.get(t["id"], ""), _seeded_key(t, date_str))),
          "放宽同期同艺人(极端不足)", allow_artist_repeat=True)                  # 4（仍不放宽旋律/黑名单）
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
