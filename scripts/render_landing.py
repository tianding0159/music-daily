"""站点入口：开机自检落地页（site/index.html）。

日报本体挪到 daily.html，这里是访客先看到的一屏——模仿设备上电：
LCD 屏逐行打出自检日志（POOL / MELODY / MOOD / ARCHIVE / VISITORS），
像素猫从屏外跑进来抬头看，中央一个 POWER 方钮呼吸发光。
点 POWER（或按 space / enter）→ 屏幕先收成一条横线再炸开 → 跳进日报。

视觉全部沿用日报：Terminal Green + 工业铭牌 + 同一套 CSS 变量与像素猫，
所以直接从 render_grid 复用，不另起一套（另起必漂移）。

访客计数走 Abacus（jasoncameron.dev）：/hit 自增并返回，/get 只读。
实测有 access-control-allow-origin:*，纯静态页可直接 fetch。
拿不到就显示 "—"，绝不因为第三方挂了而卡住入场（fail-open）。
"""
from __future__ import annotations

import datetime as dt

from render_grid import CSS as GRID_CSS
from render_grid import ICON_CAT, _esc

# 计数命名空间：换 key 会从 0 重新计
COUNTER_NS = "tianding0159-music-daily"
COUNTER_KEY = "landing"

LANDING_CSS = """
html,body{height:100%}
body{background:var(--ink); color:var(--white); overflow:hidden;
  font-family:var(--sans); -webkit-font-smoothing:antialiased}
.stage{min-height:100%; min-height:100svh; display:flex; flex-direction:column;
  align-items:center; justify-content:center; gap:clamp(18px,3.4vh,34px);
  padding:clamp(18px,4vw,40px); position:relative}
/* 背景：极淡的等距网格 + 一道缓慢扫过的绿光，暗示机器在运转 */
.stage::before{content:""; position:absolute; inset:0; pointer-events:none; opacity:.5;
  background:
    linear-gradient(rgba(255,255,255,.028) 1px, transparent 1px) 0 0/100% 34px,
    linear-gradient(90deg, rgba(255,255,255,.028) 1px, transparent 1px) 0 0/34px 100%;
  mask-image:radial-gradient(ellipse 78% 62% at 50% 46%, #000 30%, transparent 100%)}
.stage::after{content:""; position:absolute; left:-30%; top:0; width:26%; height:100%;
  pointer-events:none; opacity:.5;
  background:linear-gradient(90deg, transparent, rgba(0,166,81,.09) 45%, transparent);
  animation:sweep 9s ease-in-out infinite}
@keyframes sweep{0%{transform:translateX(0)}100%{transform:translateX(560%)}}

/* 顶部铭牌 */
.plate{display:flex; align-items:center; gap:10px; font-family:var(--mono);
  font-size:var(--fs-10); letter-spacing:.16em; text-transform:uppercase;
  color:var(--g500); position:relative; z-index:2;
  animation:fade-up .5s ease-out both}
.plate .sq{width:11px; height:11px; background:var(--orange)}
.plate b{color:var(--white); font-weight:400; letter-spacing:.1em}

/* LCD 自检屏 */
.scr{width:min(560px,100%); border:1px solid var(--g1000); background:#08110c;
  position:relative; z-index:2; animation:fade-up .55s ease-out .08s both;
  box-shadow:0 0 0 1px rgba(0,166,81,.1), 0 26px 60px -30px rgba(0,166,81,.4)}
.scr .bar{display:flex; align-items:center; gap:8px; padding:8px 14px;
  border-bottom:1px solid #12241a; font-family:var(--mono); font-size:9px;
  letter-spacing:.14em; text-transform:uppercase; color:#2f6b4a}
.scr .bar .dot{width:6px; height:6px; border-radius:50%; background:var(--green);
  box-shadow:0 0 7px var(--green); animation:pulse 1.6s steps(1) infinite}
@keyframes pulse{50%{opacity:.3}}
.scr .bar .rt{margin-left:auto; letter-spacing:.1em}
.scr .body{padding:16px 16px 12px; font-family:var(--mono); font-size:var(--fs-15);
  color:var(--green); line-height:2.05; min-height:210px; position:relative}
/* 自检每行：左标签 · 中间点线 · 右值。点线用 repeating-linear 画，不用手打 ... */
.ln{display:flex; align-items:baseline; gap:9px; opacity:0; transform:translateX(-6px)}
.ln.on{animation:ln-in .28s ease-out forwards}
@keyframes ln-in{to{opacity:1; transform:none}}
.ln .t{color:#3f8f66}
.ln .dots{flex:1; height:1px; align-self:center; opacity:.34;
  background:repeating-linear-gradient(90deg,currentColor 0 2px,transparent 2px 6px)}
.ln .v{color:var(--green); font-weight:400}
.ln .v.warn{color:var(--yellow,#fab413)}
.ln.done .v::after{content:" ✓"; color:#2f6b4a}
.cur{display:inline-block; width:.55em; background:var(--green); animation:blink .5s steps(1) infinite}
@keyframes blink{50%{opacity:0}}
/* 猫从屏幕右侧外跑进来，停在最后一行右边抬头 */
/* 猫：直接挂 .lcd 类复用日报那 14 条填色/动画规则（背景透明化即可） */
.scr .cat{position:absolute; right:14px; bottom:6px; width:58px; height:40px;
  background:transparent; border:none; margin:0; opacity:0;
  animation:cat-enter .6s cubic-bezier(.2,.9,.3,1) 2.5s forwards}
@keyframes cat-enter{from{opacity:0; transform:translateX(52px)}to{opacity:1; transform:none}}
.scr .cat .cat-wrap{width:100%; height:40px; margin:0}
.scr .cat .pose{right:2px}

/* POWER 方钮 */
.pw{position:relative; z-index:2; appearance:none; border:1px solid var(--green-d);
  background:transparent; color:var(--white); cursor:pointer; font-family:var(--mono);
  font-size:var(--fs-20); letter-spacing:.3em; text-transform:uppercase;
  padding:17px 42px 17px 46px; opacity:0;
  animation:fade-up .5s ease-out 3s both, breathe 2.6s ease-in-out 3.5s infinite;
  transition:background .18s, border-color .18s, letter-spacing .25s}
.pw:hover{background:rgba(0,166,81,.12); border-color:var(--green); letter-spacing:.36em}
.pw:active{transform:scale(.985)}
.pw:focus-visible{outline:2px solid var(--green); outline-offset:3px}
@keyframes breathe{0%,100%{box-shadow:0 0 0 0 rgba(0,166,81,0)}
  50%{box-shadow:0 0 30px -4px rgba(0,166,81,.55)}}
/* 钮内左侧的电源符号 */
.pw::before{content:""; position:absolute; left:20px; top:50%; width:11px; height:11px;
  margin-top:-5.5px; border:1.6px solid currentColor; border-radius:50%;
  clip-path:polygon(0 32%,100% 32%,100% 100%,0 100%)}
.pw::after{content:""; position:absolute; left:24.6px; top:50%; width:1.6px; height:8px;
  margin-top:-9px; background:currentColor}

.tip{font-family:var(--mono); font-size:var(--fs-10); color:var(--g600);
  letter-spacing:.1em; position:relative; z-index:2;
  animation:fade-up .5s ease-out 3.2s both}
.tip kbd{border:1px solid var(--g900); display:inline-flex; align-items:center;
  justify-content:center; min-width:1.9em; height:1.55em; padding:0 .45em;
  line-height:1; color:var(--g300); vertical-align:middle; position:relative; top:-.05em}
.foot{position:absolute; left:0; right:0; bottom:14px; text-align:center;
  font-family:var(--mono); font-size:9px; letter-spacing:.1em; color:#3a3a3a; z-index:2}
@keyframes fade-up{from{opacity:0; transform:translateY(9px)}to{opacity:1; transform:none}}

/* 离场：屏幕先横向收成一条线再整体炸白，然后跳转 */
body.go .scr{animation:collapse .42s cubic-bezier(.7,0,.84,0) forwards}
body.go .plate,body.go .pw,body.go .tip,body.go .foot{animation:none; opacity:0;
  transition:opacity .2s}
@keyframes collapse{
  55%{transform:scaleY(.02); opacity:1}
  70%{transform:scaleY(.02) scaleX(1.04); opacity:1}
  100%{transform:scaleY(.02) scaleX(1.5); opacity:0}}
body.go::after{content:""; position:fixed; inset:0; background:var(--white);
  opacity:0; z-index:99; animation:flash .34s ease-in .3s forwards; pointer-events:none}
@keyframes flash{to{opacity:1}}

@media(max-width:520px){
  .stage{gap:20px; padding:20px 16px}
  .scr .body{font-size:13px; line-height:1.95; min-height:190px; padding:13px 13px 10px}
  .pw{font-size:14px; padding:15px 30px 15px 40px; letter-spacing:.24em}
  .tip{font-size:9px; text-align:center; line-height:2}
}
@media(prefers-reduced-motion:reduce){
  .stage::after,.scr .bar .dot,.cur{animation:none}
  .ln{opacity:1; transform:none}
  .plate,.scr,.pw,.tip,.foot{animation:none; opacity:1}
  .scr .cat{opacity:1; animation:none}
  .pw{box-shadow:none}
  body.go .scr{animation:none; opacity:0}
}
"""

LANDING_JS = """
(function(){
  var LINES = document.querySelectorAll('.ln');
  var reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  var i = 0;
  function step(){
    if(i >= LINES.length) return;
    var el = LINES[i++];
    el.classList.add('on');
    setTimeout(function(){ el.classList.add('done'); }, 190);
    setTimeout(step, 330);
  }
  if(reduce){ LINES.forEach(function(l){ l.classList.add('on','done'); }); }
  else { setTimeout(step, 260); }

  // 访客计数：Abacus /hit 自增并返回当前值。第三方挂了就留 "—"，绝不挡入场。
  var slot = document.getElementById('vis');
  if(slot){
    fetch(HITURL, {cache:'no-store'})
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(d){
        var n = d && (d.value != null ? d.value : d.count);
        if(n == null) return;
        slot.textContent = String(n).padStart(5,'0');
        slot.parentElement.classList.remove('warn');
      })
      .catch(function(){});
  }

  var going = false;
  function go(){
    if(going) return; going = true;
    try{ sessionStorage.setItem('md_entered','1'); }catch(e){}
    document.body.classList.add('go');
    setTimeout(function(){ location.href = 'daily.html'; }, reduce ? 60 : 660);
  }
  document.getElementById('pw').addEventListener('click', go);
  addEventListener('keydown', function(e){
    if(e.key === ' ' || e.key === 'Enter'){ e.preventDefault(); go(); }
  });
})();
"""


def build_html(n_issues: int, n_tracks: int, n_moods: int, latest_date: str,
               playlist_title: str = "") -> str:
    """开机自检落地页。数字都从真实数据来，不写死。"""
    hit = f"https://abacus.jasoncameron.dev/hit/{COUNTER_NS}/{COUNTER_KEY}"
    year = dt.datetime.now(dt.timezone.utc).year

    def ln(tag: str, val: str, cls: str = "") -> str:
        return (f'<div class="ln"><span class="t">{_esc(tag)}</span>'
                f'<span class="dots"></span>'
                f'<span class="v {cls}">{_esc(val)}</span></div>')

    rows = "".join([
        ln("boot", "md-30"),
        ln("pool", f"{n_tracks} tracks"),
        ln("melody-first", "ok"),
        ln("mood index", f"{n_moods} tags"),
        ln("archive", f"{n_issues} issues"),
        # 访客数先占位，JS 拿到再替换；拿不到就保持 "—"（fail-open）
        f'<div class="ln"><span class="t">visitors</span><span class="dots"></span>'
        f'<span class="v warn"><span id="vis">—</span></span></div>',
        ln("latest", latest_date),
    ])
    sub = (f'<div class="ln"><span class="t">&gt;</span><span class="v">'
           f'{_esc(playlist_title or "ready")}<span class="cur">&nbsp;</span></span></div>')

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>MUSIC DAILY</title>
<meta name="description" content="每日精选 30 首 · melody-first · mood-first · production-first">
<meta name="theme-color" content="#0f0e12">
<link rel="preload" href="daily.html" as="document">
<style>{GRID_CSS}{LANDING_CSS}</style>
</head>
<body>
<div class="stage">
  <div class="plate"><span class="sq"></span><b>music daily</b> · md-30</div>

  <div class="scr">
    <div class="bar"><span class="dot"></span><span>self-check</span>
      <span class="rt">issue {n_issues:03d}</span></div>
    <div class="body">
      {rows}
      {sub}
      <div class="cat lcd"><div class="cat-wrap">{ICON_CAT}</div></div>
    </div>
  </div>

  <button class="pw" id="pw" type="button">power</button>
  <div class="tip">点一下 · 或按 <kbd>space</kbd> / <kbd>enter</kbd> 进入今日精选</div>
  <div class="foot">© {year} MUSIC DAILY · PERSONAL USE · COVER &amp; PREVIEW VIA PUBLIC MUSIC API</div>
</div>
<script>const HITURL={hit!r};{LANDING_JS}</script>
</body>
</html>"""
