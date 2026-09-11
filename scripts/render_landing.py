"""站点入口：黑胶上机落地页（site/index.html）。

日报本体在 daily.html，这里是访客先看到的一屏：
中央一张黑胶在唱盘上慢速自转，中心白标签印着 MUSIC DAILY 与期号。
唱臂停在盘外，start 是直接进入日报的原生链接。
保留唱盘的慢速自转，导航不等待动画。浅色纸底，排版与日报一致。

复用而非重画：
- 唱盘/唱片/唱臂的几何与配色全部来自 render_random 的 `.tt` 那套
  （针尖落点已经调到 0.92r，重画一次必然又偏），落地页给容器挂上
  `class="tt"` 直接继承整块作用域。
这条教训在 memory css-scope-and-layout-traps 里：作用域锁死的样式要
「补作用域类」而不是「复制一份」。

访客计数走 Abacus（jasoncameron.dev）：/hit 自增并返回。实测带
access-control-allow-origin:*，纯静态页可直接 fetch。放在唱盘下方的
铭牌行里（VISITORS 一格），拿不到就显示 "—"，绝不挡入场。
"""
from __future__ import annotations

import datetime as dt
import re

from render_grid import CSS as GRID_CSS
from render_grid import SITE_URL, _esc
from render_random import EXTRA_CSS as RANDOM_CSS

COUNTER_NS = "tianding0159-music-daily"
COUNTER_KEY = "landing"


def _vinyl_label(n_issues: int, latest_date: str) -> str:
    """传统黑胶纸标签排版：上弧走站名、中间横排期号、下弧走转速。

    真黑胶的标签字是围着中心绕的（上下半圈都正读），CSS 做不到，
    用两条 SVG 弧线 + textPath。viewBox 100×100，圆心 (50,50)。
    """
    md = _esc(latest_date.replace("-", ".")) if latest_date else ""
    return (
        '<svg viewBox="0 0 100 100" aria-hidden="true">'
        '<path id="vt" fill="none" d="M18 50 A32 32 0 0 1 82 50"/>'      # 上弧
        '<path id="vb" fill="none" d="M15 50 A35 35 0 0 0 85 50"/>'      # 下弧
        '<text class="arc"><textPath href="#vt" startOffset="50%" text-anchor="middle">'
        'MUSIC DAILY</textPath></text>'
        '<text class="mid" x="50" y="47" text-anchor="middle">MD-30</text>'
        f'<text class="sub" x="50" y="55.5" text-anchor="middle">ISSUE {n_issues:03d}</text>'
        f'<text class="sub" x="50" y="61.5" text-anchor="middle">{md}</text>'
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
html,body{min-height:100%}
/* 与日报 body 同一套排版（--sans / weight 300 / line-height 1.5 / 同 font-feature） */
body{background:var(--paper); color:var(--ink); overflow-x:hidden; overflow-y:auto; padding-bottom:0;
  font-family:var(--sans); font-weight:300; line-height:1.5; letter-spacing:0;
  -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility;
  font-feature-settings:"kern" 1,"liga" 1}
/* 落地页是整屏 flex 居中，没有 nav 兜底，四边都要自己吃 inset。
   实测这一页原本是安全的（唱机居中、离边很远），但铭牌行与 rail 在小屏 +
   横屏下会贴近边缘，且 100svh 在 standalone 下就是含安全区的全屏高度。 */
.stage{min-height:100vh; min-height:calc(100svh - 1px); display:flex; flex-direction:column;
  align-items:center; justify-content:center; gap:clamp(16px,3vh,30px);
  padding:calc(clamp(16px,4vw,38px) + var(--sat, 0px))
          calc(clamp(16px,4vw,38px) + var(--sar, 0px))
          calc(clamp(16px,4vw,38px) + var(--sab, 0px))
          calc(clamp(16px,4vw,38px) + var(--sal, 0px));
  position:relative; isolation:isolate}
/* 背景：极淡网格 + 一道缓慢扫过的绿光 */
.stage::before{content:""; position:absolute; inset:0; pointer-events:none; opacity:.45;
  background:
    linear-gradient(rgba(15,14,18,.042) 1px, transparent 1px) 0 0/100% 34px,
    linear-gradient(90deg, rgba(15,14,18,.042) 1px, transparent 1px) 0 0/34px 100%;
  mask-image:radial-gradient(ellipse 76% 60% at 50% 46%, #000 28%, transparent 100%)}
.stage::after{content:""; position:absolute; left:-30%; top:0; width:26%; height:100%;
  pointer-events:none; opacity:.45;
  background:linear-gradient(90deg, transparent, rgba(15,14,18,.05) 45%, transparent);
  animation:sweep 11s ease-in-out infinite}
@keyframes sweep{0%{transform:translateX(0)}100%{transform:translateX(560%)}}

/* 铭牌：与日报同一套字体（--sans + 极细）。TE 规范只用 100/300，从不 400/700。 */
.plate{display:flex; align-items:center; gap:10px; font-family:var(--sans);
  font-size:var(--fs-15); font-weight:300; letter-spacing:.02em; text-transform:lowercase;
  color:var(--g600); position:relative; z-index:2; animation:landing-in .22s ease-out both}
.plate .sq{width:10px; height:10px; background:var(--orange)}
.plate b{color:var(--ink); font-weight:300; letter-spacing:.02em}

/* ── 唱盘：容器挂 .tt 继承 render_random 那套几何 ── */
/* 底座：真唱机是「盘在上、控制条在下」，容器不再是正方——
   上半 1:1 转盘区，下方留一条 62px 控制条放 START 键、转速标记、电源灯。 */
.deckbox{position:relative; z-index:2; width:min(420px,78vw); max-width:100%; flex-shrink:0;
  animation:landing-in .22s cubic-bezier(.16,1,.3,1) both}
/* .deck 塌成 0×0 的真因（实测）：切片里的 @supports 块给 .tt .deck 设了
   height:min(100cqw,100cqh)，而落地页的 .deckbox 此刻高度由子元素决定 → 100cqh = 0
   → deck 高 0 → 容器还是 0，成了容器查询的循环依赖。
   这里用更高特异性覆盖掉它，改回「宽度撑满 + aspect-ratio 定高」。 */
.deckbox.tt{container-type:normal}
.deckbox.tt .deck{width:100%; height:auto; aspect-ratio:1; max-height:none; margin:0 auto}
/* 控制条：border-top 会参与 align-items:center 的居中计算，使内容整体下沉 1px；
   加之它贴在底座最下沿、上方无等量留白，视觉上更显低。用 padding-bottom 比
   padding-top 多 2px 把内容顶到光学中心（实测方式：量文字盒 cy 与条中线之差）。 */
.ctlbar{position:absolute; left:0; right:0; bottom:0; height:62px; z-index:6;
  box-sizing:border-box; display:flex; align-items:center; gap:14px;
  padding:0 20px 1px; border-top:1px solid rgba(255,255,255,.07)}
.ctlbar .rpm{margin-left:auto; font-family:var(--sans); font-size:10px; font-weight:300;
  letter-spacing:.02em; text-transform:lowercase; color:rgba(255,255,255,.34)}
/* 唱盘自带的转速标记与电源灯本来是绝对定位在盘面角上的，现在归到控制条 */
.deckbox.tt::after{content:none}
.deckbox .ctlbar .led{position:static; flex:none; margin:0}
.deckbox.tt{position:relative; inset:auto; display:block; padding-bottom:62px;
  background:var(--ink); overflow:visible; border:1px solid var(--g200); border-radius:2px;
  box-shadow:0 20px 46px -24px rgba(15,14,18,.5);
  animation:landing-in .22s cubic-bezier(.16,1,.3,1) both}
/* 唱片：保留待机时的慢速自转 */
.deckbox .disc{animation:spin 9s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
/* 唱片自带的沿弧转速字 .vlbl 与中心标签抢位，落地页隐掉 */
.deckbox .disc .vlbl{display:none}
/* 中心纸标签：按传统黑胶排版——上弧走艺名、中间横排、下弧走厂牌与转速。
   挂在【不自转】的 .dwrap 上：挂 .disc 会跟着转，转到下半圈字就是倒的。 */
.deckbox .disc>.lbl{position:absolute; left:50%; top:50%; transform:translate(-50%,-50%);
  width:37%; aspect-ratio:1; border-radius:50%; z-index:3; pointer-events:none;
  background:radial-gradient(circle at 50% 42%, #fbf7ec 0 62%, #f0e8d6 100%);
  box-shadow:0 0 0 1px rgba(0,0,0,.16), inset 0 0 12px rgba(120,100,60,.14)}
.deckbox .disc>.lbl svg{position:absolute; inset:0; width:100%; height:100%;
  shape-rendering:geometricPrecision}
.deckbox .disc>.lbl text{font-family:var(--mono); fill:#2a2318;
  text-rendering:geometricPrecision}
.deckbox .disc>.lbl .arc{font-size:4.6px; letter-spacing:.62px}
.deckbox .disc>.lbl .arc.lo{font-size:3.5px; letter-spacing:.5px; fill:#6b5f47}
.deckbox .disc>.lbl .mid{font-size:5.6px; letter-spacing:.5px; font-weight:700}
.deckbox .disc>.lbl .sub{font-size:3.4px; letter-spacing:.7px; fill:#6b5f47}
/* 主轴孔 */
.deckbox .disc>.lbl::after{content:""; position:absolute; left:50%; top:50%;
  width:7%; aspect-ratio:1; transform:translate(-50%,-50%); border-radius:50%;
  background:#151515; box-shadow:inset 0 0 0 1px rgba(0,0,0,.5)}
/* 唱臂：停机位 */
.deckbox .arm{transform:rotate(80deg)}
/* 铭牌行：期号 / 曲目数 / 访客数 —— 访客计数就在这儿 */
.rail{position:relative; z-index:2; display:flex; border:1px solid var(--g300);
  background:var(--white); font-family:var(--sans); font-size:var(--fs-10);
  font-weight:300; text-transform:lowercase; letter-spacing:.02em;
  animation:landing-in .22s ease-out both}
.rail div{padding:9px 15px; border-right:1px solid var(--g100); color:var(--g600);
  display:flex; align-items:baseline; gap:7px; white-space:nowrap}
.rail div:last-child{border-right:none}
.rail b{color:var(--ink); font-weight:300; letter-spacing:.02em}
.rail .vs b{color:var(--green-d)}

/* ── START 键：集成在唱盘底座的控制条上（真唱机就长这样）──
   TE 语言：一枚小圆钮 + 旁边刻字，极细小写，橙色只用在状态上。 */
.pw{appearance:none; border:none; background:none; cursor:pointer; padding:0; min-height:44px;
  text-decoration:none; touch-action:manipulation;
  display:inline-flex; align-items:center; gap:10px;
  font-family:var(--sans); font-size:var(--fs-15); font-weight:300;
  letter-spacing:normal; text-transform:lowercase; line-height:1.1;
  color:rgba(245,245,245,.7); transition:color .16s}
/* start 的字母主体比圆钮低 1.25px：小写词没有降部、x-height 堆在文字盒下半部，
   几何居中时视觉上就是偏低。按像素实测量出的差值上移。 */
.pw .t{position:relative; top:-1.62px}
.pw:hover{color:#f5f5f5}
.pw:focus-visible{outline:1px solid rgba(255,255,255,.5); outline-offset:5px}
/* 圆钮：待机是橙色描边空心，hover 半亮，按下实心并留一圈光 */
.pw .knob{width:22px; height:22px; border-radius:50%; flex:none; position:relative;
  background:#211e19; box-shadow:inset 0 0 0 1px rgba(255,255,255,.14),
    0 1px 2px rgba(0,0,0,.5); transition:box-shadow .16s, transform .1s}
.pw .knob::after{content:""; position:absolute; left:50%; top:50%; width:7px; height:7px;
  margin:-3.5px 0 0 -3.5px; border-radius:50%;
  box-shadow:inset 0 0 0 1.4px var(--orange); transition:background .16s, box-shadow .16s}
.pw:hover .knob::after{background:rgba(240,90,36,.45)}
.pw:active .knob{transform:translateY(1px)}
.pw:active .knob{box-shadow:inset 0 0 0 1px rgba(255,255,255,.2), 0 0 0 3px rgba(240,90,36,.18)}
.pw:active .knob::after{background:var(--orange)}
/* 原控制条刻度保留，点击反馈随按压即时完成。 */
.pw .trk{width:22px; height:1px; flex:none; background:rgba(245,245,245,.2);
  /* 轨对齐圆钮的几何中线（flex align-items:center 已保证），不再补偿——
     补偿量本是为了对齐旧的文字盒中线，文字上移后就不需要了 */
  position:relative; top:0}
.pw .trk::after{content:""; position:absolute; left:0; top:0; height:100%; width:0;
  background:var(--orange)}
.pw:active .trk::after{width:100%}

.tip{font-family:var(--sans); font-size:var(--fs-10); font-weight:300; color:var(--g600);
  letter-spacing:.02em; position:relative; z-index:2;
  display:flex; flex-wrap:wrap; justify-content:center; gap:4px 16px; margin:0;
  animation:landing-in .22s ease-out both}
.tip a{display:inline-flex; align-items:center; min-height:44px; color:var(--g600);
  text-decoration:none; border-bottom:1px solid transparent; transition:color .15s,border-color .15s}
.tip a:hover{color:var(--ink); border-bottom-color:var(--orange)}
.tip a:focus-visible{outline:2px solid var(--orange); outline-offset:3px}
.foot{position:relative; margin-top:2px; text-align:center;
  font-family:var(--sans); font-size:9px; font-weight:300; letter-spacing:.02em;
  text-transform:lowercase; color:var(--g600); z-index:2; max-width:100%; text-wrap:balance}
/* 第一帧就可见，轻微位移只作点缀，不等 stagger 才显示入口。 */
@keyframes landing-in{from{opacity:.96; transform:translateY(3px)}to{opacity:1; transform:none}}

@media(max-width:520px){
  /* 覆盖 padding 时必须把 inset 一起带上 —— 简写 padding 会整条替换掉
     上面那四行 calc()，窄屏（也就是手机，最需要安全区的那批设备）反而丢掉保护。 */
  .stage{gap:16px;
    padding:calc(18px + var(--sat, 0px)) calc(14px + var(--sar, 0px))
            calc(18px + var(--sab, 0px)) calc(14px + var(--sal, 0px))}
  .deckbox{width:min(320px,84vw)}
  .rail{font-size:9px; display:grid; grid-template-columns:repeat(4,auto); max-width:100%}
  .rail div{padding:7px 8px; gap:5px}
  .pw{font-size:14px; padding:0; letter-spacing:normal}
  .tip{font-size:11px; text-align:center; line-height:1.5; gap:4px 18px}
}
@media(max-height:640px){
  .stage{gap:10px}
  .deckbox{width:min(290px,76vw)}
}
@media(max-width:350px){
  .rail{grid-template-columns:repeat(2,auto)}
  .rail div:nth-child(2){border-right:none}
  .rail div:nth-child(-n+2){border-bottom:1px solid var(--g100)}
}
@media(prefers-reduced-motion:reduce){
  .stage::after,.deckbox .disc{animation:none}
  .plate,.deckbox.tt,.rail,.pw,.tip,.foot,.deckbox .ctlbar .led{animation:none; opacity:1}
  .pw{box-shadow:none}
}
"""

LANDING_JS = """
(function(){
  // 访客计数：Abacus /hit 自增并返回。第三方挂了就留 "—"，绝不挡入场。
  var slot = document.getElementById('vis');
  if(slot){
    fetch(HITURL, {cache:'no-store'})
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(d){
        var n = d && (d.value != null ? d.value : d.count);
        if(n != null) slot.textContent = String(n).padStart(5,'0');
      })
      .catch(function(){});
  }

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
<meta name="theme-color" content="#f5f5f5">
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
<link rel="preload" href="daily.html" as="document">
<!-- PWA。本页是 manifest 的 start_url —— 从主屏图标点进来先看到这一屏，
     再落针进日报，跟真开唱机的顺序一致。 -->
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
<body>
<main class="stage">
  <div class="plate"><span class="sq"></span><b>music daily</b> · md-30</div>

  <div class="deckbox tt">
    <div class="deck">
      <div class="dwrap"><div class="disc">
        <span class="lbl">{_vinyl_label(n_issues, latest_date)}</span>
      </div></div>
      <div class="arm"><i></i><b></b></div>
    </div>
    <div class="ctlbar">
      <a class="pw" id="pw" href="daily.html" aria-label="进入今日精选">
        <span class="knob" aria-hidden="true"></span><span class="t">start</span><span class="trk" aria-hidden="true"></span></a>
      <span class="rpm">33⅓ rpm</span>
      <span class="led"></span>
    </div>
  </div>

  <div class="rail">
    <div>issue <b>{n_issues:03d}</b></div>
    <div>pool <b>{n_tracks}</b></div>
    <div class="vs">visitors <b id="vis">—</b></div>
    <div>{_esc(md)}</div>
  </div>

  <nav class="tip" aria-label="浏览音乐"><a href="daily.html">今日日报</a><a href="random.html">听点别的</a><a href="archive/index.html">往期</a><a href="legacy/index.html">旧版</a></nav>
  <div class="foot">© {year} MUSIC DAILY · PERSONAL USE · COVER &amp; PREVIEW VIA PUBLIC MUSIC API</div>
</main>
<script>const HITURL={hit!r};{LANDING_JS}</script>
</body>
</html>"""
