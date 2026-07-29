"""补池助手：按 profile 从乐评/社区搜候选线索，供 LLM 策展成 pool.json 条目。

发现是「重」活（要审美判断 + 核实真实），不在每日关键路径。本脚本只做**找线索**：
按 4 气质簇跑一批 profile 导出的查询，抓回 标题/URL/摘要，落 data/discover_leads.json。
真正把线索变成打好美学标签、写好卡片、核过来源的 pool 条目，由 LLM 按下方总开关完成。

后端：TAVILY_API_KEY 存在走 Tavily（结果干净）；否则退 DuckDuckGo。纯 stdlib、自包含。
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

# ── 策展总开关（LLM 把线索转成 pool 条目时的 persona，务必遵守 profile）──────────
CURATION_PROMPT = """\
像 Pitchfork 编辑、Bandcamp Daily 选曲人、Resident Advisor 的电子乐耳朵、以及一个听了
二十年独立音乐的朋友一起推荐。不追猎奇、不追冷门、不追评分；找一听就想收藏、一个月后还在
循环、十年后依然想起的作品。选曲按【气质+制作+旋律】而非流派：旋律必须存在，好听>耐听>
制作>气质>易循环>审美，不因历史地位/高分/经典/热门而选。命中黑名单（EDM/dubstep/metal/
hyperpop/math rock 炫技/jazz fusion 炫技/只有氛围没旋律的 ambient 等）一律排除。
每条 pool 条目必须核实真实（Bandcamp/RYM/Wikipedia/厂牌页可查），绝不编造曲名。
字段：id/title/artist/year/album/genres[]/genre_stars(3-5)/mood_tags[]/production_tags[]/
instrumentation[]/vocal_style/bpm_band/has_melody(true)/scene/artist_oneliner/why(<=2句)/
fit_score(0-100)/source/source_url/added_date。
"""

# ── profile 导出的搜索查询（4 气质簇）──────────────────────────────────────────
SEED_QUERIES = [
    'Shibuya-kei Japanese indie pop best tracks like Lamp cero site:daily.bandcamp.com',
    'Japanese city pop sophisti-pop jazz pop essential songs rateyourmusic',
    'folktronica organic electronic best albums Bibio Four Tet Bandcamp Daily',
    'melodic IDM downtempo warm analog best tracks The Quietus',
    'dream pop bedroom pop refined airy best songs Beach House Men I Trust pitchfork',
    'quiet alternative R&B neo soul mellow best tracks reddit',
    'midwest emo clean jangle guitar soft best songs',
    'modern bossa nova MPB downtempo airy best tracks Bandcamp',
    'trip-hop slowcore chamber pop nostalgic best songs',
    'ambient folk nylon fingerstyle woody best tracks',
]


def tavily(query: str, key: str, k: int = 6) -> list[dict]:
    body = json.dumps({"api_key": key, "query": query, "max_results": k}).encode()
    req = urllib.request.Request(
        "https://api.tavily.com/search", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        data = json.load(r)
    return [{"title": x.get("title"), "url": x.get("url"),
             "snippet": x.get("content", "")[:300]} for x in data.get("results", [])]


def ddg(query: str, k: int = 6) -> list[dict]:
    params = urllib.parse.urlencode({"q": query, "format": "json", "no_html": 1})
    req = urllib.request.Request(
        "https://api.duckduckgo.com/?" + params,
        headers={"User-Agent": "music-daily/1.0"},
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        data = json.load(r)
    out = []
    for topic in data.get("RelatedTopics", [])[:k]:
        if "Text" in topic:
            out.append({"title": topic.get("Text", "")[:120],
                        "url": topic.get("FirstURL", ""), "snippet": topic.get("Text", "")})
    return out


def main() -> None:
    key = os.environ.get("TAVILY_API_KEY", "")
    backend = "tavily" if key else "ddg"
    print(f"[discover] 后端={backend}（无 TAVILY_API_KEY 时覆盖较弱，建议配 key）")
    leads: dict[str, list[dict]] = {}
    for q in SEED_QUERIES:
        try:
            leads[q] = tavily(q, key) if key else ddg(q)
        except Exception as e:
            leads[q] = [{"error": f"{type(e).__name__}: {e}"}]
        print(f"  · {q[:60]}… → {len(leads[q])} 条")
    out = Path(__file__).resolve().parent.parent / "data" / "discover_leads.json"
    out.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[discover] 线索已落 {out}")
    print("[discover] 下一步：LLM 按 CURATION_PROMPT 把线索核实+打标签+写卡片，append 进 pool.json")


if __name__ == "__main__":
    main()
