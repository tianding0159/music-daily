"""每日选曲：全历史作品去重、黑名单过滤与气质多样性。

pool.json 保留已听审的美学判断；资料核实但未听审的曲目单独标为新发现。
同一天日期与输入做种子，结果稳定；已推荐作品不回填，库存不足按实际数量出刊。
"""
from __future__ import annotations

import hashlib
import re
import unicodedata

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


def _seeded_key(track: dict, date_str: str) -> float:
    """按日期 + id 的确定性伪随机，用于同分候选的每日轮换。"""
    h = hashlib.sha256(f"{date_str}:{track.get('id','')}".encode()).hexdigest()
    return int(h[:12], 16) / 0xFFFFFFFFFFFF


def score(track: dict) -> float:
    """fit_score(0-100) + genre_stars 加权。genre_stars: 5/4/3。"""
    return float(track.get("fit_score", 60)) + 4.0 * float(track.get("genre_stars", 3))


def _canon_mood(m: str) -> str:
    """气质名归一到受控词表（SSOT: scripts/mood_vocab.py）。

    不归一的后果：同义写法在多样性算法眼里是不同气质，一期里挑三首同气质的歌
    还以为凑够了反差。池里曾有 357 个 mood 写法，收敛后是 32 个受控英文词。
    """
    import mood_vocab
    return _norm(mood_vocab.canon(m) or m)


def _primary_mood(track: dict) -> str:
    moods = track.get("mood_tags") or ["其他"]
    return _canon_mood(moods[0])


# 动态反差：识别"上扬/groove/明快"曲，避免整期全是软调（温柔/木质/松弛）
BRIGHT_GENRES = ("boogie", "funk", "disco", "nu-disco", "soul", "neo soul", "neo-soul",
                 "samba", "jazz-funk", "jazz funk", "city pop", "afrobeat", "house")


def _bpm_mid(t: dict) -> float:
    ns = re.findall(r"\d+", str(t.get("bpm_band", "")))
    return (int(ns[0]) + int(ns[-1])) / 2 if ns else 90.0


def _is_bright(t: dict) -> bool:
    """节奏偏快(≥108)或 groove 型流派 → 视为对比色。"""
    if _bpm_mid(t) >= 108:
        return True
    gs = " ".join(t.get("genres") or []).lower()
    return any(bg in gs for bg in BRIGHT_GENRES)


LAST_RELAX: list[str] = []   # 上次选曲放宽了哪些软约束（供 build_daily 记录）


def _akey(t: dict) -> str:
    return t.get("artist_key") or _norm(t.get("artist", ""))


def _alkey(t: dict) -> str:
    return t.get("album_key") or _norm(t.get("album", ""))


def work_key(track: dict) -> tuple[str, str]:
    """作品身份不依赖上架 ID；同艺人的重制、现场版本不会再次推荐。"""
    title = re.sub(r"[\(（\[【].*?[\)）\]】]", " ", str(track.get("title", "")))
    version = r"(?:remaster(?:ed)?|remix(?:ed)?|live|rework|edit|acoustic|instrumental|demo|reprise|rerecorded|re[- ]recorded|version|mix)"
    title = re.sub(r"\s*[-–—]\s*(?:(?:\d{4}|stereo|mono|original|digitally|album|single|radio|us|uk|lp)\s+)*" + version + r"\b.*$", "", title, flags=re.I)
    title = re.sub(r"\s+(?:(?:\d{4}|digitally)\s+)?remaster(?:ed)?(?:\s+\d{4})?\s*$", "", title, flags=re.I)
    def key(value):
        raw = unicodedata.normalize("NFKD", str(value)).casefold()
        return "".join(c for c in raw if c.isalnum() and not unicodedata.combining(c))
    return key(track.get("artist", "")), key(title)


def identities(track: dict) -> set[str]:
    return {str(x) for x in [track.get("id"), *(track.get("legacy_ids") or [])] if x}


def unsent_tracks(candidates: list[dict], history: dict, history_tracks=()) -> list[dict]:
    """全历史 ID、旧 ID 与作品名共同去重，不因日期窗口或曲库迁移而重置。"""
    sent = _recent_sent_ids(history, set(history))
    sent_works = {work_key(t) for t in [*candidates, *history_tracks] if identities(t) & sent}
    return [t for t in candidates if not identities(t) & sent and work_key(t) not in sent_works]


def daily_candidates(pool: list[dict], discoveries=()) -> list[dict]:
    """听审精选与资料核实的新发现分开，绝不补造 has_melody 或听感字段。"""
    curated = [t for t in pool if is_eligible(t)[0]]
    curated_works = {work_key(t) for t in pool}
    pending = [t for t in discoveries
               if t.get("selection_status") == "discovery_not_curated"
               and not (_tagset(t, "genres") & BLACKLIST)
               and not (_tagset(t, "production_tags") & BLACKLIST_PROD)
               and work_key(t) not in curated_works]
    return curated + pending


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
                wk = ("work", *work_key(t))
                if t["id"] in uid or wk in uid:
                    continue
                if not allow_artist_repeat and ak in uartist:
                    continue
                if alk and alk in ualbum:
                    continue
                picked.append(t)
                uid.add(t["id"]); uid.add(wk); uartist.add(ak)
                if alk:
                    ualbum.add(alk)
                advanced = True
                break
    return len(picked) - start


def select_daily(pool: list[dict], history: dict, date_str: str, n: int = 30,
                 recency_days: int = 45, artist_gap_issues: int = 6,
                 bright_floor: int = 5, *, discoveries=(), history_tracks=()) -> list[dict]:
    """已推荐作品永不回填；库存不足少选。recency_days 仅保留调用兼容。"""
    global LAST_RELAX
    LAST_RELAX = []
    if n < 1:
        raise ValueError("每日曲目数必须大于 0")
    eligible = daily_candidates(pool, discoveries)
    by_id = {t["id"]: t for t in [*pool, *discoveries, *history_tracks] if t.get("id")}
    sent_dates = sorted(history)
    recent_artists = set()
    for d in sent_dates[-artist_gap_issues:]:
        for tid in history.get(d, []):
            tr = by_id.get(tid)
            if tr:
                recent_artists.add(_akey(tr))
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

    fresh = unsent_tracks(eligible, history, history_tracks)
    fresh_strict = [t for t in fresh if _akey(t) not in recent_artists]
    # 动态反差：先在最严池里保底挑 bright_floor 首上扬/groove 曲，避免整期一路软到底
    brights = [t for t in fresh_strict if _is_bright(t)]
    if brights and bright_floor > 0:
        added = _fill(brights, min(bright_floor, n), date_str, picked, uid, uartist, ualbum)
        if added:
            LAST_RELAX.append(f"bright保底(+{added})")
    stage(fresh_strict, "")                                                      # 1 最严
    stage(fresh, "放宽跨期艺人间隔")                                             # 2
    stage(fresh, "放宽同期同艺人(仅未推荐作品)", allow_artist_repeat=True)
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
