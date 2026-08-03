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

/* 铭牌：与日报同一套字体（--sans + 极细）。TE 规范只用 100/300，从不 400/700。 */
.plate{display:flex; align-items:center; gap:10px; font-family:var(--sans);
  font-size:var(--fs-15); font-weight:300; letter-spacing:.02em; text-transform:lowercase;
  color:var(--g600); position:relative; z-index:2; animation:fade-up .5s ease-out both}
.plate .sq{width:10px; height:10px; background:var(--orange)}
.plate b{color:var(--ink); font-weight:300; letter-spacing:.02em}

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
  animation:fade-up .6s cubic-bezier(.16,1,.3,1) .1s both}
/* 唱片：慢速自转；点下之后提速 */
.deckbox .disc{animation:spin 9s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
/* 点下后由慢加速到高速：关键帧间距递增＝真的在提速，不是匀速转一圈 */
/* spin-up 与 needle-hit 合并声明在下方（同一元素上两条 animation，
   分开写后者会整条覆盖前者，唱片就不转了） */
@keyframes spin-up{
  0%{transform:rotate(0)}        11%{transform:rotate(26deg)}
  23%{transform:rotate(104deg)}  35%{transform:rotate(286deg)}
  47%{transform:rotate(612deg)}  59%{transform:rotate(1080deg)}
  68%{transform:rotate(1512deg)} 78%{transform:rotate(2016deg)}
  88%{transform:rotate(2592deg)} 100%{transform:rotate(3312deg)}}
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
/* arm-drop 与 arm-out 合并声明在离场那一段（同元素两条 animation
   必须写在一条 animation 里，分开写后者整条覆盖前者，落针就没了） */
@keyframes arm-drop{0%{transform:rotate(80deg)}
  72%{transform:rotate(55.3deg)} 88%{transform:rotate(57.5deg)}
  100%{transform:rotate(56.6deg)}}
/* 落针那一下：涟漪从唱片外缘朝内收。
   原来挂在 .deck 上用【向外扩】的 box-shadow —— .deck 是正方形、下边缘紧贴控制条，
   白圈扩出去就在控制条那条 border-top 上摊成一道横白线，实测第 250ms 那一帧
   控制条顶边亮度从 18 突跳到 76、下一帧掉回，看着就是「横线冒一下白光」。
   改挂 .disc（border-radius:50% 的正圆）并用 inset：光从外缘往内收，
   物理上也更对（针尖落在最外圈沟槽），且 inset 永远溢不出唱片、碰不到控制条。 */
body.go .deckbox .disc{animation:spin-up 2.9s linear forwards,
  needle-hit .42s ease-out .74s both}
@keyframes needle-hit{0%{box-shadow:inset 0 0 0 0 rgba(255,255,255,.30)}
  40%{box-shadow:inset 0 0 12px 3px rgba(255,255,255,.20)}
  100%{box-shadow:inset 0 0 26px 10px rgba(255,255,255,0)}}

/* 铭牌行：期号 / 曲目数 / 访客数 —— 访客计数就在这儿 */
.rail{position:relative; z-index:2; display:flex; border:1px solid var(--g300);
  background:var(--white); font-family:var(--sans); font-size:var(--fs-10);
  font-weight:300; text-transform:lowercase; letter-spacing:.02em;
  animation:fade-up .5s ease-out .42s both}
.rail div{padding:9px 15px; border-right:1px solid var(--g100); color:var(--g600);
  display:flex; align-items:baseline; gap:7px; white-space:nowrap}
.rail div:last-child{border-right:none}
.rail b{color:var(--ink); font-weight:300; letter-spacing:.02em}
.rail .vs b{color:var(--green-d)}

/* ── START 键：集成在唱盘底座的控制条上（真唱机就长这样）──
   TE 语言：一枚小圆钮 + 旁边刻字，极细小写，橙色只用在状态上。 */
.pw{appearance:none; border:none; background:none; cursor:pointer; padding:0;
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
.pw.down .knob{box-shadow:inset 0 0 0 1px rgba(255,255,255,.2), 0 0 0 3px rgba(240,90,36,.18)}
.pw.down .knob::after{background:var(--orange)}
/* 键右侧一条极细刻度轨，按下后 2.2s 走完（呼应 TE 面板刻度）。
   两处对齐讲究：
   ① 长度 22px = 圆钮直径，左右两端形成呼应，不是随手取的数
   ② 轨要对齐字形的【视觉中心】，不是文字盒中心。canvas measureText 实测
      "start" 在 14px 下 ascent=10、descent=0（t 有升部、无降部），
      字形视觉中心比 16px 文字盒的几何中心高 2px。所以轨上移 2px。 */
.pw .trk{width:22px; height:1px; flex:none; background:rgba(245,245,245,.2);
  /* 轨对齐圆钮的几何中线（flex align-items:center 已保证），不再补偿——
     补偿量本是为了对齐旧的文字盒中线，文字上移后就不需要了 */
  position:relative; top:0}
.pw .trk::after{content:""; position:absolute; left:0; top:0; height:100%; width:0;
  background:var(--orange)}
.pw.down .trk::after{animation:trk-run 2.2s linear forwards}
@keyframes trk-run{to{width:100%}}

.tip{font-family:var(--sans); font-size:var(--fs-10); font-weight:300; color:var(--g600);
  letter-spacing:.02em; position:relative; z-index:2;
  animation:fade-up .5s ease-out .85s both}
.tip kbd{border:1px solid var(--g300); background:var(--white); font-family:var(--mono);
  font-size:.92em; display:inline-flex; align-items:center;
  justify-content:center; min-width:1.9em; height:1.55em; padding:0 .45em;
  line-height:1; color:var(--g900); vertical-align:middle; position:relative; top:-.05em}
.foot{position:absolute; left:0; right:0; bottom:13px; text-align:center;
  font-family:var(--sans); font-size:9px; font-weight:300; letter-spacing:.02em;
  text-transform:lowercase; color:var(--g300); z-index:2}
@keyframes fade-up{from{opacity:0; transform:translateY(9px)}to{opacity:1; transform:none}}

/* ── 离场：镜头钻进唱片中心的纸标签 ──────────────────────────
   旧版是「2.2s 唱片停转 → 整个 stage 等比 scale(1.45) 淡出 → 外挂一层白幕」。
   两个毛病：①提速在 2.2s 硬停、推进也在 2.2s 起，动作断成两截，看着就是
   「先停住再放大」；②「整体缩放+淡出+白闪」是任何网站都能用的通用转场，
   跟黑胶没有关系，所以显得普通。

   新版：转速一路加到底不断档，镜头从 1.9s 起【钻进唱片中心那张纸标签】。
   标签本来就是米白色（跟日报的 --paper 同色），它涨满屏幕的过程本身
   就是那道白 —— 白幕不再是外挂特效，而是画面里真实存在的东西。
   同时唱片还在转，所以最后一瞬是「旋转的白面扑上来」，不是「静止的图放大」。 */

/* 唱片区整体前推：origin 落在唱片圆心（.deck 是正方，圆心即 50% 50%）。
   只推 .deck 不推 .deckbox —— 控制条自己淡走，不跟着一起怼到脸上。 */
body.go .deckbox .deck{animation:dive 1.06s
  cubic-bezier(.55,0,.78,.16) 1.9s forwards}
@keyframes dive{
  0%{transform:scale(1)}
  38%{transform:scale(1.9)}
  100%{transform:scale(13)}}
/* 标签在推进后段同步涨大：镜头钻进去的最后一段，白面吃掉整屏。
   .lbl 实测是唱片直径的 37%（不是目测的 44%），scale 5.6 → 约 2.07 倍盘宽，
   再叠 .deck 的 13 倍推进，铺满 16:9 视口有余量。 */
body.go .deckbox .disc .lbl{animation:label-swell .62s
  cubic-bezier(.6,0,.85,.25) 2.34s forwards; transform-origin:50% 50%}
@keyframes label-swell{
  0%{transform:translate(-50%,-50%) scale(1)}
  100%{transform:translate(-50%,-50%) scale(5.6)}}
/* 主轴孔是黑的，跟着涨大会在白面正中留一个黑洞 —— 跟标签文字同时提前淡完。
   原来 2.34s 起淡 .3s，实测 2.45s 那帧才淡掉 37%，黑点还清晰可见。 */
body.go .deckbox .disc>.lbl::after{animation:spindle-out .4s ease-in 1.95s forwards}
@keyframes spindle-out{to{opacity:0}}
/* 标签上的字必须在【涨大开始之前】就淡完，不是边涨边淡 ——
   实测 2.34s 起淡 .34s 的话，2.7s 那帧仍能清晰读到倒写的 MUSIC DAILY，
   一堆巨大的字母怼在脸上。改成 1.95s 起、.42s 淡完，涨大时已是纯白面。 */
body.go .deckbox .disc .lbl svg{animation:lbl-text-out .42s ease-in 1.95s forwards}
@keyframes lbl-text-out{to{opacity:0}}
/* 盘面沟槽在钻进去时提亮一档：越靠近越亮，像被针尖带起的反光 */
body.go .deckbox .deck::after{animation:groove-hot .9s ease-in 2.0s forwards}
@keyframes groove-hot{to{opacity:.85; filter:brightness(1.9)}}

/* 周边元素按远近先后退场，不要一起消失 */
body.go .plate,body.go .rail,body.go .tip,body.go .foot{
  animation:none; opacity:0; transition:opacity .34s .24s}
body.go .pw{animation:none; opacity:0; transition:opacity .26s 1.62s}
body.go .ctlbar{animation:none; opacity:0; transition:opacity .4s 1.9s}
/* 唱臂：落针后它的任务就完了。推进时它会被放大成一根很粗的白棍（实测 2.45s
   那帧非常显眼），所以跟控制条一起淡走 —— 镜头里只留唱片和标签。
   注意不能提前太多，落针那一下要看得见，所以卡在 dive 起跑前后。 */
body.go .deckbox .arm{animation:arm-drop .8s cubic-bezier(.3,.86,.32,1) both,
  arm-out .34s ease-in 1.86s forwards}
@keyframes arm-out{to{opacity:0}}
body.go .stage::before,body.go .stage::after{animation:none; opacity:0;
  transition:opacity .5s .3s}
/* 兜底白幕：只在最后 0.2s 补一层，把标签涨大可能留下的边角抹平。
   它现在是收尾而不是主角，所以起得很晚、时间很短。 */
body.go::after{content:""; position:fixed; inset:0; background:var(--paper);
  opacity:0; z-index:99; animation:flash .2s linear 2.78s forwards; pointer-events:none}
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
        <span class="knob"></span><span class="t">start</span><span class="trk"></span></button>
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
