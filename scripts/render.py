"""渲染浅色玻璃卡片风格的每日日报网页（纯 Python 字符串模板，零依赖）。

浅色玻璃卡片美学：毛玻璃吸顶导航、封面圆形播放按钮（点封面播 30s 试听）、
底部「正在播放」迷你播放器、编辑部式 hero、squircle 封面 + 悬停浮起、载入分级动画。
每首含：封面 / 曲名·艺人 / 专辑·年份 / 风格·气质标签 / 一句话艺人介绍 / 推荐理由 /
最适合场景 / 试听 / 官方播放页·网易云跳转 / 来源。页尾附可一键复制的网易云导入文本块。
"""
from __future__ import annotations

import html
import urllib.parse

ICON_PLAY = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.14v13.72a1 1 0 0 0 1.54.84l10.28-6.86a1 1 0 0 0 0-1.68L9.54 4.3A1 1 0 0 0 8 5.14z"/></svg>'
ICON_PAUSE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4h4v16H7zM13 4h4v16h-4z"/></svg>'
ICON_PIN = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7zm0 9.5A2.5 2.5 0 1 1 12 6a2.5 2.5 0 0 1 0 5.5z"/></svg>'
ICON_NOTE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 17.5a2.5 2.5 0 1 1-2.5-2.5c.55 0 1.06.18 1.5.47V6l10-2v9.5A2.5 2.5 0 1 1 15.5 11c.55 0 1.06.18 1.5.47V6.24L9 7.8v9.7z"/></svg>'

CSS = """
:root{
  --bg:#ffffff; --bg2:#fbfbfd; --card:#ffffff; --ph:#f0f0f3;
  --text:#1d1d1f; --sub:#6e6e73; --dim:#86868b;
  --accent:#fa2536; --accent-ink:#e11d2b;
  --pill-bg:#f2f2f4; --pill-ink:#515154;
  --line:#e6e6eb; --hair:#d2d2d7;
  --glass:rgba(255,255,255,.72);
  --shadow:0 1px 2px rgba(0,0,0,.04),0 8px 24px rgba(0,0,0,.06);
  --radius:20px;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{
  font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","SF Pro Text",
    "PingFang SC","Hiragino Sans GB","Microsoft YaHei",system-ui,sans-serif;
  background:var(--bg); color:var(--text); line-height:1.55;
  -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility;
  padding-bottom:120px;
}
.wrap{max-width:780px; margin:0 auto; padding:0 22px}

/* 毛玻璃吸顶导航 */
.nav{position:sticky; top:0; z-index:50; background:var(--glass);
  backdrop-filter:saturate(180%) blur(20px); -webkit-backdrop-filter:saturate(180%) blur(20px);
  border-bottom:1px solid var(--line)}
.nav .wrap{display:flex; align-items:center; justify-content:space-between; height:52px}
.brand{display:flex; align-items:center; gap:9px; font-weight:700; font-size:16px; letter-spacing:-.01em}
.brand .glyph{width:26px; height:26px; border-radius:8px; display:grid; place-items:center;
  background:linear-gradient(150deg,#fb5560,var(--accent)); color:#fff; box-shadow:0 2px 6px rgba(250,37,54,.35)}
.brand .glyph svg{width:16px; height:16px; fill:#fff}
.nav .navdate{color:var(--dim); font-size:13px; font-variant-numeric:tabular-nums}

/* Hero */
header.hero{position:relative; padding:60px 22px 30px; text-align:center; overflow:hidden}
header.hero::before{content:""; position:absolute; inset:-40% 0 auto 0; height:340px; z-index:-1;
  background:
    radial-gradient(60% 70% at 22% 0%,rgba(250,37,54,.10),transparent 60%),
    radial-gradient(55% 70% at 82% 8%,rgba(255,138,90,.12),transparent 60%),
    radial-gradient(50% 60% at 50% 30%,rgba(90,120,255,.06),transparent 60%)}
.hero .eyebrow{color:var(--accent-ink); font-size:12px; font-weight:700; letter-spacing:.24em;
  text-transform:uppercase}
.hero h1{font-size:46px; font-weight:800; letter-spacing:-.03em; line-height:1.05; margin:12px 0 8px}
.hero .sub{color:var(--sub); font-size:16px; font-variant-numeric:tabular-nums}
.hero .credo{color:var(--dim); font-size:13px; margin-top:16px; max-width:440px;
  margin-left:auto; margin-right:auto; line-height:1.6}
.hero .count{display:inline-flex; align-items:center; gap:6px; margin-top:18px;
  background:var(--pill-bg); color:var(--pill-ink); font-size:12.5px; font-weight:600;
  padding:5px 13px; border-radius:999px}

/* 列表 + 卡片 */
.list{display:flex; flex-direction:column; gap:14px; margin-top:26px}
.card{position:relative; background:var(--card); border:1px solid var(--line);
  border-radius:var(--radius); padding:16px; display:flex; gap:16px; align-items:flex-start;
  box-shadow:var(--shadow); transition:transform .25s ease, box-shadow .25s ease;
  opacity:0; transform:translateY(14px); animation:rise .55s cubic-bezier(.22,.61,.36,1) forwards;
  animation-delay:calc(var(--i,0)*40ms)}
.card:hover{transform:translateY(-2px); box-shadow:0 2px 4px rgba(0,0,0,.05),0 16px 40px rgba(0,0,0,.10)}
@keyframes rise{to{opacity:1; transform:none}}

/* 封面 + 播放按钮 */
.art{position:relative; width:118px; height:118px; flex:none}
.cover{width:118px; height:118px; border-radius:14px; object-fit:cover; display:block;
  background:var(--ph); box-shadow:0 6px 18px rgba(0,0,0,.16); transition:transform .3s ease}
.cover.ph{display:grid; place-items:center; font-weight:800; font-size:34px; color:#fff;
  background:linear-gradient(140deg,#fb5560,var(--accent))}
.art:hover .cover{transform:scale(1.02)}
.play{position:absolute; inset:0; margin:auto; width:46px; height:46px; border-radius:50%;
  border:none; cursor:pointer; display:grid; place-items:center; color:#fff;
  background:rgba(0,0,0,.42); backdrop-filter:blur(6px); -webkit-backdrop-filter:blur(6px);
  opacity:0; transform:scale(.86); transition:opacity .22s ease, transform .22s ease;
  box-shadow:0 4px 14px rgba(0,0,0,.3)}
.art:hover .play, .play.playing{opacity:1; transform:scale(1)}
.play svg{width:22px; height:22px; fill:#fff; margin-left:1px}
.play.playing{background:var(--accent)}
.play.playing svg{margin-left:0}

/* 文本 */
.body{flex:1; min-width:0}
.idx{color:var(--dim); font-size:12px; font-weight:700; letter-spacing:.04em;
  font-variant-numeric:tabular-nums}
.title{font-size:20px; font-weight:700; letter-spacing:-.015em; line-height:1.25; margin:3px 0 1px}
.artist{color:var(--text); font-size:15px; font-weight:600}
.album{color:var(--sub); font-size:13px; margin-top:3px; font-variant-numeric:tabular-nums}
.pills{margin:10px 0 8px; display:flex; flex-wrap:wrap; gap:6px}
.pill{font-size:11px; font-weight:500; color:var(--pill-ink); background:var(--pill-bg);
  border-radius:999px; padding:3px 10px; line-height:1.5}
.pill.mood{color:var(--accent-ink); background:rgba(250,37,54,.07)}
.oneliner{color:var(--sub); font-size:13px; font-style:italic; margin:8px 0 3px; line-height:1.55}
.why{color:var(--text); font-size:14.5px; margin:6px 0; line-height:1.6}
.scene{display:flex; align-items:center; gap:5px; color:var(--dim); font-size:12.5px; margin:8px 0 10px}
.scene svg{width:13px; height:13px; fill:var(--dim); flex:none}
.scene b{color:var(--sub); font-weight:600}
.links{display:flex; flex-wrap:wrap; gap:8px; align-items:center}
.chip{display:inline-flex; align-items:center; gap:4px; font-size:12.5px; font-weight:600;
  color:var(--accent-ink); background:rgba(250,37,54,.08); border-radius:999px;
  padding:5px 12px; text-decoration:none; transition:background .2s ease}
.chip:hover{background:rgba(250,37,54,.14)}
.chip.ghost{color:var(--pill-ink); background:var(--pill-bg)}
.chip.ghost:hover{background:#e8e8ed}
.src{color:var(--dim); font-size:11.5px; margin-top:9px}
.src a{color:var(--dim)}

/* 网易云导入 */
.nc{margin:34px 0 0; background:var(--bg2); border:1px solid var(--line);
  border-radius:var(--radius); padding:22px}
.nc h2{font-size:18px; letter-spacing:-.01em; margin-bottom:4px}
.nc p{color:var(--sub); font-size:13px; margin-bottom:14px; line-height:1.6}
.nc pre{background:#fff; border:1px solid var(--line); border-radius:14px; padding:15px;
  color:var(--text); font-size:13px; white-space:pre-wrap; line-height:1.7;
  font-family:"SF Mono",ui-monospace,Menlo,Consolas,monospace; max-height:300px; overflow:auto}
.copybtn{margin-top:12px; background:var(--accent); color:#fff; border:none; border-radius:999px;
  padding:10px 22px; font-size:14px; font-weight:600; cursor:pointer; transition:transform .12s ease,filter .2s ease}
.copybtn:hover{filter:brightness(1.05)}
.copybtn:active{transform:scale(.97)}

footer{color:var(--dim); font-size:12px; text-align:center; margin-top:44px; line-height:1.8}

/* 底部「正在播放」迷你播放器 */
.np{position:fixed; left:0; right:0; bottom:0; z-index:60; transform:translateY(120%);
  transition:transform .4s cubic-bezier(.22,.61,.36,1); background:var(--glass);
  backdrop-filter:saturate(180%) blur(24px); -webkit-backdrop-filter:saturate(180%) blur(24px);
  border-top:1px solid var(--line)}
.np.show{transform:none}
.np-in{max-width:780px; margin:0 auto; padding:10px 22px; display:flex; align-items:center; gap:14px}
.np img{width:46px; height:46px; border-radius:9px; object-fit:cover; flex:none; box-shadow:0 2px 8px rgba(0,0,0,.2)}
.np-meta{flex:1; min-width:0}
.np-title{font-size:14px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis}
.np-artist{font-size:12.5px; color:var(--sub); white-space:nowrap; overflow:hidden; text-overflow:ellipsis}
.np-toggle{width:40px; height:40px; border-radius:50%; border:none; cursor:pointer; flex:none;
  background:var(--accent); color:#fff; display:grid; place-items:center; box-shadow:0 3px 10px rgba(250,37,54,.35)}
.np-toggle svg{width:19px; height:19px; fill:#fff}
.np-time{font-size:12px; color:var(--dim); font-variant-numeric:tabular-nums; flex:none; width:38px; text-align:right}
.np-prog{position:absolute; left:0; right:0; top:0; height:2px; background:rgba(0,0,0,.08)}
.np-bar{height:100%; width:0; background:var(--accent); transition:width .2s linear}

@media(max-width:560px){
  .hero h1{font-size:34px}
  .card{flex-direction:row}
  .art,.cover{width:92px; height:92px}
  .title{font-size:18px}
  .wrap{padding:0 16px}
}
@media(prefers-reduced-motion:reduce){
  .card{animation:none; opacity:1; transform:none}
  html{scroll-behavior:auto}
}
"""

JS = """
const audio = new Audio();
let current = null;  // 当前播放的 play 按钮
const np = document.getElementById('np');
const npCover = document.getElementById('np-cover');
const npTitle = document.getElementById('np-title');
const npArtist = document.getElementById('np-artist');
const npToggle = document.getElementById('np-toggle');
const npBar = document.getElementById('np-bar');
const npTime = document.getElementById('np-time');
const ICON_PLAY = `%PLAY%`;
const ICON_PAUSE = `%PAUSE%`;

function fmt(t){ if(!t||isNaN(t)) return '0:00'; const m=Math.floor(t/60), s=Math.floor(t%60); return m+':'+String(s).padStart(2,'0'); }
function setBtn(btn, playing){ btn.classList.toggle('playing', playing); btn.innerHTML = playing?ICON_PAUSE:ICON_PLAY; }

function playTrack(btn){
  if(current && current!==btn){ setBtn(current, false); }
  if(current===btn && !audio.paused){ audio.pause(); return; }
  if(current===btn && audio.paused){ audio.play(); return; }
  current = btn;
  audio.src = btn.dataset.src;
  audio.play();
  npCover.src = btn.dataset.cover || '';
  npTitle.textContent = btn.dataset.title;
  npArtist.textContent = btn.dataset.artist;
  np.classList.add('show');
}

document.querySelectorAll('.play').forEach(btn=>{
  btn.addEventListener('click', ()=>playTrack(btn));
});
npToggle.addEventListener('click', ()=>{ if(audio.paused) audio.play(); else audio.pause(); });
audio.addEventListener('play', ()=>{ if(current) setBtn(current,true); npToggle.innerHTML=ICON_PAUSE; });
audio.addEventListener('pause', ()=>{ if(current) setBtn(current,false); npToggle.innerHTML=ICON_PLAY; });
audio.addEventListener('timeupdate', ()=>{
  npBar.style.width = (audio.currentTime/(audio.duration||30)*100)+'%';
  npTime.textContent = fmt(audio.currentTime);
});
audio.addEventListener('ended', ()=>{ if(current){ setBtn(current,false);} npBar.style.width='0%'; });

function copyNC(){
  const t=document.getElementById('nc-text').innerText;
  navigator.clipboard.writeText(t).then(()=>{
    const b=document.getElementById('nc-btn'); const o=b.innerText;
    b.innerText='已复制 ✓'; setTimeout(()=>b.innerText=o,1600);
  });
}
"""


def _esc(s) -> str:
    return html.escape(str(s or ""))


def _ncsearch(track: dict) -> str:
    q = urllib.parse.quote(f"{track['title']} {track['artist']}")
    return f"https://music.163.com/#/search/m/?s={q}"


def _art_html(track: dict) -> str:
    art = track.get("_cover") or track.get("artwork") or ""
    if art:
        cover = f'<img class="cover" src="{_esc(art)}" alt="" loading="lazy">'
    else:
        initial = _esc((track.get("artist") or "?")[:1].upper())
        cover = f'<div class="cover ph">{initial}</div>'
    play = ""
    if track.get("_preview"):
        play = (
            f'<button class="play" data-src="{_esc(track["_preview"])}" '
            f'data-title="{_esc(track["title"])}" data-artist="{_esc(track["artist"])}" '
            f'data-cover="{_esc(art)}" aria-label="播放 30 秒试听">{ICON_PLAY}</button>'
        )
    return f'<div class="art">{cover}{play}</div>'


def _card(track: dict, idx: int) -> str:
    pills = "".join(
        f'<span class="pill">{_esc(g)}</span>' for g in (track.get("genres") or [])[:3]
    ) + "".join(
        f'<span class="pill mood">{_esc(m)}</span>' for m in (track.get("mood_tags") or [])[:2]
    )
    links = []
    if track.get("_apple"):
        links.append(f'<a class="chip" href="{_esc(track["_apple"])}" target="_blank" rel="noopener">listen ↗</a>')
    links.append(f'<a class="chip ghost" href="{_ncsearch(track)}" target="_blank" rel="noopener">netease ↗</a>')
    src = ""
    if track.get("source"):
        s = _esc(track["source"])
        src = (f'<a href="{_esc(track["source_url"])}" target="_blank" rel="noopener">{s}</a>'
               if track.get("source_url") else s)
    album_line = " · ".join(x for x in [_esc(track.get("album", "")), _esc(track.get("year", ""))] if x)
    return f"""
    <article class="card" style="--i:{idx-1}">
      {_art_html(track)}
      <div class="body">
        <div class="idx">#{idx:02d}</div>
        <h3 class="title">{_esc(track['title'])}</h3>
        <div class="artist">{_esc(track['artist'])}</div>
        <div class="album">{album_line}</div>
        <div class="pills">{pills}</div>
        <p class="oneliner">{_esc(track.get('artist_oneliner',''))}</p>
        <p class="why">{_esc(track.get('why',''))}</p>
        <div class="scene">{ICON_PIN}<span><b>最适合</b> · {_esc(track.get('scene',''))}</span></div>
        <div class="links">{''.join(links)}</div>
        <div class="src">来源 · {src}</div>
      </div>
    </article>"""


def build_html(date_str: str, tracks: list[dict], issue_no: int,
               netease_text: str) -> str:
    cards = "\n".join(_card(t, i) for i, t in enumerate(tracks, 1))
    nc = _esc(netease_text)
    js = JS.replace("%PLAY%", ICON_PLAY.replace("`", "")).replace("%PAUSE%", ICON_PAUSE.replace("`", ""))
    favicon = (
        "data:image/svg+xml,"
        + urllib.parse.quote(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            '<rect width="24" height="24" rx="6" fill="#fa2536"/>'
            '<path d="M9 17.5a2.5 2.5 0 1 1-2.5-2.5c.55 0 1.06.18 1.5.47V6l10-2v9.5A2.5 2.5 0 1 1 15.5 11'
            'c.55 0 1.06.18 1.5.47V6.24L9 7.8v9.7z" fill="#fff"/></svg>'
        )
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#ffffff">
<meta name="description" content="每日精选 15 首 · 旋律优先 · 气质优先 · 制作优先">
<title>每日音乐日报 · {_esc(date_str)}</title>
<link rel="icon" href="{favicon}">
<style>{CSS}</style>
</head>
<body>
<nav class="nav">
  <div class="wrap">
    <div class="brand"><span class="glyph">{ICON_NOTE}</span>每日音乐日报</div>
    <div class="navdate">{_esc(date_str)} · 第 {issue_no} 期</div>
  </div>
</nav>

<header class="hero">
  <div class="eyebrow">Daily Music</div>
  <h1>今日精选</h1>
  <div class="sub">{_esc(date_str)}</div>
  <div class="credo">旋律优先 · 气质优先 · 制作优先<br>越听越舒服，值得反复循环的 {len(tracks)} 首</div>
  <div class="count">🎧 今日 {len(tracks)} 首</div>
</header>

<main class="wrap">
  <div class="list">
    {cards}
  </div>

  <section class="nc">
    <h2>导入网易云音乐</h2>
    <p>复制下面的列表，网易云 App「新建歌单 → 导入」即可（每行「歌名 - 艺人」）。</p>
    <pre id="nc-text">{nc}</pre>
    <button class="copybtn" id="nc-btn" onclick="copyNC()">复制歌单</button>
  </section>

  <footer>
    每日 08:00 更新 · 封面与试听来自公开音乐接口<br>仅供个人聆听发现
  </footer>
</main>

<div class="np" id="np">
  <div class="np-prog"><div class="np-bar" id="np-bar"></div></div>
  <div class="np-in">
    <img id="np-cover" alt="">
    <div class="np-meta"><div class="np-title" id="np-title"></div><div class="np-artist" id="np-artist"></div></div>
    <div class="np-time" id="np-time">0:00</div>
    <button class="np-toggle" id="np-toggle" aria-label="播放/暂停">{ICON_PAUSE}</button>
  </div>
</div>

<script>{js}</script>
</body>
</html>"""
