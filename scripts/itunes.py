"""在线音乐接口（iTunes Search）：精确版本匹配 + 瞬时错误区分 + 全局限流 + 结构化缓存。

不再只有 found=True/False。lookup() 返回状态枚举之一：
  exact_match / acceptable_match / version_mismatch / artist_mismatch / album_mismatch
  / not_found / transient_error
- 精确匹配：艺人规范化后一致（exact=完全相等 / acceptable=互为子串），主标题（去版本括号）一致，
  且结果不得含候选未声明的版本词（Remix/Live/Remaster/Edit/... → version_mismatch）。
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


class _Transient(Exception):
    pass


def _strip_parens(s: str) -> str:
    return _PARENS.sub(" ", s or "")


def _key(s: str) -> str:
    """归一化成可比较的键：先剥重音，再只留数字/拉丁小写/中日文字。

    必须先 NFKD 剥重音再过滤——否则带重音的字符会被整个删掉：
    「María」→ 'mara'（í 消失）而 iTunes 返回的「Maria」→ 'maria'，两边永远比不上。
    这正是 Khruangbin - María También 这类曲子一直 not_found、页面只显示首字母的原因。
    """
    t = unicodedata.normalize("NFKD", _strip_parens(s or ""))
    t = "".join(c for c in t if not unicodedata.combining(c))   # 去掉重音记号
    return re.sub(r"[^0-9a-z一-鿿぀-ヿ]+", "", t.lower())


def _versions(s: str) -> set[str]:
    raw = (s or "").lower()
    return {w for w in VERSION_WORDS if w in raw}


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
    ct = _key(cand_title)
    ca_set = _artist_keys(cand_artist)
    cver = _versions(cand_title)
    saw_ver = saw_artist = None
    for r in results:
        ra = _key(r.get("artistName", ""))
        tn = r.get("trackName", "")
        if _key(tn) != ct:            # 主标题（去版本括号）必须一致
            continue
        extra = _versions(tn) - cver  # 结果多出的版本词
        artist_exact = ra in ca_set
        artist_sub = any(len(k) >= 4 and (k in ra or ra in k) for k in ca_set)
        if (artist_exact or artist_sub) and not extra:
            return ("exact_match" if artist_exact else "acceptable_match", r)
        if (artist_exact or artist_sub) and extra:
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


def lookup(artist: str, title: str, cache: dict, album: str = "") -> dict:
    """按 artist + title 查 iTunes。返回 status 枚举之一（见模块 docstring）。

    ⚠️ **album 参数当前【不参与匹配】，纯占位。** 2026-08-04 审计确认：
    它从声明起就没被读过，`album_mismatch` 因此从未被任何代码产生
    （merge_candidates 的计数器恒为 0）。merge_candidates:170 在传这个参数，
    调用方误以为有专辑级校验 —— 所以这里必须写明，而不是留个沉默的死参数。

    没有直接实现的原因：缓存 1106 条里【一条都没存 collection 字段】，
    要做专辑匹配得先改 CACHE_SCHEMA 再全量重查，每条限流 3s ≈ 55 分钟，
    而且会动到现役的 99% 命中数据。收益（专辑级精度）远小于风险，暂不做。
    真要做的话：_mk() 里补 collection → bump CACHE_SCHEMA → 重查 → 再在
    classify 里加判据，四步一起，缺一步都会静默失效。
    """
    key = _key(artist) + "|" + _key(title)
    ent = cache.get(key)
    if ent and ent.get("schema") == CACHE_SCHEMA and ent.get("status") != "transient_error":
        return ent

    best_nonexact = None  # (status, dict, country)
    try:
        for country in ("US", "JP"):
            results = _query(f"{artist} {title}", country)
            status, best = classify(artist, title, results)
            if status in ACCEPT:
                res = _mk(status, best, country)
                cache[key] = res
                return res
            if best_nonexact is None and status != "not_found":
                best_nonexact = (status, best, country)
        # 最后手段：只搜曲名，但仅在能严格 exact 时采用（不降级）
        results = _query(title, "US")
        status, best = classify(artist, title, results)
        if status in ACCEPT:
            res = _mk(status, best, "US")
            cache[key] = res
            return res
    except _Transient as e:
        return _mk("transient_error", None, "US", error=str(e), retryable=True)  # 不写缓存

    status, best, country = best_nonexact if best_nonexact else ("not_found", None, "US")
    res = _mk(status, best, country)
    cache[key] = res
    return res


if __name__ == "__main__":
    import sys
    c = load_cache()
    a, t = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("aus", "Halo")
    print(json.dumps(lookup(a, t, c), ensure_ascii=False, indent=2))
    save_cache(c)
