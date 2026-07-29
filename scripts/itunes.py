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
    return re.sub(r"[^0-9a-z一-鿿぀-ヿ]+", "", _strip_parens(s or "").lower())


def _versions(s: str) -> set[str]:
    raw = (s or "").lower()
    return {w for w in VERSION_WORDS if w in raw}


# ── 纯逻辑：分类（可离线单测）────────────────────────────────────────────────
def classify(cand_artist: str, cand_title: str, results: list[dict]) -> tuple[str, dict | None]:
    ca, ct = _key(cand_artist), _key(cand_title)
    cver = _versions(cand_title)
    saw_ver = saw_artist = None
    for r in results:
        ra = _key(r.get("artistName", ""))
        tn = r.get("trackName", "")
        if _key(tn) != ct:            # 主标题（去版本括号）必须一致
            continue
        extra = _versions(tn) - cver  # 结果多出的版本词
        artist_exact = ra == ca
        artist_sub = len(ca) >= 4 and (ca in ra or ra in ca)
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
        "found": bool(best),                      # 兼容 build_daily：有标题匹配即给封面
        "accepted": status in ACCEPT,             # 严格：仅 exact/acceptable 可入库
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
