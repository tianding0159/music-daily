"""站点入口：黑胶上机落地页（site/index.html）。

日报本体在 daily.html，这里是访客先看到的一屏：
中央一张黑胶在唱盘上慢速自转，中心白标签印着 MUSIC DAILY 与期号。
唱臂停在盘外，点「drop the needle」→ 唱臂落到外圈 → 唱片提速 →
画面往前推、白闪一下 → 进日报。浅色纸底，排版与日报一致。

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
from render_grid import _esc
from render_random import EXTRA_CSS as RANDOM_CSS

COUNTER_NS = "tianding0159-music-daily"
COUNTER_KEY = "landing"


def _vinyl_label(n_issues: int, latest_date: str) -> str:
    """传统黑胶纸标签排版：上弧走站名、中间横排期号、下弧走转速。

    真黑胶标签的字是围着中心绕的（上下半圈都正读），CSS 做不到，
    用两条方向相反的 SVG 弧线 + textPath。viewBox 100×100，圆心 (50,50)。
    """
    md = latest_date.replace("-", ".") if latest_date else ""
    return (
        '<svg viewBox="0 0 100 100" aria-hidden="true">'
        '<path id="vt" fill="none" d="M20 50 A30 30 0 0 1 80 50"/>'
        '<path id="vb" fill="none" d="M16 50 A34 34 0 0 0 84 50"/>'
        '<text class="arc"><textPath href="#vt" startOffset="50%" text-anchor="middle">'
        'MUSIC DAILY</textPath></text>'
        '<text class="mid" x="50" y="47.5" text-anchor="middle">MD-30</text>'
        f'<text class="sub" x="50" y="56" text-anchor="middle">ISSUE {n_issues:03d}</text>'
        f'<text class="sub" x="50" y="62" text-anchor="middle">{md}</text>'
        '<text class="arc lo"><textPath href="#vb" startOffset="50%" text-anchor="middle">'
        '33\u2153 RPM \u00b7 LONG PLAYING</textPath></text>'
        '</svg>')


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
html,body{height:100%}
/* 与日报 body 同一套排版（--sans / weight 300 / line-height 1.5 / 同 font-feature） */
body{background:var(--paper); color:var(--ink); overflow:hidden;
  font-family:var(--sans); font-weight:300; line-height:1.5; letter-spacing:0;
  -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility;
  font-feature-settings:"kern" 1,"liga" 1}
.stage{min-height:100%; min-height:100svh; display:flex; flex-direction:column;
  align-items:center; justify-content:center; gap:clamp(16px,3vh,30px);
  padding:clamp(16px,4vw,38px); position:relative}
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

.plate{display:flex; align-items:center; gap:10px; font-family:var(--mono);
  font-size:var(--fs-10); letter-spacing:.16em; text-transform:uppercase;
  color:var(--g600); position:relative; z-index:2; animation:fade-up .5s ease-out both}
.plate .sq{width:11px; height:11px; background:var(--orange)}
.plate b{color:var(--ink); font-weight:400; letter-spacing:.1em}

/* ── 唱盘：容器挂 .tt 继承 render_random 那套几何 ── */
/* 底座：真唱机是「盘在上、控制条在下」，容器不再是正方——
   上半 1:1 转盘区，下方留一条 62px 控制条放 START 键、转速标记、电源灯。 */
.deckbox{position:relative; z-index:2; width:min(420px,78vw);
  animation:fade-up .6s cubic-bezier(.16,1,.3,1) .1s both}
/* .deck 塌成 0×0 的真因（实测）：切片里的 @supports 块给 .tt .deck 设了
   height:min(100cqw,100cqh)，而落地页的 .deckbox 此刻高度由子元素决定 → 100cqh = 0
   → deck 高 0 → 容器还是 0，成了容器查询的循环依赖。
   这里用更高特异性覆盖掉它，改回「宽度撑满 + aspect-ratio 定高」。 */
.deckbox.tt{container-type:normal}
.deckbox.tt .deck{width:100%; height:auto; aspect-ratio:1; max-height:none; margin:0 auto}
.ctlbar{position:absolute; left:0; right:0; bottom:0; height:62px; z-index:6;
  display:flex; align-items:center; gap:14px; padding:0 20px;
  border-top:1px solid rgba(255,255,255,.07)}
.ctlbar .rpm{margin-left:auto; font-family:var(--mono); font-size:9px;
  letter-spacing:.14em; color:rgba(255,255,255,.32)}
/* 唱盘自带的转速标记与电源灯本来是绝对定位在盘面角上的，现在归到控制条 */
.deckbox.tt::after{content:none}
.deckbox .ctlbar .led{position:static; flex:none; margin:0}
.deckbox.tt{position:relative; inset:auto; display:block; padding-bottom:62px;
  background:var(--ink); overflow:visible; border:1px solid var(--g200); border-radius:2px;
  box-shadow:0 20px 46px -24px rgba(15,14,18,.5);
  animation:fade-up .6s cubic-bezier(.16,1,.3,1) .1s both}
/* 唱片：慢速自转；点下之后提速 */
.deckbox .disc{animation:spin 9s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
/* 点下后由慢加速到高速：关键帧间距递增＝真的在提速，不是匀速转一圈 */
body.go .deckbox .disc{animation:spin-up 2.2s linear forwards}
@keyframes spin-up{
  0%{transform:rotate(0)}        14%{transform:rotate(26deg)}
  30%{transform:rotate(104deg)}  46%{transform:rotate(286deg)}
  62%{transform:rotate(612deg)}  78%{transform:rotate(1080deg)}
  90%{transform:rotate(1512deg)} 100%{transform:rotate(1872deg)}}
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
/* 唱臂：停机位；点下之后落到外圈并停住 */
.deckbox .arm{transform:rotate(80deg)}
body.go .deckbox .arm{animation:arm-drop .8s cubic-bezier(.3,.86,.32,1) both}
@keyframes arm-drop{0%{transform:rotate(80deg)}
  72%{transform:rotate(55.3deg)} 88%{transform:rotate(57.5deg)}
  100%{transform:rotate(56.6deg)}}
/* 落针那一下：盘面一圈短促涟漪 */
body.go .deckbox .deck{animation:needle-hit .36s ease-out .74s both}
@keyframes needle-hit{0%{box-shadow:0 0 0 0 rgba(255,255,255,.42)}
  100%{box-shadow:0 0 0 16px rgba(255,255,255,0)}}

/* 铭牌行：期号 / 曲目数 / 访客数 —— 访客计数就在这儿 */
.rail{position:relative; z-index:2; display:flex; border:1px solid var(--g300);
  background:var(--white);
  font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase;
  letter-spacing:.1em; animation:fade-up .5s ease-out .5s both}
.rail div{padding:9px 15px; border-right:1px solid var(--g100); color:var(--g600);
  display:flex; align-items:baseline; gap:7px; white-space:nowrap}
.rail div:last-child{border-right:none}
.rail b{color:var(--ink); font-weight:700; letter-spacing:.04em}
.rail .vs b{color:var(--green-d)}

/* ── START 键：集成在唱盘底座的控制条上（真唱机就长这样）──
   TE 语言：一枚小圆钮 + 旁边刻字，极细小写，橙色只用在状态上。 */
.pw{appearance:none; border:none; background:none; cursor:pointer; padding:0;
  display:inline-flex; align-items:center; gap:10px;
  font-family:var(--sans); font-size:var(--fs-15); font-weight:300;
  letter-spacing:normal; text-transform:lowercase; line-height:1.1;
  color:rgba(245,245,245,.7); transition:color .16s}
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
.pw.down .knob{box-shadow:inset 0 0 0 1px rgba(255,255,255,.2), 0 0 0 3px rgba(240,90,36,.18)}
.pw.down .knob::after{background:var(--orange)}
/* 键右侧一条极细刻度轨，按下后 2.2s 走完（呼应 TE 面板刻度）。
   两处对齐讲究：
   ① 长度 22px = 圆钮直径，左右两端形成呼应，不是随手取的数
   ② 轨要对齐字形的【视觉中心】，不是文字盒中心。canvas measureText 实测
      "start" 在 14px 下 ascent=10、descent=0（t 有升部、无降部），
      字形视觉中心比 16px 文字盒的几何中心高 2px。所以轨上移 2px。 */
.pw .trk{width:22px; height:1px; flex:none; background:rgba(245,245,245,.2);
  position:relative; top:-1px}
.pw .trk::after{content:""; position:absolute; left:0; top:0; height:100%; width:0;
  background:var(--orange)}
.pw.down .trk::after{animation:trk-run 2.2s linear forwards}
@keyframes trk-run{to{width:100%}}

.tip{font-family:var(--mono); font-size:var(--fs-10); color:var(--g600);
  letter-spacing:.1em; position:relative; z-index:2;
  animation:fade-up .5s ease-out .85s both}
.tip kbd{border:1px solid var(--g300); background:var(--white); display:inline-flex; align-items:center;
  justify-content:center; min-width:1.9em; height:1.55em; padding:0 .45em;
  line-height:1; color:var(--g900); vertical-align:middle; position:relative; top:-.05em}
.foot{position:absolute; left:0; right:0; bottom:13px; text-align:center;
  font-family:var(--mono); font-size:9px; letter-spacing:.1em; color:var(--g300); z-index:2}
@keyframes fade-up{from{opacity:0; transform:translateY(9px)}to{opacity:1; transform:none}}

/* 离场：画面往前推 + 白闪 */
/* 唱片提速跑完 2.2s 之后才推进，整段 3.0s */
body.go .stage{animation:push-in .78s cubic-bezier(.6,0,.8,.2) 2.2s forwards}
@keyframes push-in{to{transform:scale(1.45); opacity:.25}}
body.go .plate,body.go .rail,body.go .tip,body.go .foot{
  animation:none; opacity:0; transition:opacity .3s .3s}
body.go .pw{animation:none; opacity:0; transition:opacity .3s 1.9s}
body.go::after{content:""; position:fixed; inset:0; background:var(--paper);
  opacity:0; z-index:99; animation:flash .34s ease-in 2.62s forwards; pointer-events:none}
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
  .stage::after,.deckbox .disc{animation:none}
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
    document.getElementById('pw').classList.add('down');   // 键帽保持按下
    document.body.classList.add('go');
    setTimeout(function(){ location.href = 'daily.html'; }, reduce ? 60 : 2960);
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
<meta name="theme-color" content="#f5f5f5">
<link rel="preload" href="daily.html" as="document">
<style>{GRID_CSS}{_turntable_css()}{LANDING_CSS}</style>
</head>
<body>
<div class="stage">
  <div class="plate"><span class="sq"></span><b>music daily</b> · md-30</div>

  <div class="deckbox tt">
    <div class="deck">
      <div class="dwrap"><div class="disc">
        <span class="lbl">{_vinyl_label(n_issues, latest_date)}</span>
      </div></div>
      <div class="arm"><i></i><b></b></div>
    </div>
    <div class="ctlbar">
      <button class="pw" id="pw" type="button">
        <span class="knob"></span>start<span class="trk"></span></button>
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

  <div class="tip">按下 start · 或敲 <kbd>space</kbd> / <kbd>enter</kbd> 落针进今日精选</div>
  <div class="foot">© {year} MUSIC DAILY · PERSONAL USE · COVER &amp; PREVIEW VIA PUBLIC MUSIC API</div>
</div>
<script>const HITURL={hit!r};{LANDING_JS}</script>
</body>
</html>"""
