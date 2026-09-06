"""Render verified discovery metadata without presenting it as curated copy."""
from __future__ import annotations

import html
import json
from pathlib import Path
import urllib.parse

from render_grid import CSS, ICON_HEART, ICON_NEXT, ICON_PAUSE, ICON_PLAY, ICON_PREV
from ui_common import UI_JS, site_nav

DIRECTORY = Path(__file__).resolve().parent
PAGE_SIZE = 36


def _url(value: object, hosts: set[str]) -> str:
    value = str(value or "")
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError:
        return ""
    return value if parsed.scheme == "https" and parsed.hostname in hosts else ""


def _normalize(tracks: list[dict]) -> list[dict]:
    result = []
    for track in tracks:
        result.append({
            "id": str(track.get("review_id") or track.get("id") or ""),
            "title": str(track.get("title") or ""), "artist": str(track.get("artist") or ""),
            "album": str(track.get("album") or ""),
            "year": str(track.get("apple_edition_year") or ""),
            "genre": str(track.get("apple_genre") or ""),
            "duration": int(track.get("duration_ms") or 0),
            "cover": _url(track.get("artwork_url"), {"is1-ssl.mzstatic.com", "is2-ssl.mzstatic.com", "is3-ssl.mzstatic.com", "is4-ssl.mzstatic.com", "is5-ssl.mzstatic.com"}),
            "preview": _url(track.get("preview_url"), {"audio-ssl.itunes.apple.com"}),
            "apple": _url(track.get("apple_url"), {"music.apple.com"}),
        })
    return result


def _card(track: dict) -> str:
    esc = html.escape
    spotify = "https://open.spotify.com/search/" + urllib.parse.quote(track["artist"] + " " + track["title"])
    cover = track["cover"].replace("600x600bb", "160x160bb")
    artwork = f'<img src="{esc(cover)}" alt="" loading="lazy" width="80" height="80">' if cover else '<span class="discover-cover-missing" aria-hidden="true">♪</span>'
    apple_link = (f'<a href="{esc(track["apple"])}" target="_blank" rel="noopener noreferrer">APPLE MUSIC ↗</a>'
                  if track["apple"] else "")
    return (f'<article class="discovery-track" data-id="{esc(track["id"])}">'
            f'<div class="discover-artwork">{artwork}</div><div class="discover-info">'
            f'<h2>{esc(track["title"])}</h2><p class="discover-artist">{esc(track["artist"])}</p>'
            f'<p class="discover-album">{esc(track["album"])} · {esc(track["year"])}</p>'
            f'<div class="discover-links">{apple_link}'
            f'<a href="{esc(spotify)}" target="_blank" rel="noopener noreferrer">SPOTIFY 搜索 ↗</a></div></div>'
            f'<div class="discover-controls"><button class="discover-play" type="button" aria-label="试听：{esc(track["title"])}" disabled>{ICON_PLAY}{ICON_PAUSE}<span>试听片段</span></button>'
            f'<button class="heart" type="button" aria-label="收藏：{esc(track["title"])}" aria-pressed="false" disabled>{ICON_HEART}</button></div></article>')


def build_html(tracks: list[dict]) -> str:
    """Return a self-contained page; callers pass the queue's ``tracks`` list."""
    if isinstance(tracks, dict):
        tracks = tracks.get("tracks", [])
    data = _normalize(tracks)
    count = len(data)
    artists = len({t["artist"].casefold() for t in data})
    first_page = "\n".join(_card(t) for t in data[:PAGE_SIZE])
    embedded = json.dumps(data, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c")
    css = (DIRECTORY / "discover_ui.css").read_text(encoding="utf-8")
    js = (DIRECTORY / "discover_ui.js").read_text(encoding="utf-8")
    icons = json.dumps({"play": ICON_PLAY, "pause": ICON_PAUSE, "heart": ICON_HEART}, separators=(",", ":"))
    return f'''<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#f3f0e8"><meta name="description" content="{count} 首新发现，搜索、试听，把喜欢的收藏。曲目资料已核对，仍待逐首精选。">
<title>新发现 · MUSIC DAILY</title><link rel="manifest" href="manifest.webmanifest"><link rel="apple-touch-icon" href="icon-180.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@100;300;400&family=Space+Mono:wght@400;700&family=Noto+Sans+SC:wght@100;300;400&display=swap" rel="stylesheet">
<style>{CSS}{css}</style></head><body>
{site_nav('discover')}
<main class="wrap" id="main">
 <header class="discover-hero"><div><p class="eyebrow">the discovery shelf</p><h1>新发现。<br><span>从熟悉的唱片，再往里听。</span></h1><p class="lead">{count:,} 首新发现，来自 {artists} 位已收录艺人。曲名、艺人与专辑资料已经核对，仍待逐首精选；先听一段，喜欢的就留下。</p><div class="discover-hero-actions"><button class="primary-action" id="discover-start" type="button" disabled>▶ 从第一首试听</button><a class="discover-curated-link" href="daily.html">去听今日精选 ↗</a></div></div><div class="discover-stamp"><b>{count:,}</b><span>首新发现 / 待精选</span></div></header>
 <section class="discover-toolbar" aria-label="新发现筛选"><div class="filterbar">
  <label class="field search-field" for="discover-search">在新发现里找歌<input id="discover-search" type="search" placeholder="搜索曲名、艺人或专辑" autocomplete="off" disabled></label>
  <label class="field" for="discover-genre">流派<select id="discover-genre" disabled><option value="">全部流派</option></select></label>
  <label class="field" for="discover-decade">年代<select id="discover-decade" disabled><option value="">全部年代</option></select></label>
  <button class="tbtn line" id="discover-reset" type="button" disabled>清空筛选</button></div>
  <div class="tools"><button class="tbtn" id="discover-favorites" type="button" aria-pressed="false" disabled>♡ 只看收藏</button><button class="tbtn line" id="discover-export" type="button" disabled>导出收藏</button><span class="discover-save-note">收藏和今日精选共用，跨期保留。</span></div>
  <div class="filter-status"><span id="discover-count" role="status">显示前 {min(count, PAGE_SIZE)} / {count:,} 首</span><span>new discoveries</span></div>
 </section>
 <noscript><p class="empty-state">开启 JavaScript 即可搜索全部 {count:,} 首、试听及收藏。下方链接仍可直接在音乐平台打开。</p></noscript>
 <section id="discover-list" class="discover-list" aria-label="新发现曲目">{first_page}</section>
 <section class="empty-state" id="discover-empty" hidden><strong>这里暂时没找到。</strong><p>换个关键词，或清空筛选再找找。</p><button class="tbtn" id="discover-empty-reset" type="button">清空筛选</button></section>
 <nav class="discover-pagination" aria-label="新发现分页"><button class="tbtn" id="discover-prev-page" type="button" disabled>上一页</button><span id="discover-page">1 / {max(1, (count + PAGE_SIZE - 1) // PAGE_SIZE)}</span><button class="tbtn" id="discover-next-page" type="button" disabled>下一页</button></nav>
 <section class="export" id="discover-export-box" hidden><div class="h">saved tracks <button class="tbtn" id="discover-export-close" type="button">收起</button></div><div class="in"><p>完整歌曲请前往音乐平台。复制后可按「曲名 - 艺人」导入。</p><pre id="discover-export-text"></pre><button class="tbtn" id="discover-copy" type="button">复制收藏</button><button class="tbtn line" id="discover-download" type="button">下载清单</button></div></section>
 <footer class="discover-footer"><span>试听与封面来自 Apple · 年份按当前发行版本显示</span><a href="daily.html">今日精选 ↗</a></footer>
</main>
<div id="np" role="region" aria-label="试听播放器"><img id="np-cover" alt=""><div id="np-meta"><div id="np-title"></div><div id="np-artist"></div></div><button id="np-prev" class="np-btn" type="button" aria-label="上一首">{ICON_PREV}</button><button id="np-toggle" class="np-btn" type="button" aria-label="播放试听">{ICON_PLAY}{ICON_PAUSE}</button><button id="np-next" class="np-btn" type="button" aria-label="下一首">{ICON_NEXT}</button><div id="np-bar" role="slider" tabindex="0" aria-label="试听进度" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><div id="np-fill"></div></div><span id="np-time">0:00</span><button id="np-close" class="np-btn" type="button" aria-label="关闭播放器">×</button></div>
<script id="discovery-data" type="application/json">{embedded}</script><script>{UI_JS}\nconst DISCOVERY_ICONS={icons};\n{js}</script>
</body></html>'''


if __name__ == "__main__":
    import sys
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DIRECTORY.parent / "data/discovery.json"
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else DIRECTORY.parent / "site/discover.html"
    payload = json.loads(source.read_text(encoding="utf-8"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_html(payload), encoding="utf-8")
    print(target)
