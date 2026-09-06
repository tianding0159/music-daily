"""在线音乐接口（iTunes Search）：精确版本匹配 + 瞬时错误区分 + 全局限流 + 结构化缓存。

不再只有 found=True/False。lookup() 返回状态枚举之一：
  exact_match / acceptable_match / version_mismatch / artist_mismatch
  （没有 album_mismatch —— 本模块不做专辑匹配，见 lookup docstring）
  / not_found / transient_error
- 精确匹配：艺人规范化后一致（exact=完全相等 / acceptable=有效子串），主标题一致，
  且声明的版本类型双向一致（Remix/Live/Remaster/Edit/... → version_mismatch）。
- 搜索顺序：artist+title 美区 → 日区；再尝试"只搜曲名"但仅能升级为 exact（严格艺人匹配），不降级。
- 瞬时错误（超时/DNS/429/5xx/JSON 异常）：status=transient_error, retryable=True，**不进长期缓存**，
  指数退避 + Retry-After + jitter + 最大重试；调用方应据此整批 fail-closed，而非当成"假曲"。
- 全局限流：未命中缓存的请求间隔 ~3s（不是每首 sleep 那种）。
纯标准库。classify() 为纯逻辑、可离线单测。
"""
from __future__ import annotations

import json
import random
import re
import unicodedata
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SEARCH_URL = "https://itunes.apple.com/search"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_PATH = DATA_DIR / "itunes_cache.json"
CACHE_SCHEMA = 2

ACCEPT = {"exact_match", "acceptable_match"}
VERSION_WORDS = ("remix", "remixed", "remaster", "remastered", "live", "rework", "edit",
                 "acoustic", "instrumental", "demo", "reprise", "radio edit", "single edit",
                 "extended", "rerecorded", "re recorded", "cover", "karaoke", "version", "mix")

_MIN_INTERVAL = 3.0          # 全局限流：未命中缓存的请求最小间隔（秒）
_MAX_RETRIES = 3
_last_req = [0.0]

_PARENS = re.compile(r"[\(\（\[【].*?[\)\）\]】]")
_VERSION_PATTERNS = {
    word: re.compile(r"(?<!\w)" + r"[\s\-\u2010-\u2015]+".join(
        re.escape(part) for part in word.split()) + r"(?!\w)", re.IGNORECASE)
    for word in VERSION_WORDS
}


class _Transient(Exception):
    pass


def _strip_parens(s: str) -> str:
    return _PARENS.sub(" ", s or "")


def _key(s: str, *, strip_parentheses: bool = True) -> str:
    """保留各语言文字；拉丁字母容忍重音差异，标点与大小写不参与比较。

    旧白名单把韩文整段删成空串，不同韩文曲名因此相等；韩文艺人又会
    以空串命中任何拉丁艺人的子串规则。NFKD 之后重新组合 Hangul，
    只剥拉丁重音，保留日文浊点及其它语言有辨义作用的附加符号。
    """
    text = _strip_parens(s or "") if strip_parentheses else (s or "")
    text = unicodedata.normalize("NFKD", text).casefold()
    chars = []
    latin_base = False
    for char in text:
        category = unicodedata.category(char)
        if category.startswith("M"):
            if not latin_base:
                chars.append(char)
            continue
        latin_base = unicodedata.name(char, "").startswith("LATIN ")
        if category[0] in {"L", "N"}:
            chars.append(char)
    key = unicodedata.normalize("NFC", "".join(chars))
    return key if any(c.isalnum() for c in key) else ""


def _versions(s: str) -> set[str]:
    # Whole tokens: Deliver is not Live, Meditation is not Edit, Mixed is not Mix.
    # Hyphenated re-recorded is the same marker as the existing "re recorded".
    raw = unicodedata.normalize("NFKC", s or "")
    return {word for word, pattern in _VERSION_PATTERNS.items() if pattern.search(raw)}


def _version_kinds(s: str) -> set[str]:
    """同种版本的常见词形等价；radio edit / single edit 仍保留区别。"""
    aliases = {"remixed": "remix", "remastered": "remaster", "re recorded": "rerecorded"}
    kinds = {aliases.get(word, word) for word in _versions(s)}
    if len(kinds) > 1:
        kinds.discard("version")  # Acoustic 与 Acoustic Version 是同一种声明。
    return kinds


def _title_key(s: str) -> str:
    # iTunes also writes version suffixes as "Title - Live" or "Title – Radio Edit".
    # Only remove a separated suffix that actually declares a version marker.
    title = _PARENS.sub(lambda match: " " if _versions(match.group()) else match.group(), s or "")
    pieces = re.split(r"\s+[-–—]\s+", title, maxsplit=1)
    if len(pieces) == 2 and _versions(pieces[1]):
        title = pieces[0]
    # Non-version parentheses are real title words: "Song (For You)" is not "Song".
    return _key(title, strip_parentheses=False)


# ── 纯逻辑：分类（可离线单测）────────────────────────────────────────────────
def _artist_keys(s: str) -> set[str]:
    """艺人名的可接受写法集合。

    池里不少日系艺人写成「Ozora Kimijima (君島大空)」这种「拉丁名 (原文名)」，
    而 iTunes 只返回其中一种（多半是原文名）。只比完整串会永远 artist_mismatch，
    所以括号内外都算数。
    """
    s = str(s or "")
    keys = {_key(s)}
    if "(" in s and ")" in s:
        keys.add(_key(s.split("(", 1)[0]))
        keys.add(_key(s.split("(", 1)[1].rsplit(")", 1)[0]))
    return {k for k in keys if k}


def classify(cand_artist: str, cand_title: str, results: list[dict]) -> tuple[str, dict | None]:
    # ca 已被 ca_set 取代（括号内外都算命中），这里只留 ct
    ct = _title_key(cand_title)
    ca_set = _artist_keys(cand_artist)
    if not ct or not ca_set:
        return ("not_found", None)
    cver = _version_kinds(cand_title)
    saw_ver = saw_artist = None
    for r in results:
        ra = _key(r.get("artistName", ""))
        tn = r.get("trackName", "")
        if _title_key(tn) != ct:      # 主标题（去版本括号/后缀）必须一致
            continue
        version_mismatch = _version_kinds(tn) != cver
        artist_exact = ra in ca_set
        artist_sub = len(ra) >= 4 and any(
            len(k) >= 4 and (k in ra or ra in k) for k in ca_set)
        if (artist_exact or artist_sub) and not version_mismatch:
            return ("exact_match" if artist_exact else "acceptable_match", r)
        if (artist_exact or artist_sub) and version_mismatch:
            saw_ver = saw_ver or r
        else:
            saw_artist = saw_artist or r
    if saw_ver:
        return ("version_mismatch", saw_ver)
    if saw_artist:
        return ("artist_mismatch", saw_artist)
    return ("not_found", None)


# ── 缓存 ───────────────────────────────────────────────────────────────────
def load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_cache(cache: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 网络层（限流 + 退避 + 瞬时错误）─────────────────────────────────────────
def _throttle() -> None:
    dt = time.time() - _last_req[0]
    if dt < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - dt)
    _last_req[0] = time.time()


def _query(term: str, country: str) -> list[dict]:
    params = urllib.parse.urlencode({"term": term, "entity": "song", "limit": 10, "country": country})
    for attempt in range(_MAX_RETRIES + 1):
        _throttle()
        req = urllib.request.Request(SEARCH_URL + "?" + params, headers={"User-Agent": "music-daily/2.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r).get("results", [])
        except urllib.error.HTTPError as e:
            retry_after = e.headers.get("Retry-After") if e.headers else None
            transient = e.code == 429 or 500 <= e.code < 600
            if transient and attempt < _MAX_RETRIES:
                wait = float(retry_after) if (retry_after or "").isdigit() else 2 ** attempt + random.uniform(0, .5)
                time.sleep(wait)
                continue
            raise _Transient(f"HTTP {e.code}")
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as e:
            if attempt < _MAX_RETRIES:
                time.sleep(2 ** attempt + random.uniform(0, .5))
                continue
            raise _Transient(f"{type(e).__name__}: {e}")
    raise _Transient("max retries exceeded")


def _mk(status: str, best: dict | None, country: str, error: str = "", retryable: bool = False) -> dict:
    art = (best or {}).get("artworkUrl100", "")
    return {
        "schema": CACHE_SCHEMA,
        "lookup_ts": int(time.time()),
        "country": country,
        "status": status,
        # found = 「有标题匹配」，【不代表可用】——它对 version_mismatch /
        # artist_mismatch 也为真。采纳媒体的唯一判据是 status in ACCEPT。
        # 原注释写「兼容 build_daily：有标题匹配即给封面」，那正是把别人的歌
        # 挂上封面的那个 bug 的源头（已在 aea6cbb 修掉 build_daily 两处）。
        "found": bool(best),
        # 这里【不再】写 "accepted" 字段：它零消费者，却长得像权威判据，
        # 而没有任何东西保证它与 status 一致 —— 典型的 parallel path。
        # 三处真消费者（media_check ×2、merge_candidates ×1）都各自查 ACCEPT。
        # 不 bump CACHE_SCHEMA：schema 闸只比版本号不校验键集合，存量 1297 条
        # 带不带这个键都能正常读；bump 会让全部失效、重查约 65 分钟，
        # 超 merge.yml 的 60 分钟 timeout。
        "artwork": art.replace("100x100bb", "600x600bb") if art else "",
        "preview": (best or {}).get("previewUrl", ""),
        "apple_url": (best or {}).get("trackViewUrl", ""),
        "track_id": (best or {}).get("trackId", ""),
        "collection_id": (best or {}).get("collectionId", ""),
        "matched_artist": (best or {}).get("artistName", ""),
        "matched_title": (best or {}).get("trackName", ""),
        "collection_name": (best or {}).get("collectionName", ""),
        "release_year": ((best or {}).get("releaseDate", "") or "")[:4],
        "error_type": error,
        "retryable": retryable,
    }


def lookup(artist: str, title: str, cache: dict) -> dict:
    """按 artist + title 查 iTunes。返回 status 枚举之一（见模块 docstring）。

    不做专辑匹配。缓存保留现有键与 schema，避免让全部媒体重新联网；
    但必须用缓存中的实际曲名/艺人重新检查，不能让括号被省略的缓存键
    把原版与 Live 等版本混为一条。失败缓存只在同一原始查询下复用。
    """
    if not _artist_keys(artist) or not _title_key(title):
        return _mk("not_found", None, "US")
    key = _key(artist) + "|" + _key(title)
    ent = cache.get(key)
    if ent and ent.get("schema") == CACHE_SCHEMA and ent.get("status") != "transient_error":
        if ent.get("matched_artist") and ent.get("matched_title"):
            status, _ = classify(artist, title, [{
                "artistName": ent["matched_artist"], "trackName": ent["matched_title"]}])
            if status in ACCEPT:
                return dict(ent, status=status)
        if (ent.get("status") not in ACCEPT and ent.get("query_artist") == artist
                and ent.get("query_title") == title):
            return ent

    def remember(result: dict) -> dict:
        result.update(query_artist=artist, query_title=title)
        cache[key] = result
        return result

    best_nonexact = None  # (status, dict, country)
    try:
        for country in ("US", "JP"):
            results = _query(f"{artist} {title}", country)
            status, best = classify(artist, title, results)
            if status in ACCEPT:
                res = _mk(status, best, country)
                return remember(res)
            if best_nonexact is None and status != "not_found":
                best_nonexact = (status, best, country)
        # 最后手段：只搜曲名，但仅在能严格 exact 时采用（不降级）
        results = _query(title, "US")
        status, best = classify(artist, title, results)
        if status == "exact_match":
            res = _mk(status, best, "US")
            return remember(res)
    except _Transient as e:
        return _mk("transient_error", None, "US", error=str(e), retryable=True)  # 不写缓存

    status, best, country = best_nonexact if best_nonexact else ("not_found", None, "US")
    res = _mk(status, best, country)
    return remember(res)


if __name__ == "__main__":
    import sys
    c = load_cache()
    a, t = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("aus", "Halo")
    print(json.dumps(lookup(a, t, c), ensure_ascii=False, indent=2))
    save_cache(c)
