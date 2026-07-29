"""渲染工业 / 瑞士国际主义(Swiss)风格的每日日报网页（纯 Python 模板，零依赖）。

设计规范（自研的工程/网格美学，不隶属任何特定品牌）：
- 字体：Univers Next Pro 的免费替身 Inter 100/300（极细）+ Space Mono（技术数据）+ Noto Sans SC；
  标题小写、正文字重 300、层级靠字号不靠加粗。
- 配色：底 #f5f5f5（非纯白）、字 #0f0e12（非纯黑）、发丝灰阶、蓝 #0071bb / LCD 绿 #006837 /
  强调橙 #f05a24。多色做流派分类色标。
- 版式：12 栏网格、方角（border-radius:0）、几乎无阴影、发丝线 + 工程方格纸分格、vw/clamp 间距。
- 动效：极度克制、.2s、hover opacity:.7、播放键 scale(.94)+bulge、LCD 跑马灯 + boot 打字机、
  卡片 IntersectionObserver 分级进场。

公开接口 build_html(date_str, tracks, issue_no, netease_text) 与 render.py 一致。
"""
from __future__ import annotations

import html
import urllib.parse

# LCD 上的像素小猫（绿屏设备宠物感）：会眨眼(cat-eyes)、甩尾(cat-tail)、轻轻呼吸摇摆(整体 bob)
ICON_CAT = (
    '<svg class="cat" viewBox="0 0 16 15" shape-rendering="crispEdges" aria-hidden="true">'
    '<g class="cat-tail"><rect x="12" y="9" width="2" height="2"/><rect x="13" y="7" width="2" height="2"/>'
    '<rect x="14" y="6" width="1" height="2"/></g>'
    '<rect x="2" y="0" width="3" height="2"/><rect x="11" y="0" width="3" height="2"/>'
    '<rect x="2" y="1" width="12" height="7"/><rect x="3" y="8" width="9" height="5"/>'
    '<rect x="3" y="13" width="3" height="1"/><rect x="9" y="13" width="3" height="1"/>'
    '<rect class="blush" x="2" y="5" width="1" height="1"/><rect class="blush" x="13" y="5" width="1" height="1"/>'
    '<rect class="nose" x="7" y="5" width="2" height="1"/>'
    '<g class="cat-eyes"><rect x="4" y="3" width="2" height="2"/><rect x="10" y="3" width="2" height="2"/>'
    '<rect class="glint" x="5" y="3" width="1" height="1"/><rect class="glint" x="11" y="3" width="1" height="1"/></g>'
    '</svg>'
)
# 道具：吃饭用的食盆、玩耍用的小球（配合行为循环出现）
ICON_BOWL = ('<svg viewBox="0 0 12 6" shape-rendering="crispEdges" aria-hidden="true">'
             '<rect class="food" x="3" y="1" width="6" height="1"/>'
             '<rect x="1" y="2" width="10" height="1"/><rect x="2" y="3" width="8" height="2"/></svg>')
ICON_BALL = ('<svg viewBox="0 0 6 6" shape-rendering="crispEdges" aria-hidden="true">'
             '<rect x="1" y="1" width="4" height="4"/><rect class="hl" x="1" y="1" width="1" height="1"/></svg>')

# 工程编码色思路的一组多色 + 补色，做流派分类色标（小面积）
KNOB = ["#0071bb", "#006837", "#f05a24", "#fab413", "#b81d13", "#0f0e12"]


def _knob(seed: str) -> str:
    return KNOB[sum(ord(c) for c in (seed or "x")) % len(KNOB)]


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --white:#fff; --paper:#f5f5f5; --ink:#0f0e12;
  --g100:#e5e5e5; --g200:#ccc; --g300:#b2b2b2; --g500:#a1a7af;
  --g600:#767676; --g900:#4d4d4d; --g1000:#272727;
  --blue:#0071bb; --green:#00a651; --green-d:#006837; --orange:#f05a24;
  --red:#b81d13; --yellow:#fab413;
  --sans:"Inter","Noto Sans SC","Helvetica Neue",Arial,sans-serif;
  --mono:"Space Mono","JetBrains Mono",ui-monospace,Menlo,monospace;
  --fs-10:clamp(11px,.92vw,13px); --fs-15:clamp(12px,1.1vw,15px);
  --fs-20:clamp(15px,1.5vw,20px); --fs-25:clamp(19px,2.1vw,27px);
  --fs-30:clamp(23px,2.7vw,36px); --fs-40:clamp(34px,5vw,68px);
  --sp-xs:clamp(4px,.5vw,6px); --sp-sm:clamp(8px,1vw,12px);
  --sp-md:clamp(12px,1.5vw,18px); --sp-lg:clamp(18px,2.3vw,28px);
  --sp-xl:clamp(28px,4vw,52px);
}
html{scroll-behavior:smooth}
body{font-family:var(--sans); font-weight:300; color:var(--ink); background:var(--paper);
  line-height:1.5; letter-spacing:0; -webkit-font-smoothing:antialiased;
  text-rendering:optimizeLegibility; font-feature-settings:"kern" 1,"liga" 1;
  padding-bottom:76px; overscroll-behavior-y:none}
a{color:inherit; text-decoration:none}
.mono{font-family:var(--mono)}
.wrap{max-width:1160px; margin:0 auto; padding-inline:var(--sp-xl)}
.lc{text-transform:lowercase}

/* 顶部铭牌导航 */
.nav{position:sticky; top:0; z-index:1000; background:var(--ink); color:var(--white);
  border-bottom:1px solid var(--g1000)}
.nav .wrap{height:clamp(52px,7vw,66px); display:flex; align-items:center; justify-content:space-between}
.brand{display:flex; align-items:center; gap:10px; font-size:var(--fs-20); font-weight:100; letter-spacing:.01em}
.brand .sq{width:14px; height:14px; background:var(--orange)}
.nav .serial{font-family:var(--mono); font-size:var(--fs-10); color:var(--g300); text-transform:uppercase;
  display:flex; gap:16px; flex-wrap:wrap; justify-content:flex-end}
.nav .serial b{color:var(--white); font-weight:400}

/* Hero */
.hero{padding:var(--sp-xl) 0 var(--sp-lg); display:flex; align-items:flex-end;
  justify-content:space-between; gap:var(--sp-lg); flex-wrap:wrap}
.hero .h-l h1{font-size:var(--fs-40); font-weight:100; line-height:1.02; letter-spacing:-.01em}
.hero .h-l .en{font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase;
  color:var(--g600); margin-top:10px; letter-spacing:.06em}
.hero .h-r{text-align:right; font-family:var(--mono); font-size:var(--fs-10); color:var(--g600);
  text-transform:uppercase; line-height:1.7}
.hero .h-r .big{display:block; font-size:var(--fs-40); font-weight:100; color:var(--ink);
  font-family:var(--sans); line-height:.9; letter-spacing:-.02em}

/* LCD 屏幕模块 */
.lcd{background:#08110c; border:1px solid var(--g1000); color:var(--green);
  font-family:var(--mono); font-size:var(--fs-15); overflow:hidden; position:relative; margin-bottom:var(--sp-md)}
.lcd .row1{display:flex; align-items:center; gap:10px; padding:9px 16px; min-height:46px; border-bottom:1px solid #12241a}
.lcd .dot{width:8px; height:8px; border-radius:50%; background:var(--green); flex:none;
  box-shadow:0 0 8px var(--green); animation:blink 1.3s steps(1) infinite}
.lcd #boot{white-space:pre; overflow:hidden; flex:1; min-width:0; text-overflow:ellipsis}
.lcd #boot .cur{animation:blink .8s steps(1) infinite}
.lcd .cat-wrap{position:relative; width:58px; height:34px; flex:none; margin-left:auto; align-self:center;
  transform-origin:bottom center; animation:cat-breathe 2.8s ease-in-out infinite}
.lcd .cat{position:absolute; right:2px; bottom:1px; width:30px; height:30px; display:block;
  image-rendering:pixelated; transform-origin:bottom center; animation:cat-act 22s ease-in-out infinite}
.lcd .cat rect{fill:#8be0aa}
.lcd .cat .cat-eyes rect{fill:#06231a}
.lcd .cat .glint{fill:#eafff2}
.lcd .cat .nose{fill:#f0a24a}
.lcd .cat .blush{fill:#f05a24; opacity:.65}
.lcd .cat .cat-eyes{transform-box:fill-box; transform-origin:center; animation:cat-blink 3.4s infinite}
.lcd .cat .cat-tail{transform-box:fill-box; transform-origin:0% 100%;
  animation:cat-wag .9s ease-in-out infinite alternate}
.lcd .prop{position:absolute; bottom:1px; image-rendering:pixelated; opacity:0}
.lcd .prop.bowl{left:12px; width:15px} .lcd .prop.bowl svg{display:block; width:15px}
.lcd .prop.ball{left:5px; width:9px} .lcd .prop.ball svg{display:block; width:9px}
.lcd .prop.bowl{animation:prop-bowl 22s ease-in-out infinite}
.lcd .prop.ball{animation:prop-ball 22s ease-in-out infinite}
.lcd .prop.bowl rect{fill:#6fbf90} .lcd .prop.bowl .food{fill:#f0a24a}
.lcd .prop.ball rect{fill:#f05a24} .lcd .prop.ball .hl{fill:#ffd7bf}
@keyframes cat-breathe{50%{transform:scaleY(1.04)}}
@keyframes cat-blink{0%,90%,100%{transform:scaleY(1)}95%{transform:scaleY(.1)}}
@keyframes cat-wag{from{transform:rotate(-20deg)}to{transform:rotate(16deg)}}
/* 行为循环：静(归位,含小动作)→吃饭→静→伸懒腰→静→玩球→静，灵动不死板 */
@keyframes cat-act{
  0%,4%{transform:rotate(0)}
  8%{transform:rotate(-7deg)}
  13%{transform:rotate(2deg)}
  18%{transform:rotate(0)}
  27%{transform:rotate(7deg) translate(-3px,2px)}
  30%{transform:rotate(7deg) translate(-3px,0)}
  33%{transform:rotate(7deg) translate(-3px,2px)}
  36%{transform:rotate(7deg) translate(-3px,0)}
  40%{transform:rotate(0) translate(0,0)}
  47%{transform:rotate(5deg)}
  52%{transform:rotate(0)}
  61%{transform:scaleX(1.3) translateX(-4px)}
  66%{transform:scaleX(1.3) translateX(-4px)}
  70%{transform:scaleX(1) translateX(0)}
  74%{transform:translateY(-2px)}
  78%{transform:translateY(0)}
  84%{transform:translate(-6px,1px) rotate(6deg)}
  87%{transform:translate(0,0) rotate(0)}
  91%{transform:translate(-6px,1px) rotate(6deg)}
  94%{transform:translate(0,0) rotate(0)}
  100%{transform:rotate(0)}
}
@keyframes prop-bowl{0%,23%{opacity:0}26%,39%{opacity:1}41%,100%{opacity:0}}
@keyframes prop-ball{0%,80%{opacity:0;transform:translateY(0)}82%{opacity:1;transform:translateY(0)}
  85%{opacity:1;transform:translateY(-9px)}88%{opacity:1;transform:translateY(0)}
  91%{opacity:1;transform:translateY(-6px)}94%{opacity:1;transform:translateY(0)}96%,100%{opacity:0}}
.lcd .ticker{padding:8px 0; position:relative; -webkit-mask-image:linear-gradient(90deg,transparent,#000 4%,#000 96%,transparent);
  mask-image:linear-gradient(90deg,transparent,#000 4%,#000 96%,transparent)}
.lcd .track{display:inline-block; white-space:nowrap; padding-left:100%; color:#3fae6f;
  animation:marquee 26s linear infinite}
.lcd:hover .track{animation-play-state:paused}
.lcd .track b{color:var(--green); font-weight:700}
.lcd .track i{color:#1f6b42; font-style:normal; margin:0 14px}
@keyframes blink{50%{opacity:.2}}
@keyframes marquee{to{transform:translateX(-50%)}}

/* 规格条 */
.spec{border:1px solid var(--g300); border-bottom:none; font-family:var(--mono);
  font-size:var(--fs-10); text-transform:uppercase; color:var(--g600);
  display:grid; grid-template-columns:repeat(4,1fr)}
.spec div{padding:9px 14px; border-right:1px solid var(--g100)}
.spec div:last-child{border-right:none}
.spec b{color:var(--ink); font-weight:700}

/* 分区标题 */
.sect{font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase; letter-spacing:.14em;
  color:var(--ink); margin:var(--sp-lg) 0 var(--sp-sm); display:flex; align-items:center; gap:12px}
.sect::after{content:""; flex:1; height:1px; background:var(--ink)}

/* 工程方格纸模块网格 */
.grid{display:grid; grid-template-columns:repeat(2,1fr);
  border-top:1px solid var(--g300); border-left:1px solid var(--g300)}
.mod{border-right:1px solid var(--g300); border-bottom:1px solid var(--g300);
  background:var(--paper); display:flex; flex-direction:column; position:relative;
  opacity:0; transform:translateY(8px); transition:opacity .4s ease-out, transform .4s ease-out}
.mod.in{opacity:1; transform:none}
.mod.fill{background:
  repeating-linear-gradient(0deg,transparent,transparent 21px,var(--g100) 21px,var(--g100) 22px),
  repeating-linear-gradient(90deg,transparent,transparent 21px,var(--g100) 21px,var(--g100) 22px)}
.m-top{display:flex; align-items:center; justify-content:space-between; padding:10px 14px;
  border-bottom:1px solid var(--g100)}
.m-num{font-family:var(--mono); font-size:var(--fs-25); font-weight:400; line-height:1; letter-spacing:-.02em}
.m-code{display:inline-flex; align-items:center; gap:6px; font-family:var(--mono); font-size:var(--fs-10);
  text-transform:uppercase; color:var(--white); padding:3px 8px}
.m-main{display:flex; gap:var(--sp-md); padding:var(--sp-md) var(--sp-md) 0}
.art{position:relative; width:clamp(84px,9vw,104px); aspect-ratio:1; flex:none}
.cover{width:100%; height:100%; object-fit:cover; display:block; background:var(--g100);
  border:1px solid var(--g100); transition:opacity .2s}
.cover.ph{display:grid; place-items:center; font-family:var(--mono); font-size:var(--fs-30);
  color:var(--white); background:var(--ink); border:none}
.art:hover .cover{opacity:.82}
.hd{flex:1; min-width:0}
.title{font-size:var(--fs-25); font-weight:100; line-height:1.12; letter-spacing:-.01em}
.artist{font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase; color:var(--g900);
  margin-top:5px; letter-spacing:.03em}
.meta{font-family:var(--mono); font-size:var(--fs-10); color:var(--g600); margin-top:7px; line-height:1.6}
.tags{display:flex; flex-wrap:wrap; gap:5px; margin-top:8px}
.tag{font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase; padding:2px 7px;
  background:var(--g100); color:var(--g900)}
.body{padding:var(--sp-md); display:flex; flex-direction:column; flex:1}
.one{font-family:var(--mono); font-size:var(--fs-10); color:var(--g600); line-height:1.65; margin-bottom:7px}
.why{font-size:var(--fs-15); font-weight:300; line-height:1.55}
.scene{font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase; color:var(--g900);
  margin-top:auto; padding-top:11px}
.scene .k{color:var(--orange)}
.links{display:flex; gap:8px; margin-top:11px}
.btn{font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase; padding:8px 12px;
  cursor:pointer; transition:opacity .2s; border:1px solid var(--ink)}
.btn.solid{background:var(--ink); color:var(--white)}
.btn.line{background:transparent; color:var(--ink)}
.btn:hover{opacity:.7}
.src{font-family:var(--mono); font-size:var(--fs-10); color:var(--g500); margin-top:10px; letter-spacing:.02em}
.src a{border-bottom:1px solid var(--g300)}

/* 导出面板 */
.export{border:1px solid var(--g300); margin-top:var(--sp-lg); background:var(--white)}
.export .h{display:flex; justify-content:space-between; align-items:center; padding:12px 16px;
  border-bottom:1px solid var(--g100); font-family:var(--mono); font-size:var(--fs-10);
  text-transform:uppercase; letter-spacing:.04em}
.export .h span{color:var(--g600)}
.export .in{padding:var(--sp-md)}
.export p{font-family:var(--mono); font-size:var(--fs-10); color:var(--g600); margin-bottom:10px; text-transform:none}
.export pre{border:1px solid var(--g100); background:var(--paper); padding:14px; font-family:var(--mono);
  font-size:var(--fs-10); line-height:1.8; white-space:pre-wrap; max-height:280px; overflow:auto}

footer{display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px; margin-top:var(--sp-lg);
  padding:var(--sp-lg) 0; font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase;
  color:var(--g600); border-top:1px solid var(--g300)}

@media(max-width:720px){
  .grid{grid-template-columns:1fr}
  .hero{align-items:flex-start}
  .m-main{flex-direction:row}
}
@media(prefers-reduced-motion:reduce){
  .mod{opacity:1; transform:none; transition:none}
  .track,.dot,.rec,.cat,.cat-wrap,.cat-eyes,.cat-tail,.prop{animation:none}
  html{scroll-behavior:auto}
}
"""

JS = """
// LCD boot 打字机
const boot=document.getElementById('boot'), BOOT=boot?boot.dataset.text:'';
if(boot){let i=0;boot.textContent='';(function type(){if(i<=BOOT.length){boot.innerHTML=BOOT.slice(0,i)+'<span class="cur">▋</span>';i++;setTimeout(type,26);}else{boot.textContent=BOOT;}})();}

// 卡片分级进场
const io=new IntersectionObserver((es)=>{es.forEach((e,k)=>{if(e.isIntersecting){const el=e.target;
  setTimeout(()=>el.classList.add('in'),(el.dataset.d||0)*1);io.unobserve(el);}});},{threshold:.12});
document.querySelectorAll('.mod').forEach((m,k)=>{m.dataset.d=(k%6)*70;io.observe(m);});

function copyNC(){const t=document.getElementById('nc-text').innerText;
  navigator.clipboard.writeText(t).then(()=>{const b=document.getElementById('nc-btn'),o=b.innerText;
    b.innerText='copied ✓';setTimeout(()=>b.innerText=o,1600);});}
"""


def _esc(s) -> str:
    return html.escape(str(s or ""))


def _ncsearch(track: dict) -> str:
    q = urllib.parse.quote(f"{track['title']} {track['artist']}")
    return f"https://music.163.com/#/search/m/?s={q}"


def _art(track: dict) -> str:
    art = track.get("_cover") or track.get("artwork") or ""
    if art:
        cover = f'<img class="cover" src="{_esc(art)}" alt="" loading="lazy">'
    else:
        cover = f'<div class="cover ph">{_esc((track.get("artist") or "?")[:1].upper())}</div>'
    return f'<div class="art">{cover}</div>'


def _mod(track: dict, idx: int) -> str:
    g0 = (track.get("genres") or ["—"])[0]
    tags = "".join(f'<span class="tag">{_esc(g)}</span>' for g in (track.get("genres") or [])[1:3])
    tags += "".join(f'<span class="tag">{_esc(m)}</span>' for m in (track.get("mood_tags") or [])[:2])
    links = []
    if track.get("_apple"):
        links.append(f'<a class="btn solid" href="{_esc(track["_apple"])}" target="_blank" rel="noopener">listen ↗</a>')
    links.append(f'<a class="btn line" href="{_ncsearch(track)}" target="_blank" rel="noopener">netease ↗</a>')
    src = ""
    if track.get("source"):
        s = _esc(track["source"])
        src = (f'<a href="{_esc(track["source_url"])}" target="_blank" rel="noopener">{s}</a>'
               if track.get("source_url") else s)
    meta = " / ".join(x for x in [_esc(track.get("year", "")), _esc(track.get("album", ""))] if x)
    return f"""
    <article class="mod">
      <div class="m-top">
        <span class="m-num">{idx:02d}</span>
        <span class="m-code" style="background:{_knob(g0)}">{_esc(g0)}</span>
      </div>
      <div class="m-main">
        {_art(track)}
        <div class="hd">
          <div class="title lc">{_esc(track['title'])}</div>
          <div class="artist">{_esc(track['artist'])}</div>
          <div class="meta">{meta}</div>
          <div class="tags">{tags}</div>
        </div>
      </div>
      <div class="body">
        <div class="one">{_esc(track.get('artist_oneliner',''))}</div>
        <div class="why">{_esc(track.get('why',''))}</div>
        <div class="scene"><span class="k">use ▸</span> {_esc(track.get('scene',''))}</div>
        <div class="links">{''.join(links)}</div>
        <div class="src">src · {src}</div>
      </div>
    </article>"""


def build_html(date_str: str, tracks: list[dict], issue_no: int, netease_text: str) -> str:
    mods = "\n".join(_mod(t, i) for i, t in enumerate(tracks, 1))
    if len(tracks) % 2 == 1:  # 补一格方格纸填充，让网格成完整矩形
        mods += '\n<div class="mod fill"></div>'
    nc = _esc(netease_text)
    js = JS
    n = len(tracks)
    ymd = date_str.replace("-", ".")
    genres = sorted({(t.get("genres") or ["—"])[0] for t in tracks})
    genre_line = " · ".join(_esc(g).lower() for g in genres[:6])
    ticker = "".join(
        f'<b>{i:02d}</b> {_esc(t["title"])} <i>—</i> {_esc(t["artist"])}<i>·</i>'
        for i, t in enumerate(tracks, 1)
    )
    boot = f"system ready — {n} tracks loaded · melody-first · mood-first · production-first"
    favicon = "data:image/svg+xml," + urllib.parse.quote(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<rect width="24" height="24" fill="#f05a24"/>'
        '<rect x="5" y="5" width="14" height="14" fill="none" stroke="#0f0e12" stroke-width="2"/></svg>'
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0f0e12">
<meta name="description" content="每日精选 30 首 · melody-first · mood-first · production-first">
<title>music daily · md-{n:02d} · {_esc(date_str)}</title>
<link rel="icon" href="{favicon}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@100;300;400&family=Space+Mono:wght@400;700&family=Noto+Sans+SC:wght@100;300;400&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<nav class="nav">
  <div class="wrap">
    <div class="brand lc"><span class="sq"></span>music daily</div>
    <div class="serial"><span>model <b>md-{n:02d}</b></span><span>issue <b>{issue_no:03d}</b></span><span>date <b>{ymd}</b></span></div>
  </div>
</nav>

<main class="wrap">
  <div class="hero">
    <div class="h-l">
      <h1 class="lc">今日精选</h1>
      <div class="en">today's selection · daily music report</div>
    </div>
    <div class="h-r"><span class="big">{n:02d}</span>tracks / daily<br>{ymd}</div>
  </div>

  <div class="lcd">
    <div class="row1"><span class="dot"></span><span id="boot" data-text="{_esc(boot)}"></span><div class="cat-wrap">{ICON_CAT}<span class="prop bowl">{ICON_BOWL}</span><span class="prop ball">{ICON_BALL}</span></div></div>
    <div class="ticker"><span class="track">{ticker}{ticker}</span></div>
  </div>

  <div class="spec">
    <div>sort <b>melody-first</b></div><div>bpm <b>70–120</b></div>
    <div>tracks <b>{n:02d}</b></div><div>genres <b>{genre_line or '—'}</b></div>
  </div>

  <div class="sect">tracklist</div>
  <div class="grid">
    {mods}
  </div>

  <section class="export">
    <div class="h">data export · 网易云导入 <span>format: title - artist</span></div>
    <div class="in">
      <p>复制下列清单 → 网易云 App「新建歌单 → 导入」，第一行会作为歌单名自动创建。</p>
      <pre id="nc-text">{nc}</pre>
      <button class="btn solid" id="nc-btn" onclick="copyNC()" style="margin-top:12px">复制歌单 / copy</button>
    </div>
  </section>

  <footer>
    <span>music daily · md-{n:02d} · issue {issue_no:03d}</span>
    <span>updated 08:00 cst</span>
    <span>cover via public music api · personal use</span>
  </footer>
</main>

<script>{js}</script>
</body>
</html>"""
