"""iTunes Search API 查询：专辑封面 / 30s 试听 / Apple Music 链接，带本地缓存。

纯标准库（urllib）。GitHub Actions 托管 runner 与本地环境均有公网出口，iTunes 可直连。
查不到的曲目返回 found=False，由上层回退占位封面。
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

SEARCH_URL = "https://itunes.apple.com/search"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_PATH = DATA_DIR / "itunes_cache.json"


def _norm(s: str) -> str:
    """归一化用于模糊匹配：小写、去括号内容、去标点、压空格。"""
    s = s.lower()
    s = re.sub(r"[\(\（\[].*?[\)\）\]]", " ", s)  # 去 (feat. ...) 等
    s = re.sub(r"[^0-9a-z぀-ヿ一-鿿]+", " ", s)  # 保留中日文
    return re.sub(r"\s+", " ", s).strip()


def _score(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_cache(cache: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# 先查美区，miss 再查日区（日系 city pop / shibuya-kei 常只在日区上架）
COUNTRIES = ("US", "JP")


def _query(term: str, limit: int = 8, country: str = "US") -> list[dict]:
    params = urllib.parse.urlencode(
        {"term": term, "entity": "song", "limit": limit, "country": country}
    )
    req = urllib.request.Request(
        SEARCH_URL + "?" + params, headers={"User-Agent": "music-daily/1.0"}
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r).get("results", [])


def _best_match(results: list[dict], artist: str, title: str) -> dict | None:
    best, best_s = None, 0.0
    for t in results:
        s = 0.6 * _score(t.get("trackName", ""), title) + 0.4 * _score(
            t.get("artistName", ""), artist
        )
        if s > best_s:
            best, best_s = t, s
    # 阈值：曲名+艺人综合相似度过低视为没匹配上
    return best if best_s >= 0.55 else None


def lookup(artist: str, title: str, cache: dict, sleep: float = 0.2) -> dict:
    """返回 {found, artwork, preview, apple_url, matched_artist, matched_title}。

    artwork 已替换为 600x600 高清。命中缓存不重复请求。
    """
    key = f"{_norm(artist)}|{_norm(title)}"
    if key in cache:
        return cache[key]

    result = {
        "found": False,
        "artwork": "",
        "preview": "",
        "apple_url": "",
        "matched_artist": "",
        "matched_title": "",
    }
    try:
        m = None
        for country in COUNTRIES:  # 美区优先，日区兜底
            m = _best_match(_query(f"{artist} {title}", country=country), artist, title)
            if m is None:  # 退一步只搜曲名
                m = _best_match(_query(title, country=country), artist, title)
            if m:
                break
        if m:
            art = m.get("artworkUrl100", "")
            result = {
                "found": True,
                "artwork": art.replace("100x100bb", "600x600bb"),
                "preview": m.get("previewUrl", ""),
                "apple_url": m.get("trackViewUrl", ""),
                "matched_artist": m.get("artistName", ""),
                "matched_title": m.get("trackName", ""),
            }
        time.sleep(sleep)  # 对 iTunes 客气一点
    except Exception as e:  # 网络/解析失败：留空由上层回退，不中断整批
        result["error"] = f"{type(e).__name__}: {e}"

    cache[key] = result
    return result


if __name__ == "__main__":
    import sys

    c = load_cache()
    art, ti = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("Bibio", "Lovers' Carvings")
    print(json.dumps(lookup(art, ti, c), ensure_ascii=False, indent=2))
    save_cache(c)
