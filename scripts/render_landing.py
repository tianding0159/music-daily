"""音乐日报首页：清晰入口、可直接访问的导航与保留原几何的黑胶唱机。

所有浏览入口都是原生链接，脚本只负责可选的访客计数。
唱盘几何来自随机页，首页仅调整展示尺寸、控制条和静止唱臂。
"""
from __future__ import annotations

import datetime as dt
import re

from render_grid import CSS as GRID_CSS
from render_grid import ICON_CAT_SIT, SITE_URL, _esc
from render_random import EXTRA_CSS as RANDOM_CSS
from ui_common import site_nav

COUNTER_NS = "tianding0159-music-daily"
COUNTER_KEY = "landing"


def _vinyl_label(n_issues: int, latest_date: str) -> str:
    """传统黑胶纸标签排版：上弧走站名、中间横排期号、下弧走转速。

    真黑胶的标签字是围着中心绕的（上下半圈都正读），CSS 做不到，
    用两条 SVG 弧线 + textPath。viewBox 100×100，圆心 (50,50)。
    """
    md = latest_date.replace("-", ".") if latest_date else ""
    return (
        '<svg viewBox="0 0 100 100" aria-hidden="true">'
        '<path id="vt" fill="none" d="M18 50 A32 32 0 0 1 82 50"/>'      # 上弧
        '<path id="vb" fill="none" d="M15 50 A35 35 0 0 0 85 50"/>'      # 下弧
        '<text class="arc"><textPath href="#vt" startOffset="50%" text-anchor="middle">'
        'MUSIC DAILY</textPath></text>'
        '<text class="mid" x="50" y="47" text-anchor="middle">MD-30</text>'
        f'<text class="sub" x="50" y="55.5" text-anchor="middle">ISSUE {n_issues:03d}</text>'
        f'<text class="sub" x="50" y="61.5" text-anchor="middle">{_esc(md)}</text>'
        '<text class="arc lo"><textPath href="#vb" startOffset="50%" text-anchor="middle">'
        '33\u2153 RPM \u00b7 LONG PLAYING</textPath></text>'
        '</svg>')


def _turntable_css() -> str:
    """从 render_random 的 EXTRA_CSS 里切出唱盘那一整块（单一来源，不复制）。

    切到唱臂之后（唱臂规则在 @keyframes disc-lit 后面，切早了会漏掉它）。
    落地页的唱盘是静态展示，所以只剥掉「揭晓」那套入场时序，几何与配色照搬——
    针尖落点 0.92r 是实测调准的，重画一次必然又偏。
    """
    start = RANDOM_CSS.index("/* ── 唱盘：先摆一个正方形")
    end = RANDOM_CSS.index("/* 落针冲击")          # 涟漪只在揭晓时用，落地页不要
    blk = RANDOM_CSS[start:end]

    # 只删 animation 这一条声明，不动同一规则里的其它属性（正则吃掉整条规则会连
    # transform-origin/几何一起丢，之前就把 .tt .arm 整条吃没了）
    def _strip_anim(css: str, *names: str) -> str:
        for nm in names:
            css = re.sub(r"\n?\s*animation:" + nm + r"[^;}]*;", "", css)
            css = re.sub(r"\n?\s*animation:" + nm + r"[^;}]*(?=\})", "", css)
        return css

    blk = _strip_anim(blk, "disc-place", "disc-up", "arm-down")
    blk = blk.replace("animation:led-on .34s steps(1) .2s infinite",
                      "animation:led-on .9s steps(1) infinite")
    return blk


LANDING_CSS = """
body{background:var(--paper);color:var(--ink);overflow-x:hidden}
.home-main{width:min(1240px,100%);margin:auto;padding:clamp(32px,6vw,84px)
  calc(clamp(20px,4vw,48px) + var(--sar,0px)) 32px
  calc(clamp(20px,4vw,48px) + var(--sal,0px))}
.home-stage{display:grid;grid-template-columns:1.05fr 1fr;gap:clamp(28px,5vw,80px);
  align-items:center;min-height:550px;position:relative}
.home-copy{position:relative;z-index:2;max-width:560px}
.home-kicker{display:flex;align-items:center;gap:10px;font-family:var(--mono);
  font-size:12px;letter-spacing:.12em;color:var(--g600);margin-bottom:25px}
.home-kicker::before{content:"";width:8px;height:8px;background:var(--orange);border-radius:50%}
.home-title{font-size:clamp(44px,5.5vw,76px);font-weight:400;line-height:1.16;
  letter-spacing:-.055em;margin:0 0 26px;text-transform:none}
.home-title span{color:var(--orange)}
.home-intro{font-size:clamp(15px,1.4vw,18px);line-height:1.95;color:var(--g900);
  max-width:29em;margin:0 0 30px}
.home-actions{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:28px}
.home-action{display:inline-flex;align-items:center;justify-content:center;gap:22px;
  min-height:50px;padding:12px 20px;border:1px solid var(--g300);border-radius:6px;
  color:var(--ink);font-size:15px;font-weight:400;text-decoration:none;
  transition:background .15s,border-color .15s,transform .15s}
.home-action.primary{background:var(--orange);border-color:var(--orange);color:#fff}
.home-action:hover{background:var(--white);border-color:var(--ink);transform:translateY(-1px)}
.home-action.primary:hover{background:#bd431e;border-color:#bd431e}
.home-action:focus-visible,.pw:focus-visible,.home-latest a:focus-visible{
  outline:3px solid var(--orange);outline-offset:5px}
.home-latest{font-size:12px;color:var(--g600);display:flex;flex-wrap:wrap;gap:8px 16px;line-height:1.8}
.home-latest a{color:var(--ink);text-underline-offset:4px;text-decoration:underline}
.home-latest time{font-variant-numeric:tabular-nums}
.home-art{position:relative;display:flex;flex-direction:column;align-items:center;
  min-width:0;padding:24px 0 20px;isolation:isolate}
.home-art::before{content:"";position:absolute;inset:0 -18px 8px;z-index:-1;
  background:radial-gradient(ellipse at 50% 42%,rgba(199,171,128,.19),transparent 70%)}
/* Keep the random-page deck geometry; its container query must not size itself. */
.deckbox.tt{container-type:normal;position:relative;inset:auto;display:block;
  width:min(420px,100%);padding-bottom:64px;background:var(--ink);overflow:visible;
  border:1px solid #34312d;border-radius:10px;
  box-shadow:0 28px 56px -27px rgba(37,29,18,.55);animation:none}
.deckbox.tt .deck{width:100%;height:auto;aspect-ratio:1;max-height:none;margin:0 auto;
  border-radius:9px 9px 0 0}
.deckbox.tt::after{content:none}
.deckbox .disc{animation:home-spin 18s linear infinite}
@keyframes home-spin{to{transform:rotate(360deg)}}
.deckbox .disc .vlbl{display:none}
.deckbox .disc>.lbl{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);
  width:37%;aspect-ratio:1;border-radius:50%;z-index:3;pointer-events:none;
  background:radial-gradient(circle at 50% 42%,#fbf7ec 0 62%,#f0e8d6 100%);
  box-shadow:0 0 0 1px rgba(0,0,0,.16),inset 0 0 12px rgba(120,100,60,.14)}
.deckbox .disc>.lbl svg{position:absolute;inset:0;width:100%;height:100%;shape-rendering:geometricPrecision}
.deckbox .disc>.lbl text{font-family:var(--mono);fill:#2a2318;text-rendering:geometricPrecision}
.deckbox .disc>.lbl .arc{font-size:4.6px;letter-spacing:.62px}
.deckbox .disc>.lbl .arc.lo{font-size:3.5px;letter-spacing:.5px;fill:#6b5f47}
.deckbox .disc>.lbl .mid{font-size:5.6px;letter-spacing:.5px;font-weight:700}
.deckbox .disc>.lbl .sub{font-size:3.4px;letter-spacing:.7px;fill:#6b5f47}
.deckbox .disc>.lbl::after{content:"";position:absolute;left:50%;top:50%;width:7%;aspect-ratio:1;
  transform:translate(-50%,-50%);border-radius:50%;background:#151515;box-shadow:inset 0 0 0 1px rgba(0,0,0,.5)}
.deckbox .arm{transform:rotate(80deg);animation:none}
.ctlbar{position:absolute;left:0;right:0;bottom:0;height:64px;z-index:6;
  display:flex;align-items:center;gap:14px;padding:0 20px;border-top:1px solid rgba(255,255,255,.09)}
.ctlbar .rpm{margin-left:auto;font-family:var(--mono);font-size:10px;color:#bdb4a8}
.deckbox .ctlbar .led{position:static;flex:none;margin:0}
.pw{display:inline-flex;align-items:center;gap:12px;min-height:44px;padding:4px;
  color:#f4efe6;font-size:13px;font-weight:400;line-height:1.2;text-decoration:none}
.pw:hover{color:#fff}
.pw .knob{width:22px;height:22px;border-radius:50%;flex:none;position:relative;
  background:#211e19;box-shadow:inset 0 0 0 1px rgba(255,255,255,.22)}
.pw .knob::after{content:"";position:absolute;inset:7px;border-radius:50%;background:var(--orange)}
.home-caption{display:flex;align-items:center;gap:16px;width:min(420px,100%);padding-top:24px;
  color:var(--g600);font-size:12px;line-height:1.8}
.home-caption strong{display:block;color:var(--ink);font-weight:400;letter-spacing:.05em}
.home-cat{flex:none;width:48px;height:46px;transform:rotate(-5deg)}
.home-cat .cat{display:block;width:48px;height:46px;image-rendering:pixelated}
.home-cat .fur rect{fill:#fefaf1;stroke:#c0ad93;stroke-width:.3}
.home-cat .fur2 rect{fill:var(--orange)}
.home-cat .cat-eyes rect,.home-cat .mouth{fill:var(--ink)}
.home-cat .pad rect,.home-cat .blush{fill:#db9176}
.home-bottom{display:flex;justify-content:space-between;align-items:center;gap:20px;
  border-top:1px solid var(--g200);padding-top:26px;margin-top:46px}
.home-bottom p{color:var(--g900);font-size:13px;line-height:1.8}
.home-bottom strong{font-weight:400;color:var(--ink);font-variant-numeric:tabular-nums}
.home-footer{display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px;
  padding-top:28px;padding-bottom:calc(12px + var(--sab,0px));color:var(--g600);font-size:10px}
@media(max-width:800px){
  .home-main{padding-top:36px}
  .home-stage{grid-template-columns:1fr;gap:20px;min-height:0}
  .home-copy{max-width:600px}
  .home-kicker{margin-bottom:18px}
  .home-title{font-size:clamp(43px,8vw,64px);margin-bottom:20px}
  .home-intro{max-width:36em;margin-bottom:24px}
  .home-art{padding:26px 18px 10px}
  .deckbox.tt{width:min(370px,100%)}
  .home-caption{width:min(370px,100%)}
  .home-bottom{margin-top:24px;align-items:flex-start;flex-direction:column;gap:10px}
}
@media(max-width:400px){
  .home-main{padding-left:calc(18px + var(--sal,0px));padding-right:calc(18px + var(--sar,0px))}
  .home-actions{gap:10px}
  .home-action{padding:12px 16px;gap:12px;flex:1}
  .home-art{padding-left:4px;padding-right:4px}
}
@media(prefers-reduced-motion:reduce){
  .deckbox .disc,.deckbox .led,.deckbox .arm{animation:none!important}
  .home-action{transition:none}
  .home-action:hover{transform:none}
}
"""

LANDING_JS = """
(function(){
  // Optional visitor counter. Navigation is native and remains usable without JS.
  var slot = document.getElementById('vis');
  if(!slot) return;
  fetch(HITURL, {cache:'no-store'})
    .then(function(r){ return r.ok ? r.json() : null; })
    .then(function(d){
      var n = d && (d.value != null ? d.value : d.count);
      if(typeof n === 'number' && Number.isFinite(n) && n >= 0){
        slot.textContent = n.toLocaleString('zh-CN');
      }
    })
    .catch(function(){});
})();
"""


def build_html(n_issues: int, n_tracks: int, latest_date: str) -> str:
    """落地页。曾有 n_moods 与 playlist_title 两个形参，函数体从未读过。

    删它们要同改 build_daily 的调用（那里是关键字传参，漏改是 unexpected keyword），
    并删掉 build_daily 里只为算 n_moods 而存在的函数内 import mood_vocab。
    """
    hit = f"https://abacus.jasoncameron.dev/hit/{COUNTER_NS}/{COUNTER_KEY}"
    year = dt.datetime.now(dt.timezone.utc).year
    md = latest_date.replace("-", ".") if latest_date else ""

    # 根 URL 是最常被分享的那个（daily.html 的 og:url 也指向它），
    # 之前这一页一个 OG 标签都没有 —— 分享出去抓不到卡片，是个空链接。
    # 这里的 OG 描述的是【整个站】，与日报每期各自的 OG 分工：
    # 分享根 URL = "这是个什么站"，分享某期 = "这期有哪些歌"。
    # n_tracks 是【曲池总量】（页面铭牌上标的就是 pool N），不是每期首数 ——
    # 写成"每天 1169 首"是个一眼假的数字，而 OG 描述恰恰发到站外、
    # 没有上下文兜底。每期首数不在本函数入参里，就不硬凑。
    og_desc = (f"melody-first · mood-first · production-first。"
               f"曲池 {n_tracks} 首，已出 {n_issues} 期，最新 {md}。" if n_issues else
               "每天一批歌，melody-first · mood-first · production-first。")
    og_img = SITE_URL + "icon-512.png"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>MUSIC DAILY</title>
<meta name="description" content="每日精选 30 首 · melody-first · mood-first · production-first">
<meta name="theme-color" content="#f6f2e9">
<meta property="og:type" content="website">
<meta property="og:site_name" content="MUSIC DAILY">
<meta property="og:title" content="MUSIC DAILY · 每日精选">
<meta property="og:description" content="{_esc(og_desc)}">
<meta property="og:url" content="{SITE_URL}">
<meta property="og:image" content="{og_img}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="MUSIC DAILY · 每日精选">
<meta name="twitter:description" content="{_esc(og_desc)}">
<meta name="twitter:image" content="{og_img}">
<link rel="prefetch" href="daily.html">
<!-- PWA 的 start_url；所有浏览入口不依赖脚本或动画。 -->
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icon-180.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="MD-30">
<!-- 字体必须在这里引 —— GRID_CSS 里只是【声明】 --sans:"Inter" / --mono:"Space Mono"，
     声明不等于加载。2026-08-03 之前本页漏了这三行，变量与日报完全一致却回退到
     Helvetica/Arial 渲染，看起来就是「开启页字体和日报不一致」。
     引法与 render_grid.py / render_random.py 保持逐字相同。 -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@100;300;400&family=Space+Mono:wght@400;700&family=Noto+Sans+SC:wght@100;300;400&display=swap" rel="stylesheet">
<style>{GRID_CSS}{_turntable_css()}{LANDING_CSS}</style>
</head>
<body class="home-page">
{site_nav(active='home', prefix='')}
<main class="home-main" id="main">
  <section class="home-stage" aria-labelledby="home-title">
    <div class="home-copy">
      <div class="home-kicker">A DAILY LISTENING JOURNAL</div>
      <h1 class="home-title" id="home-title">今天，<br>听点<span>好的。</span></h1>
      <p class="home-intro">每天精选 30 首，从旋律、制作和气质出发。<br>先听今天，也可以去曲库遇见下一首。</p>
      <div class="home-actions">
        <a class="home-action primary" href="daily.html">今日精选 <span aria-hidden="true">↗</span></a>
        <a class="home-action" href="random.html">听点别的 <span aria-hidden="true">↗</span></a>
      </div>
      <div class="home-latest">
        <span>最新一期 <time datetime="{_esc(latest_date)}">{_esc(md) or '即将更新'}</time> · 第 {n_issues:03d} 期</span>
        <a href="archive/index.html">翻翻往期 →</a>
      </div>
    </div>
    <div class="home-art">
      <div class="deckbox tt">
        <div class="deck" aria-hidden="true">
          <div class="dwrap"><div class="disc">
            <span class="lbl">{_vinyl_label(n_issues, latest_date)}</span>
          </div></div>
          <div class="arm"><i></i><b></b></div>
        </div>
        <div class="ctlbar">
          <a class="pw" id="pw" href="daily.html" aria-label="打开今日精选">
            <span class="knob" aria-hidden="true"></span><span>开始听今天</span></a>
          <span class="rpm">33⅓ RPM</span>
          <span class="led" aria-hidden="true"></span>
        </div>
      </div>
      <div class="home-caption">
        <span class="home-cat" aria-hidden="true">{ICON_CAT_SIT}</span>
        <span><strong>MELODY, MOOD &amp; A LITTLE CURIOSITY.</strong>给耳朵一点自由时间。</span>
      </div>
    </div>
  </section>
  <div class="home-bottom">
    <p><strong>{n_tracks:,}</strong> 首曲库 · <strong>{n_issues}</strong> 期音乐日记</p>
    <p>每天北京时间约 <strong>08:11</strong> 更新 · 试听片段，收藏喜欢的歌</p>
  </div>
  <div class="home-footer">
    <span>© {year} MUSIC DAILY · 封面与试听来自公开音乐接口</span>
    <span>来访 <span id="vis">—</span></span>
  </div>
</main>
<script>const HITURL={hit!r};{LANDING_JS}</script>
</body>
</html>"""
