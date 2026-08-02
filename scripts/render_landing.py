"""站点入口：黑胶上机落地页（site/index.html）。

日报本体在 daily.html，这里是访客先看到的一屏：
中央一张黑胶在唱盘上慢速自转，中心白标签印着 MUSIC DAILY 与期号。
唱臂停在盘外，点「drop the needle」→ 唱臂落到外圈 → 唱片提速 →
画面往前推、白闪一下 → 进日报。像素猫蹲在唱盘右下角看着。

复用而非重画：
- 唱盘/唱片/唱臂的几何与配色全部来自 render_random 的 `.tt` 那套
  （针尖落点已经调到 0.92r，重画一次必然又偏），落地页给容器挂上
  `class="tt"` 直接继承整块作用域。
- 像素猫同理挂 `class="lcd"` 继承 render_grid 那 14 条填色/动画规则。
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
from render_grid import ICON_CAT, _esc
from render_random import EXTRA_CSS as RANDOM_CSS

COUNTER_NS = "tianding0159-music-daily"
COUNTER_KEY = "landing"


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
html,body{height:100%}
body{background:var(--ink); color:var(--white); overflow:hidden;
  font-family:var(--sans); -webkit-font-smoothing:antialiased}
.stage{min-height:100%; min-height:100svh; display:flex; flex-direction:column;
  align-items:center; justify-content:center; gap:clamp(16px,3vh,30px);
  padding:clamp(16px,4vw,38px); position:relative}
/* 背景：极淡网格 + 一道缓慢扫过的绿光 */
.stage::before{content:""; position:absolute; inset:0; pointer-events:none; opacity:.45;
  background:
    linear-gradient(rgba(255,255,255,.026) 1px, transparent 1px) 0 0/100% 34px,
    linear-gradient(90deg, rgba(255,255,255,.026) 1px, transparent 1px) 0 0/34px 100%;
  mask-image:radial-gradient(ellipse 76% 60% at 50% 46%, #000 28%, transparent 100%)}
.stage::after{content:""; position:absolute; left:-30%; top:0; width:26%; height:100%;
  pointer-events:none; opacity:.45;
  background:linear-gradient(90deg, transparent, rgba(0,166,81,.085) 45%, transparent);
  animation:sweep 11s ease-in-out infinite}
@keyframes sweep{0%{transform:translateX(0)}100%{transform:translateX(560%)}}

.plate{display:flex; align-items:center; gap:10px; font-family:var(--mono);
  font-size:var(--fs-10); letter-spacing:.16em; text-transform:uppercase;
  color:var(--g500); position:relative; z-index:2; animation:fade-up .5s ease-out both}
.plate .sq{width:11px; height:11px; background:var(--orange)}
.plate b{color:var(--white); font-weight:400; letter-spacing:.1em}

/* ── 唱盘：容器挂 .tt 继承 render_random 那套几何 ── */
.deckbox{position:relative; z-index:2; width:min(420px,78vw); aspect-ratio:1;
  animation:fade-up .6s cubic-bezier(.16,1,.3,1) .1s both}
.deckbox.tt{position:relative; inset:auto; display:grid; place-items:center;
  background:var(--ink); overflow:visible; animation:fade-up .6s cubic-bezier(.16,1,.3,1) .1s both}
/* 唱片：慢速自转；点下之后提速 */
.deckbox .disc{animation:spin 7s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
body.go .deckbox .disc{animation:spin-up 1s cubic-bezier(.4,0,.7,.6) forwards}
@keyframes spin-up{to{transform:rotate(1080deg)}}
/* 唱片自带的沿弧转速字 .vlbl 与中心标签抢位，落地页隐掉 */
.deckbox .disc .vlbl{display:none}
/* 中心白标签：挂在【不自转】的 .dwrap 上。
   挂 .disc 会跟着转，转到下半圈字就是倒的（实测确认），读不了。 */
.deckbox .dwrap>.lbl{position:absolute; left:50%; top:50%; transform:translate(-50%,-50%);
  background:#f5f5f5; box-shadow:0 0 0 1px rgba(0,0,0,.12);
  width:34%; aspect-ratio:1; border-radius:50%; display:grid; place-items:center;
  text-align:center; font-family:var(--mono); color:#1a1a1a; line-height:1.5;
  letter-spacing:.06em; text-transform:uppercase; z-index:3; pointer-events:none}
.deckbox .dwrap>.lbl i{font-style:normal; font-size:clamp(7px,1.5vw,9px); display:block}
.deckbox .dwrap>.lbl b{font-weight:700; font-size:clamp(8px,1.7vw,10.5px); display:block}
.deckbox .dwrap>.lbl s{text-decoration:none; font-size:clamp(6px,1.2vw,7.5px); opacity:.62; display:block}
/* 唱臂：停机位；点下之后落到外圈并停住 */
.deckbox .arm{transform:rotate(80deg)}
body.go .deckbox .arm{animation:arm-drop .8s cubic-bezier(.3,.86,.32,1) both}
@keyframes arm-drop{0%{transform:rotate(80deg)}
  72%{transform:rotate(57.2deg)} 88%{transform:rotate(59.4deg)}
  100%{transform:rotate(58.5deg)}}
/* 猫蹲在唱盘右下角外沿 */
.deckbox .cat{position:absolute; left:-4px; bottom:-2px; width:62px; height:42px;
  background:transparent; border:none; z-index:5; opacity:0;
  animation:cat-in .55s cubic-bezier(.2,.9,.3,1) 1.1s forwards}
@keyframes cat-in{from{opacity:0; transform:translateX(-46px)}to{opacity:1; transform:none}}
.deckbox .cat .cat-wrap{width:100%; height:42px; margin:0}
.deckbox .cat .pose{right:2px}

/* 铭牌行：期号 / 曲目数 / 访客数 —— 访客计数就在这儿 */
.rail{position:relative; z-index:2; display:flex; border:1px solid var(--g1000);
  font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase;
  letter-spacing:.1em; animation:fade-up .5s ease-out .5s both}
.rail div{padding:9px 15px; border-right:1px solid var(--g1000); color:#5c5c5c;
  display:flex; align-items:baseline; gap:7px; white-space:nowrap}
.rail div:last-child{border-right:none}
.rail b{color:var(--white); font-weight:400; letter-spacing:.04em}
.rail .vs b{color:var(--green)}

/* 落针钮 */
.pw{position:relative; z-index:2; appearance:none; border:1px solid var(--green-d);
  background:transparent; color:var(--white); cursor:pointer; font-family:var(--mono);
  font-size:var(--fs-20); letter-spacing:.24em; text-transform:uppercase;
  padding:16px 34px; opacity:0;
  animation:fade-up .5s ease-out .7s both, breathe 2.8s ease-in-out 1.4s infinite;
  transition:background .18s, border-color .18s, letter-spacing .25s}
.pw:hover{background:rgba(0,166,81,.12); border-color:var(--green); letter-spacing:.3em}
.pw:active{transform:scale(.985)}
.pw:focus-visible{outline:2px solid var(--green); outline-offset:3px}
@keyframes breathe{0%,100%{box-shadow:0 0 0 0 rgba(0,166,81,0)}
  50%{box-shadow:0 0 30px -4px rgba(0,166,81,.5)}}

.tip{font-family:var(--mono); font-size:var(--fs-10); color:var(--g600);
  letter-spacing:.1em; position:relative; z-index:2;
  animation:fade-up .5s ease-out .85s both}
.tip kbd{border:1px solid var(--g900); display:inline-flex; align-items:center;
  justify-content:center; min-width:1.9em; height:1.55em; padding:0 .45em;
  line-height:1; color:var(--g300); vertical-align:middle; position:relative; top:-.05em}
.foot{position:absolute; left:0; right:0; bottom:13px; text-align:center;
  font-family:var(--mono); font-size:9px; letter-spacing:.1em; color:#3a3a3a; z-index:2}
@keyframes fade-up{from{opacity:0; transform:translateY(9px)}to{opacity:1; transform:none}}

/* 离场：画面往前推 + 白闪 */
body.go .stage{animation:push-in .8s cubic-bezier(.6,0,.8,.2) forwards}
@keyframes push-in{to{transform:scale(1.5); opacity:.25}}
body.go .plate,body.go .rail,body.go .pw,body.go .tip,body.go .foot{
  animation:none; opacity:0; transition:opacity .25s}
body.go::after{content:""; position:fixed; inset:0; background:var(--white);
  opacity:0; z-index:99; animation:flash .3s ease-in .5s forwards; pointer-events:none}
@keyframes flash{to{opacity:1}}

@media(max-width:520px){
  .stage{gap:16px; padding:18px 14px}
  .deckbox{width:min(320px,84vw)}
  .rail{font-size:9px; flex-wrap:wrap}
  .rail div{padding:7px 11px; gap:6px}
  .pw{font-size:14px; padding:14px 26px; letter-spacing:.2em}
  .tip{font-size:9px; text-align:center; line-height:2}
}
@media(prefers-reduced-motion:reduce){
  .stage::after,.deckbox .disc,.deckbox .cat{animation:none}
  .deckbox .cat{opacity:1}
  .plate,.deckbox,.rail,.pw,.tip,.foot{animation:none; opacity:1}
  .pw{box-shadow:none}
  body.go .stage{animation:none}
}
"""

LANDING_JS = """
(function(){
  var reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

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

  var going = false;
  function go(){
    if(going) return; going = true;
    document.body.classList.add('go');
    setTimeout(function(){ location.href = 'daily.html'; }, reduce ? 60 : 830);
  }
  document.getElementById('pw').addEventListener('click', go);
  addEventListener('keydown', function(e){
    if(e.key === ' ' || e.key === 'Enter'){ e.preventDefault(); go(); }
  });
})();
"""


def build_html(n_issues: int, n_tracks: int, n_moods: int, latest_date: str,
               playlist_title: str = "") -> str:
    hit = f"https://abacus.jasoncameron.dev/hit/{COUNTER_NS}/{COUNTER_KEY}"
    year = dt.datetime.now(dt.timezone.utc).year
    md = latest_date.replace("-", ".") if latest_date else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>MUSIC DAILY</title>
<meta name="description" content="每日精选 30 首 · melody-first · mood-first · production-first">
<meta name="theme-color" content="#0f0e12">
<link rel="preload" href="daily.html" as="document">
<style>{GRID_CSS}{_turntable_css()}{LANDING_CSS}</style>
</head>
<body>
<div class="stage">
  <div class="plate"><span class="sq"></span><b>music daily</b> · md-30</div>

  <div class="deckbox tt">
    <div class="deck">
      <div class="dwrap"><div class="disc"></div>
        <span class="lbl"><i>music</i><b>daily</b><s>md-30 · {n_issues:03d}</s></span>
      </div>
      <div class="arm"><i></i><b></b></div>
    </div>
    <span class="led"></span>
    <div class="cat lcd"><div class="cat-wrap">{ICON_CAT}</div></div>
  </div>

  <div class="rail">
    <div>issue <b>{n_issues:03d}</b></div>
    <div>pool <b>{n_tracks}</b></div>
    <div class="vs">visitors <b id="vis">—</b></div>
    <div>{_esc(md)}</div>
  </div>

  <button class="pw" id="pw" type="button">drop the needle</button>
  <div class="tip">点一下 · 或按 <kbd>space</kbd> / <kbd>enter</kbd> 进入今日精选</div>
  <div class="foot">© {year} MUSIC DAILY · PERSONAL USE · COVER &amp; PREVIEW VIA PUBLIC MUSIC API</div>
</div>
<script>const HITURL={hit!r};{LANDING_JS}</script>
</body>
</html>"""
