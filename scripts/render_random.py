"""渲染独立的「今天听点别的」随机页（site/random.html）+ 精简池 JSON（site/pool.min.json）。

设计延续日报页的工程 / 网格视觉语言（Inter 极细 + Space Mono、方角、发丝线、方格纸、LCD 绿），
但交互是"拆盲盒"：一次只给一首、巨型摇一摇按钮 + LCD 洗牌动画 + 30s 试听自动播。
纯前端随机（读 pool.min.json），零后端。收藏是**本次会话的临时篮子**（sessionStorage `md_basket`，
关掉标签页即清空），与日报页那份长期收藏（localStorage `md_hearts`）完全隔离、互不写入。

公开接口：
  build_pool_json(pool)  -> str   精简 JSON（供 site/pool.min.json）
  build_html(n_total)    -> str   页面
"""
from __future__ import annotations

import json

from lightbox import LIGHTBOX_CSS, LIGHTBOX_HTML, lightbox_js
from netease_open import NETEASE_OPEN_JS
from render_grid import (CSS, ICON_CAT, ICON_BOWL, ICON_BALL, ICON_PLAY, ICON_PAUSE,
                         ICON_HEART, KNOB, TAG_MAP, _esc)

# 精简字段：只留展示要用的（体积从 ~1.5MB 降到 ~400KB）
FIELDS = ("id", "title", "artist", "year", "album", "genres", "mood_tags",
          "artist_oneliner", "why", "scene", "bpm_band")


def build_pool_json(pool: list[dict]) -> str:
    out = []
    for t in pool:
        d = {k: t.get(k) for k in FIELDS if t.get(k) not in (None, "", [])}
        d["c"] = t.get("_cover", "")       # cover
        d["p"] = t.get("_preview", "")     # preview
        d["a"] = t.get("_apple", "")       # apple url
        out.append(d)
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))


EXTRA_CSS = """
/* ── 随机页专属 ───────────────────────────────────────────── */
body{padding-bottom:76px}
.dice-wrap{border:1px solid var(--g300); background:var(--paper); margin-top:var(--sp-md);
  display:flex; flex-wrap:wrap; align-items:stretch}
.filters{display:flex; flex-wrap:wrap; gap:0; flex:1; min-width:260px}
.fsel{position:relative; border-right:1px solid var(--g100); flex:1 1 33%; min-width:110px}
.fsel select{appearance:none; width:100%; height:100%; min-height:72px; padding:10px 28px 10px 14px;
  border:none; background:transparent; color:var(--ink); cursor:pointer;
  font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase; letter-spacing:.04em}
.fsel::after{content:"▾"; position:absolute; right:11px; top:50%; transform:translateY(-50%);
  font-family:var(--mono); font-size:var(--fs-10); color:var(--g600); pointer-events:none}
.fsel .lbl{position:absolute; left:14px; top:6px; font-family:var(--mono); font-size:9px;
  color:var(--g500); text-transform:uppercase; letter-spacing:.1em; pointer-events:none}
.fsel select{padding-top:20px}
#roll{flex:0 0 auto; min-width:clamp(160px,26vw,260px); border:none; cursor:pointer; position:relative;
  background:var(--ink); color:var(--white); font-family:var(--mono); font-size:var(--fs-20);
  text-transform:uppercase; letter-spacing:.08em; padding:14px 24px; display:flex; overflow:hidden;
  align-items:center; justify-content:center; gap:13px; min-height:72px;
  transition:background .2s, transform .1s}
#roll:hover{background:var(--g1000)}
#roll:active{transform:scale(.985)}
#roll.rolling{background:var(--green-d)}
#roll .k{font-size:var(--fs-10); color:var(--g300); letter-spacing:.06em; position:relative; z-index:1;
  /* 按钮已改 align-items:center，三个不同字号的元素靠中线共线，不再需要逐个 top 补偿 */
  line-height:1}
#roll .lab{position:relative; z-index:1; line-height:1}
/* 按下时从中心荡开的波纹 */
#roll::after{content:""; position:absolute; left:50%; top:50%; width:34px; height:34px;
  border-radius:50%; border:1px solid rgba(255,255,255,.5);
  transform:translate(-50%,-50%) scale(0); opacity:0}
#roll.ping::after{animation:ping .5s ease-out}
@keyframes ping{0%{transform:translate(-50%,-50%) scale(.5);opacity:.75}
  100%{transform:translate(-50%,-50%) scale(3.2);opacity:0}}
/* 图标 */
#roll .dice{width:30px; height:30px; display:inline-block; flex:none; position:relative; z-index:1}
#roll .dice .vinyl{transform-box:fill-box; transform-origin:center; will-change:transform}
#roll .dice{transition:transform .3s cubic-bezier(.34,1.4,.64,1)}
#roll:hover .dice .vinyl{animation:vinyl-idle 6s linear infinite}
#roll:active .dice{transform:scale(.93)}
/* 转动：由慢到快加速起转（spin-up），到位后维持高速 */
#roll.rolling .dice .vinyl{animation:vinyl-roll 2.34s linear both}
@keyframes vinyl-idle{to{transform:rotate(360deg)}}
/* 一条动画走完「由慢到快 → 匀速 → 惯性收停」；
   速度全由关键帧间距控制(timing 用 linear)，末段间距递减到近 0 → 停得顺滑不打顿。 */
@keyframes vinyl-roll{
  0%{transform:rotate(0)}        8%{transform:rotate(20deg)}
  18%{transform:rotate(86deg)}   30%{transform:rotate(264deg)}
  42%{transform:rotate(572deg)}  55%{transform:rotate(990deg)}
  68%{transform:rotate(1474deg)} 80%{transform:rotate(1937deg)}
  88%{transform:rotate(2244deg)} 94%{transform:rotate(2420deg)}
  98%{transform:rotate(2504deg)} 99%{transform:rotate(2515deg)}
  100%{transform:rotate(2520deg)}}   /* 2520 = 360×7，正好整圈：摘掉 .rolling 时角度不跳 */
/* 高光弧在高速时更亮（转起来的感觉） */
#roll.rolling .dice .shine{animation:shine-hot .34s ease-in-out infinite}
@keyframes shine-hot{0%,100%{stroke-opacity:.38}50%{stroke-opacity:.85}}

.hint{font-family:var(--mono); font-size:var(--fs-10); color:var(--g600); margin-top:8px}
.hint b{color:var(--ink); font-weight:400}
.hint kbd{border:1px solid var(--g300); background:var(--white); vertical-align:middle;
  /* 文字在方框正中：inline-flex 居中 + line-height:1，别靠 padding 和 line-height 凑
     （之前外框 22.2px、line-height 18.2px，余量上下不等，字就偏上了） */
  display:inline-flex; align-items:center; justify-content:center;
  min-width:1.9em; height:1.55em; padding:0 .45em; line-height:1;
  position:relative; top:-.05em}

/* 单张大卡 */
.card{border:1px solid var(--g300); background:var(--paper); margin-top:var(--sp-md);
  position:relative; overflow:hidden}
/* ══ 唱针落针 + 唱片起转（约 2.6s）：唱盘起转→加速→唱臂摆入→落针"咔"→定格成封面→信息沿轨迹浮出 ══ */
.card.in{animation:card-in .38s cubic-bezier(.16,1,.3,1) both, tt-thud .2s ease-out 1.75s both}
@keyframes card-in{from{opacity:0; transform:translateY(10px)}to{opacity:1; transform:none}}
@keyframes tt-thud{0%{transform:none}34%{transform:translateY(2px)}100%{transform:none}}

/* 唱盘：一张真在转的黑胶（JS 插入 .tt 到封面框） */
.card .big-art{position:relative; z-index:2}
.tt{position:absolute; inset:0; z-index:3; pointer-events:none; display:grid; place-items:center;
  overflow:hidden; background:var(--ink);
  animation:tt-out .2s ease-out 1.75s forwards}
/* ── 唱盘：先摆一个正方形「转盘舞台」.deck，所有几何都相对它 ──
   为什么要 deck：.tt 铺满封面框，而封面框不保证正方；直接在非正方容器上
   写 inset% + border-radius:50% 会压出椭圆(之前毡垫圈就是这么歪的)。 */
.tt .deck{position:relative; width:100%; aspect-ratio:1; max-height:100%}
@supports (container-type:size){
  .tt{container-type:size}
  .tt .deck{width:min(100cqw,100cqh); height:min(100cqw,100cqh); aspect-ratio:auto}
}
/* 转盘底座 + 毡垫同心圈线（在正方 deck 上，所以是真圆） */
.tt .deck::before{content:""; position:absolute; inset:2%; border-radius:50%;
  background:radial-gradient(circle at 50% 50%, #303030 0 62%, #232323 63% 100%);
  border:1px solid rgba(255,255,255,.07);
  box-shadow:inset 0 0 20px rgba(0,0,0,.55)}
.tt .deck::after{content:"";position:absolute; inset:9%; border-radius:50%;
  background:repeating-radial-gradient(circle at 50% 50%,
    rgba(255,255,255,.045) 0 1px, transparent 1px 8px)}
/* 左下转速标记 + 右下电源灯（挂 .tt 而非 deck，贴在方框角上） */
.tt::after{content:"33⅓"; position:absolute; left:7%; bottom:5%; font-family:var(--mono);
  font-size:9px; letter-spacing:.08em; color:rgba(255,255,255,.38); z-index:4}
.tt .led{position:absolute; right:8%; bottom:6%; width:5px; height:5px; border-radius:50%;
  background:var(--orange); box-shadow:0 0 6px var(--orange); z-index:4;
  animation:led-on .34s steps(1) .2s infinite}
@keyframes led-on{50%{opacity:.35}}
@keyframes tt-out{to{opacity:0; visibility:hidden}}
/* 唱片：占 deck 80% 居中(半径 r=0.40·deck)，.dwrap 只管「放上去」的位移，
   .disc 只管自转 —— 分层是为了两者不抢同一个 transform。 */
.tt .dwrap{position:absolute; left:10%; top:10%; width:80%; height:80%; z-index:2;
  animation:disc-place .4s cubic-bezier(.22,1.12,.3,1) both}
@keyframes disc-place{0%{opacity:0; transform:translateY(-30%) scale(.86)}
  72%{opacity:1; transform:translateY(1.5%) scale(1.012)}
  100%{opacity:1; transform:none}}
.tt .disc{width:100%; height:100%; border-radius:50%; position:relative;
  background:
    repeating-radial-gradient(circle at 50% 50%, rgba(255,255,255,.09) 0 1px, transparent 1px 4px),
    radial-gradient(circle closest-side at 50% 50%, #f5f5f5 0 30%, #191919 30.5% 100%);
  box-shadow:0 0 0 1px rgba(255,255,255,.2), inset 0 0 24px rgba(0,0,0,.72);
  will-change:transform;
  animation:disc-up 1.45s cubic-bezier(.4,0,.75,.5) .3s both, disc-lit .3s ease-out 1.42s both}
@keyframes disc-up{
  0%{transform:rotate(0)} 12%{transform:rotate(20deg)} 28%{transform:rotate(88deg)}
  46%{transform:rotate(256deg)} 64%{transform:rotate(572deg)} 80%{transform:rotate(990deg)}
  100%{transform:rotate(1440deg)}}
@keyframes disc-lit{0%{filter:brightness(1)}40%{filter:brightness(1.26)}100%{filter:brightness(1)}}
/* 纸标签上的转速字：沿标签内圈弧排（真黑胶就是围着中心绕的，不横在正中间），随盘同转。
   CSS 做不到文字沿圆弧，故内嵌一小段 SVG textPath。class 用 vlbl，别撞筛选器的 .lbl。 */
.tt .disc .vlbl{position:absolute; left:50%; top:50%; width:44%; height:44%;
  transform:translate(-50%,-50%); z-index:2; pointer-events:none}
.tt .disc .vlbl{shape-rendering:geometricPrecision}
.tt .disc .vlbl text{font-size:1.6px; fill:#242424; letter-spacing:.05px;
  font-family:ui-monospace,Menlo,monospace;
  /* 关掉字形微调：小号字旋转时 hinting 会逐帧改变对齐网格，看着就是抖 */
  text-rendering:geometricPrecision}
/* 固定反光带：挂在不自转的 .dwrap 上，所以不会变成一根转动的秒针 */
.tt .dwrap::after{content:""; position:absolute; inset:0; border-radius:50%; pointer-events:none;
  background:linear-gradient(118deg, transparent 28%, rgba(255,255,255,.13) 43%,
    rgba(255,255,255,.035) 53%, transparent 66%)}
/* ── 唱臂：支点在右下(0.955,0.730)，臂长 L=0.385·deck，向左上伸 ──
   符号约定(实测 DOMMatrix 核过)：支点在右、针尖在左时，CSS 角度【减小】才是针尖落下。
   停机位 88° → 针尖在 1.17r(盘外)；落针位 73° → 针尖在 0.92r(外圈第一道纹)。
   所以动作是 88°→73°「放上去」并停住，绝不再是反着抬起飞离。 */
.tt .arm{position:absolute; right:3%; bottom:5.6%; width:28.9%; height:2.8%; z-index:3;
  transform-origin:100% 50%; transform:rotate(80deg);
  animation:arm-down .85s cubic-bezier(.3,.86,.32,1) .55s both}
@keyframes arm-down{
  0%{transform:rotate(80deg)}                   /* 停机位：针尖在盘外 1.11r */
  70%{transform:rotate(57.2deg)}                /* 落到外圈，略过冲 */
  86%{transform:rotate(59.4deg)}                /* 一次很轻的回弹 */
  100%{transform:rotate(58.5deg)}}              /* 停在唱片上 0.92r，不移开 */
.tt .arm i{position:absolute; left:6%; right:8%; top:22%; bottom:22%; border-radius:2px;
  background:linear-gradient(180deg,#efebe3,#cbc5b9 55%,#9b958a);
  box-shadow:0 1px 2px rgba(0,0,0,.5)}                             /* 细管臂身 */
.tt .arm i::before{content:""; position:absolute; right:-34%; top:-190%; width:30%; height:480%;
  border-radius:50%; background:linear-gradient(180deg,#e2ddd3,#8e887e)}   /* 支点端配重 */
.tt .arm b{position:absolute; left:0; top:-70%; width:17%; height:240%; border-radius:1px;
  background:linear-gradient(180deg,#f6f3ed,#c3bdb1)}                      /* 拾音头 */
.tt .arm b::after{content:""; position:absolute; left:14%; bottom:-46%; width:34%; height:46%;
  background:#8e887e}                                                      /* 针尖 */
/* 落针冲击：圆心就落在【落针位的针尖】(0.842,0.362)——之前它离针尖 88px，
   所以看着就是"一个白圈莫名放大"。现在它和针尖同点，读作针尖触盘。 */
.tt .drop{position:absolute; left:81.9%; top:68.4%; width:13%; height:13%;
  margin-left:-6.5%; margin-top:-6.5%; border-radius:50%; z-index:4; opacity:0;
  border:1px solid rgba(255,255,255,.62);
  animation:drop-ring .3s ease-out 1.42s both}
@keyframes drop-ring{0%{opacity:.8; transform:scale(.5)}70%{opacity:.3}100%{opacity:0; transform:scale(1.55)}}

/* 封面：唱盘隐去的同时"定格"成专辑封面 */
.card .big-art .cover{animation:cover-set .5s cubic-bezier(.2,1.3,.32,1) 1.75s both}
@keyframes cover-set{0%{opacity:0; transform:scale(1.1) rotate(-4deg); filter:saturate(.5)}
  60%{opacity:1; transform:scale(1.01) rotate(.6deg); filter:saturate(1)}
  100%{opacity:1; transform:none}}
/* 播放键在落针后出现（唱片已经在放了） */
.card.in .big-art .pbtn{animation:pbtn-in .3s ease-out 2s both}
@keyframes pbtn-in{from{opacity:0; transform:translateY(5px) scale(.86)}to{opacity:1; transform:none}}

/* 信息：沿唱针"读取"的方向由内向外逐行浮出 */
.card.in .c-title{animation:read-in .44s cubic-bezier(.16,1,.3,1) 1.6s both}
.card.in .c-artist{animation:read-in .4s cubic-bezier(.16,1,.3,1) 2.14s both}
.card.in .c-meta{animation:read-in .4s cubic-bezier(.16,1,.3,1) 1.72s both}
.card.in .tags{animation:read-in .4s cubic-bezier(.16,1,.3,1) 1.8s both}
.card.in .c-one{animation:read-in .4s cubic-bezier(.16,1,.3,1) 1.88s both}
.card.in .c-why{animation:read-in .44s cubic-bezier(.16,1,.3,1) 1.96s both}
.card.in .c-scene{animation:read-in .4s cubic-bezier(.16,1,.3,1) 2.06s both}
.card.in .c-links{animation:read-in .4s cubic-bezier(.16,1,.3,1) 2.14s both}
@keyframes read-in{from{opacity:0; transform:translateX(-10px)}
  to{opacity:1; transform:none}}
/* 标题打字机光标：闪三下后 content 清空（不占位） */
.card.in .c-title::after{content:"\\258b"; color:var(--orange); margin-left:3px;
  animation:cur-blink .32s steps(1) 1.7s 3 both, cur-clear .01s linear 2.68s forwards}
@keyframes cur-blink{50%{opacity:0}}
@keyframes cur-clear{to{content:""; opacity:0; margin-left:0; font-size:0}}
.card.in .bpm{animation:bpm-lit .44s ease-out 2.28s both}
@keyframes bpm-lit{from{border-left-color:var(--g300)}
  45%{border-left-color:var(--bc,var(--g300)); background:rgba(0,0,0,.05)}
  to{border-left-color:var(--bc,var(--g300)); background:transparent}}
@keyframes rise{from{opacity:0; transform:translateY(8px)}to{opacity:1; transform:none}}
.card .c-top{display:flex; align-items:center; justify-content:space-between;
  padding:12px 16px; border-bottom:1px solid var(--g100)}
.card .c-no{font-family:var(--mono); font-size:var(--fs-10); color:var(--g600);
  text-transform:uppercase; letter-spacing:.1em}
.card .c-tag{display:inline-flex; gap:8px; align-items:center}
.card .c-main{display:flex; gap:var(--sp-lg); padding:var(--sp-lg); flex-wrap:wrap}
.card .big-art{position:relative; width:clamp(150px,22vw,232px); aspect-ratio:1; flex:none;
  align-self:flex-start}   /* 不加这行会被 flex 纵向拉伸成 232×342，圆变椭圆 */
.card .big-art .cover{width:100%; height:100%; object-fit:cover; display:block;
  background:var(--g100); border:1px solid var(--g100)}
.card .big-art .cover.ph{display:grid; place-items:center; font-family:var(--mono);
  font-size:var(--fs-40); font-weight:400; color:var(--white); background:var(--ink); border:none;
  background-image:repeating-linear-gradient(45deg,rgba(255,255,255,.06) 0 8px,transparent 8px 16px)}
.card .big-art .pbtn{left:10px; bottom:10px; width:38px; height:38px}
.card .big-art .pbtn svg{width:15px; height:15px}
.card .c-hd{flex:1; min-width:240px; display:flex; flex-direction:column; position:relative}
/* 读入前的占位骨架（等文字到位就淡掉），让右半边不至于空一大片 */
.card.in .c-hd::before{content:""; position:absolute; inset:0; pointer-events:none; z-index:0;
  background:
    linear-gradient(rgba(15,14,18,.075),rgba(15,14,18,.075)) 0 7px/58% 28px no-repeat,
    linear-gradient(rgba(15,14,18,.06),rgba(15,14,18,.06)) 0 48px/30% 11px no-repeat,
    linear-gradient(rgba(15,14,18,.05),rgba(15,14,18,.05)) 0 71px/44% 9px no-repeat,
    linear-gradient(rgba(15,14,18,.05),rgba(15,14,18,.05)) 0 96px/86% 9px no-repeat,
    linear-gradient(rgba(15,14,18,.05),rgba(15,14,18,.05)) 0 112px/68% 9px no-repeat;
  animation:skel-out .3s ease-out 1.6s both}
.card.in .c-hd::after{content:""; position:absolute; inset:0 -20% 0 0; pointer-events:none; z-index:1;
  background:linear-gradient(104deg, transparent 34%, rgba(255,255,255,.62) 50%, transparent 66%);
  background-size:180% 100%;
  animation:skel-sweep 1.05s linear infinite, skel-out .3s ease-out 1.6s both}
@keyframes skel-sweep{from{background-position:-80% 0}to{background-position:180% 0}}
@keyframes skel-out{to{opacity:0}}
.card .c-hd>*{position:relative; z-index:2}
.card .c-title{font-size:var(--fs-30); font-weight:100; line-height:1.32; letter-spacing:-.015em;
  padding-bottom:.12em; overflow:visible}
.card .c-artist{font-family:var(--mono); font-size:var(--fs-15); text-transform:uppercase;
  word-break:break-word; line-height:1.5;
  color:var(--g900); margin-top:8px; letter-spacing:.1em}
.card .c-meta{font-family:var(--mono); font-size:var(--fs-10); color:var(--g600); margin-top:8px}
.card .c-meta .bpm{display:inline-block; margin-left:9px; padding:1px 7px 1px 6px;
  border:1px solid var(--g200); border-left:3px solid var(--bc,var(--g300));
  color:var(--g900); letter-spacing:.04em; white-space:nowrap}
.card .c-one{font-family:var(--mono); font-size:var(--fs-10); color:var(--g600);
  line-height:1.7; margin-top:14px}
.card .c-why{font-size:var(--fs-20); font-weight:300; line-height:1.5; margin-top:10px}
.card .c-scene{font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase;
  color:var(--g900); margin-top:14px}
.card .c-scene .k{color:var(--orange)}
.card .c-links{display:flex; gap:8px; margin-top:auto; padding-top:18px; align-items:center; flex-wrap:wrap}
.card.empty .c-main{color:var(--g500); justify-content:center; text-align:center;
  font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase; padding:var(--sp-xl)}

/* 今晚的篮子：临时收藏浮条（贴在 now-playing 条上方；空时不显示）*/
#basket{position:fixed; left:0; right:0; bottom:76px; z-index:1150; display:none;
  background:var(--white); border-top:1px solid var(--g300); border-bottom:1px solid var(--g100);
  padding:10px clamp(16px,4vw,52px); align-items:center; gap:clamp(8px,1.4vw,16px);
  transform:translateY(100%); transition:transform .3s cubic-bezier(.22,1.2,.36,1)}
#basket.on{display:flex; transform:none}
#basket .bk-paw{width:22px; height:20px; flex:none; image-rendering:pixelated}
#basket .bk-paw{color:var(--ink)}
#basket.pop .bk-paw{animation:bk-stamp .42s cubic-bezier(.34,1.56,.64,1)}
@keyframes bk-stamp{0%{transform:translateY(-7px) rotate(-8deg)}55%{transform:translateY(2px) rotate(3deg)}100%{transform:none}}
#basket .bk-txt{font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase;
  color:var(--g900); letter-spacing:.04em; flex:none}
#basket .bk-n{display:inline-block; min-width:1.4em; text-align:center; color:var(--ink);
  font-size:var(--fs-20); font-weight:700; letter-spacing:0}
#basket.pop .bk-n{animation:bk-bump .38s cubic-bezier(.34,1.56,.64,1)}
@keyframes bk-bump{0%{transform:scale(1)}45%{transform:scale(1.45)}100%{transform:scale(1)}}
#basket .bk-list{flex:1; min-width:0; font-family:var(--mono); font-size:var(--fs-10);
  color:var(--g600); letter-spacing:.04em; white-space:nowrap; overflow:hidden; text-overflow:ellipsis}
#basket .bk-btn{font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase;
  padding:7px 11px; cursor:pointer; border:1px solid var(--ink); background:var(--ink);
  color:var(--white); flex:none; transition:opacity .2s}
#basket .bk-btn.line{background:transparent; color:var(--ink)}
#basket .bk-btn:hover{opacity:.7}
body.has-basket{padding-bottom:134px}
@media(max-width:720px){
  #basket .bk-list{display:none}
  #basket{gap:8px; padding:9px 16px}
}

/* 导出面板（临时篮子）*/
#bk-box{border:1px solid var(--g300); background:var(--white); margin-top:var(--sp-md); display:none}
#bk-box.on{display:block}
#bk-box .h{display:flex; justify-content:space-between; align-items:center; padding:12px 16px;
  border-bottom:1px solid var(--g100); font-family:var(--mono); font-size:var(--fs-10);
  text-transform:uppercase; letter-spacing:.04em}
#bk-box .h span{color:var(--g600); text-transform:none}
#bk-box .in{padding:var(--sp-md)}
#bk-box p{font-family:var(--mono); font-size:var(--fs-10); color:var(--g600); margin-bottom:10px}
#bk-box pre{border:1px solid var(--g100); background:var(--paper); padding:14px;
  font-family:var(--mono); font-size:var(--fs-10); line-height:1.8; white-space:pre-wrap;
  max-height:260px; overflow:auto}

/* 刚听过 */
.recent{border-top:1px solid var(--g300); border-left:1px solid var(--g300);
  display:grid; grid-template-columns:repeat(4,1fr); margin-top:var(--sp-md)}
.recent .r{border-right:1px solid var(--g300); border-bottom:1px solid var(--g300);
  padding:11px 13px; cursor:pointer; background:var(--paper); transition:background .15s; min-width:0}
.recent .r:hover{background:var(--white)}
.recent .r .rt{font-size:var(--fs-15); font-weight:300; white-space:nowrap;
  overflow:hidden; text-overflow:ellipsis}
.recent .r .ra{font-family:var(--mono); font-size:9px; color:var(--g600); letter-spacing:.09em;
  text-transform:uppercase; margin-top:4px; line-height:1.45;
  /* 长艺人名（最长 45 字符）不要一刀切省略号，允许折到第二行 */
  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden}
@media(max-width:720px){
  .recent{grid-template-columns:repeat(2,1fr)}
  #roll{flex:1 1 100%; min-width:0}
  .fsel{flex:1 1 50%}
}

/* ── 竖屏（手机）适配，基准 iPhone 390×844 ──
   实测问题：①三个筛选各占一整行，光筛选就吃掉半屏 ②「另起一首」按钮 72px 偏高
   ③the pick 里封面 232px 与右侧文字并排，两边都憋 ④hint 一行字折成三行 */
@media(max-width:520px){
  .wrap{padding-inline:16px}
  .nav .wrap{height:52px}
  .brand{font-size:14px; gap:8px; white-space:nowrap; flex:none}
  .brand .sq{width:11px; height:11px}
  .nav .serial{gap:10px; flex-wrap:nowrap; font-size:9px; overflow:hidden}
  .nav .serial>*:nth-child(n+3){display:none}
  .hero{padding:20px 0 14px; gap:12px}
  .hero .h-l h1{font-size:34px}
  .hero .h-r .big{font-size:30px; display:inline-block; margin-right:6px}
  /* 筛选：改 grid 两列（mood/genre 并排、decade 跨两列）。
     不能用 flex:1 1 50% —— 实测父级 min-width:0 后 .fsel 被压成 1px 宽，
     select 文字整个挤没、只剩 ::after 的 ▾ 箭头。grid 显式分列才稳。 */
  .filters{display:grid; grid-template-columns:1fr 1fr; min-width:0; flex:none; width:100%}
  .fsel{min-width:0; border-bottom:1px solid var(--g100)}
  .fsel:nth-child(2){border-right:none}
  .fsel:nth-child(3){grid-column:1 / -1; border-right:none; border-bottom:none}
  .fsel select{min-height:56px; padding:20px 26px 6px 12px; font-size:13px}
  .fsel .lbl{left:12px; top:6px}
  #roll{min-height:58px; padding:12px 16px; gap:10px; font-size:14px; width:100%}
  #roll .dice{width:26px; height:26px}
  .hint{font-size:9px; line-height:1.9}
  /* the pick：封面横铺在上、文字在下，别在 390px 里硬并排 */
  .card .c-main{flex-direction:column; gap:14px; padding:14px}
  .card .big-art{width:100%; max-width:none; aspect-ratio:1}
  .card .c-hd{min-width:0}
  .card .c-title{font-size:26px}
  .card .c-links{gap:6px}
  .card .c-links>*{flex:1 1 calc(50% - 3px); justify-content:center; text-align:center}
  .recent{grid-template-columns:1fr}
  #basket{bottom:70px; padding:8px 14px}
  footer{flex-direction:column; gap:6px; text-align:center}
}
@media(prefers-reduced-motion:reduce){
  .card,.card.in,.card .big-art .cover,.card.in .c-title,.card.in .c-artist,.card.in .c-meta,
  .card.in .tags,.card.in .c-one,.card.in .c-why,.card.in .c-scene,.card.in .c-links,
  .card.in .c-hd::before,.card.in .c-hd::after,
  .card.in .bpm,.card.in .big-art .pbtn{
    opacity:1; transform:none; transition:none; animation:none; filter:none; clip-path:none}
  .tt{display:none}
  .card.in .c-title::after{content:""; animation:none}
  .card.in .big-art .pbtn{animation:none; opacity:1; transform:none}
  #roll.ping::after{animation:none; display:none}
  #roll .dice g{animation:none !important}
  #roll.rolling .dice{animation:none}
  #roll.rolling .dice .vinyl{animation:none}
}
"""

ICON_DICE = (
    # 真黑胶（不是靶心）：深色盘面 + 疏密不均的沟槽 + 高光反射弧 + 中心纸标签(带小孔)
    '<svg class="dice" viewBox="0 0 34 34" aria-hidden="true">'
    '<g class="vinyl">'
    # 盘面（深色实心，这是"黑胶"的关键——靶心版是空心线圈才像靶）
    '<circle cx="17" cy="17" r="15.6" fill="#141414" stroke="#fff" stroke-width="1.1" stroke-opacity=".55"/>'
    # 沟槽：疏密不均的细弧（真唱片的纹理不是等距同心圆）
    '<g fill="none" stroke="#fff" stroke-linecap="round">'
    '<circle cx="17" cy="17" r="13.4" stroke-width=".5" stroke-opacity=".2"/>'
    '<circle cx="17" cy="17" r="12.4" stroke-width=".5" stroke-opacity=".13"/>'
    '<circle cx="17" cy="17" r="10.9" stroke-width=".5" stroke-opacity=".22"/>'
    '<circle cx="17" cy="17" r="9.6" stroke-width=".5" stroke-opacity=".12"/>'
    '<circle cx="17" cy="17" r="8.4" stroke-width=".5" stroke-opacity=".2"/>'
    '</g>'
    # 高光反射弧（唱片受光的那道亮弧，让它一眼是黑胶不是靶心）
    '<path class="shine" d="M6.6 9.4A14 14 0 0 1 24.6 6.2" fill="none" stroke="#fff"'
    '  stroke-width="1.5" stroke-opacity=".38" stroke-linecap="round"/>'
    # 中心纸标签（橙色）+ 主轴小孔
    '<circle cx="17" cy="17" r="5.4" fill="#f5f5f5"/>'
    '<circle cx="17" cy="17" r="5.4" fill="none" stroke="#fff" stroke-width=".6" stroke-opacity=".25"/>'
    # 标签内两圈细压印环 + 主轴点。
    # 不在这里放弧排转速字：图标 30px、白标签实测才 10px 宽，字环要 23px，塞不下。
    # 「绕着圈的转速字」放在够大的 the pick 唱片标签上（那里 75px）。
    '<circle cx="17" cy="17" r="3.7" fill="none" stroke="#b9b3a8" stroke-width=".3"/>'
    '<circle cx="17" cy="17" r="2.4" fill="none" stroke="#cbc5ba" stroke-width=".28"/>'
    '<circle cx="17" cy="17" r=".6" fill="#a8a29a"/>'
    '</g>'
    '</svg>')

JS = """
const $=(s)=>document.querySelector(s);
let POOL=[], seen=[], cur=null, recent=[];
const au=new Audio();
const np=$('#np'), NC=$('#np-cover'), NT=$('#np-title'), NA=$('#np-artist'),
      NBAR=$('#np-bar'), NFILL=$('#np-fill'), NTIME=$('#np-time'), NTOG=$('#np-toggle');
// 临时篮子：sessionStorage（关掉标签页即清空），与日报页 localStorage 的 md_hearts 完全隔离
const KEY='md_basket';
const ld=()=>{try{return JSON.parse(sessionStorage.getItem(KEY)||'[]')}catch(e){return []}};
const sv=(a)=>{try{sessionStorage.setItem(KEY,JSON.stringify(a))}catch(e){}};
let hearts=ld();
const BK=()=>document.getElementById('basket');
function bkRender(pop){
  const el=BK(); if(!el)return;
  const n=document.getElementById('bk-n'), li=document.getElementById('bk-list');
  if(n)n.textContent=hearts.length;
  if(li)li.textContent=hearts.length?hearts.slice(-4).reverse().join('  ·  '):'';
  const on=hearts.length>0;
  el.classList.toggle('on',on);
  document.body.classList.toggle('has-basket',on);
  if(pop&&on){el.classList.remove('pop');void el.offsetWidth;el.classList.add('pop');}
  const box=document.getElementById('bk-box');
  if(box&&!hearts.length)box.classList.remove('on');
}
const fmt=(s)=>{if(!isFinite(s)||s<0)s=0;s=Math.floor(s);return Math.floor(s/60)+':'+String(s%60).padStart(2,'0')};

// LCD boot
const boot=$('#boot'), BOOT=boot?boot.dataset.text:'';
if(boot){let i=0;boot.textContent='';(function ty(){if(i<=BOOT.length){boot.innerHTML=BOOT.slice(0,i)+'<span class="cur">\\u258b</span>';i++;setTimeout(ty,26);}else{boot.textContent=BOOT;}})();}

function lcd(msg){const b=$('#boot');if(b)b.textContent=msg;}

function match(t){
  const m=$('#f-mood').value, g=$('#f-genre').value, d=$('#f-decade').value;
  if(m && !(t.mood_tags||[]).map(tgm).includes(m))return false;
  if(g && !((t.genres||[]).map(x=>x.toLowerCase()).includes(g)))return false;
  if(d){const y=parseInt(t.year||'0',10); if(!y||Math.floor(y/10)*10!==parseInt(d,10))return false;}
  return true;
}
function pool(){return POOL.filter(match)}

// 浮层要用的 data-*（与日报 _lb_data 同一套字段，浮层组件是共用的）
function lbData(t){
  const A=(k,v)=>' data-'+k+'="'+String(v==null?'':v).replace(/&/g,'&amp;').replace(/"/g,'&quot;')+'"';
  const tags=[].concat((t.genres||[]).slice(0,3),(t.mood_tags||[]).slice(0,3)).map(tgm).join('|');
  return A('cover',t.c)+A('title',t.title)+A('artist',t.artist)+A('year',t.year)
       +A('album',t.album)+A('bpm',t.bpm_band||'')+A('tags',tags)
       +A('one',t.artist_oneliner||'')+A('why',t.why||'')+A('scene',t.scene||'')
       +A('apple',t.a||'')+A('spotify','https://open.spotify.com/search/'
         +encodeURIComponent((t.title||'')+' '+(t.artist||'')));
}

function render(t){
  const art=t.c?('<img class="cover" src="'+t.c+'" alt="">')
                :('<div class="cover ph">'+((t.artist||'?')[0]||'?').toUpperCase()+'</div>');
  const pb=t.p?('<button class="pbtn" id="cpb" type="button" aria-label="\\u8bd5\\u542c 30 \\u79d2">'+PLAY+PAUSE+'</button>'):'';
  // badge 优先显示当前筛选中的那个流派。否则筛 dream pop 时，主标签是别的流派的曲子
  // 会显示成「folktronica」「bedroom pop」，看着像筛选串味了（实测 151 首里 74 首如此）
  const gsel=$('#f-genre').value;
  const glist=(t.genres||['\\u2014']);
  const g0=(gsel&&glist.some(x=>x.toLowerCase()===gsel))
    ? glist.find(x=>x.toLowerCase()===gsel) : glist[0];
  const tags=[].concat((t.genres||[]).slice(1,3),(t.mood_tags||[]).slice(0,2))
    .map(x=>'<span class="tag">'+tgm(x)+'</span>').join('');
  const bpmC=(bb)=>{const n=String(bb||'').match(/\\d+/g); if(!n)return '';
    const m=(+n[0]+ +n[n.length-1])/2;
    return m<85?'#0071bb':m<105?'#006837':m<125?'#fab413':'#f05a24';};
  const meta=[t.year,t.album].filter(Boolean).join(' / ')
    +(t.bpm_band?('<span class="bpm" style="--bc:'+bpmC(t.bpm_band)+'">'+t.bpm_band+' bpm</span>'):'');
  const on=hearts.indexOf(t.title+' - '+t.artist)>=0?' on':'';
  const links=(t.a?'<a class="btn solid" href="'+t.a+'" target="_blank" rel="noopener">listen</a>':'')
    +'<a class="btn line" href="https://open.spotify.com/search/'+encodeURIComponent(t.title+' '+t.artist)+'" target="_blank" rel="noopener">spotify \\u2197</a>'
    +'<a class="btn line" href="https://music.163.com/#/search/m/?s='+encodeURIComponent(t.title+' '+t.artist)+'" target="_blank" rel="noopener"'
    +' data-nc="'+String(t.title+' '+t.artist).replace(/"/g,'&quot;')+'">netease \\u266b</a>'
    +'<button class="heart'+on+'" id="chz" type="button" data-k="'+(t.title+' - '+t.artist).replace(/"/g,'&quot;')+'" aria-label="\\u6536\\u85cf">'+HEART+'</button>';
  const card=$('#card');
  card.className='card';
  card.innerHTML='<div class="c-top"><span class="c-no">pick \\u00b7 '+String(seen.length).padStart(3,'0')+' / '+pool().length+'</span>'
    +'<span class="c-tag"><span class="m-code" style="background:'+knob(g0)+'">'+g0+'</span></span></div>'
    +'<div class="c-main"><div class="big-art cover-zoom" role="button" tabindex="0"'
    +' aria-label="\\u770b\\u5927\\u56fe\\u4e0e\\u8be6\\u60c5"'
    +lbData(t)+'>'+art+pb+'</div>'
    +'<div class="c-hd"><div class="c-title lc">'+t.title+'</div>'
    +'<div class="c-artist">'+t.artist+'</div><div class="c-meta">'+meta+'</div>'
    +'<div class="tags" style="margin-top:10px">'+tags+'</div>'
    +'<div class="c-one">'+(t.artist_oneliner||'')+'</div>'
    +'<div class="c-why">'+(t.why||'')+'</div>'
    +'<div class="c-scene"><span class="k">use \\u25b8</span> '+(t.scene||'')+'</div>'
    +'<div class="c-links">'+links+'</div></div></div>';
  // 唱针落针 + 唱片起转：封面框先放一张真在转的黑胶，唱臂摆入落针后定格成封面
  (function(){
    const art=card.querySelector('.big-art'); if(!art)return;
    const tt=document.createElement('div'); tt.className='tt';
    const LBL='<svg class="vlbl" viewBox="0 0 20 20" aria-hidden="true">'
      +'<defs><path id="dlbl" fill="none" d="M 10 5.1 A 4.9 4.9 0 1 1 9.99 5.1"/></defs>'
      +'<text><textPath href="#dlbl" startOffset="4%">'
      +'33\u2153 RPM \u00b7 LONG PLAY</textPath></text>'
      +'<circle cx="10" cy="10" r=".5" fill="#a8a29a"/></svg>';
    tt.innerHTML='<div class="deck"><div class="dwrap"><div class="disc">'+LBL+'</div></div>'
      +'<div class="arm"><i></i><b></b></div><span class="drop"></span></div>'
      +'<span class="led"></span>';
    art.appendChild(tt);
    setTimeout(()=>tt.remove(), 2050);
  })();
  requestAnimationFrame(()=>card.classList.add('in'));
  const pb2=$('#cpb'); if(pb2)pb2.addEventListener('click',()=>toggle(t));
  const hz=$('#chz'); if(hz)hz.addEventListener('click',()=>{
    const k=hz.dataset.k,i=hearts.indexOf(k);
    const added=i<0;
    if(i>=0)hearts.splice(i,1);else hearts.push(k);
    sv(hearts);hz.classList.toggle('on',hearts.indexOf(k)>=0);bkRender(added);});
  history.replaceState(null,'','?t='+encodeURIComponent(t.id));
}
function knob(s){s=s||'x';let n=0;for(const c of s)n+=c.charCodeAt(0);return KNOB[n%KNOB.length];}

function play(t){
  if(!t.p)return;
  au.src=t.p; cur=t;
  if(NC)NC.src=t.c||''; if(NT)NT.textContent=t.title; if(NA)NA.textContent=t.artist;
  if(np)np.classList.add('on'); au.play();
}
function toggle(t){ if(cur&&cur.id===t.id){ au.paused?au.play():au.pause(); } else play(t); }
au.addEventListener('timeupdate',()=>{if(au.duration&&NFILL){NFILL.style.width=(au.currentTime/au.duration*100)+'%';NTIME.textContent=fmt(au.currentTime)+' / '+fmt(au.duration);}});
function mark(on){const b=$('#cpb');if(b)b.classList.toggle('playing',on);if(np)np.classList.toggle('playing',on);}
au.addEventListener('play',()=>mark(true));
au.addEventListener('pause',()=>mark(false));
au.addEventListener('ended',()=>{mark(false);if(NFILL)NFILL.style.width='0%';});
if(NTOG)NTOG.addEventListener('click',()=>{if(!cur)return;au.paused?au.play():au.pause();});
if(NBAR)NBAR.addEventListener('click',(e)=>{if(!au.duration)return;const r=NBAR.getBoundingClientRect();au.currentTime=(e.clientX-r.left)/r.width*au.duration;});

function pushRecent(t){
  recent=[t].concat(recent.filter(x=>x.id!==t.id)).slice(0,8);
  $('#recent').innerHTML=recent.map(x=>'<div class="r" data-id="'+x.id+'"><div class="rt lc">'+x.title+'</div><div class="ra">'+x.artist+'</div></div>').join('');
  document.querySelectorAll('#recent .r').forEach(el=>el.addEventListener('click',()=>{
    const t2=POOL.find(y=>y.id===el.dataset.id); if(t2){render(t2);play(t2);}}));
}

function roll(){
  const list=pool();
  if(!list.length){ $('#card').className='card empty';
    $('#card').innerHTML='<div class="c-main">no track matches these filters \\u2014 \\u6362\\u4e2a\\u7b5b\\u9009\\u6761\\u4ef6\\u8bd5\\u8bd5</div>';
    lcd('0 tracks match \\u2014 loosen the filters'); return; }
  let fresh=list.filter(t=>seen.indexOf(t.id)<0);
  if(!fresh.length){ seen=[]; fresh=list; lcd('all '+list.length+' heard \\u2014 reshuffling the deck'); }
  const btn=$('#roll'); btn.classList.remove('rolling');
  void btn.offsetWidth;                       // 重启动画，连点不残留旧角度
  btn.classList.add('rolling');
  setTimeout(()=>btn.classList.remove('rolling'),2340);   // 与 vinyl-roll 同长，播完才摘
  const t0=Date.now(), spin=setInterval(()=>{
    const s=fresh[Math.floor(Math.random()*fresh.length)];
    lcd('\\u25b8 '+s.title+' \\u2014 '+s.artist);
    if(Date.now()-t0>820){
      clearInterval(spin);
      const t=fresh[Math.floor(Math.random()*fresh.length)];
      seen.push(t.id); lcd('picked \\u00b7 '+seen.length+' of '+list.length+' \\u00b7 press space to roll again');
      render(t); pushRecent(t); play(t);
    }
  },70);
}

function fill(sel,items,label){
  const el=$(sel);
  el.innerHTML='<option value="">'+label+'</option>'+items.map(x=>'<option value="'+x[0]+'">'+x[1]+'</option>').join('');
  el.addEventListener('change',()=>{ seen=[]; lcd('filter set \\u00b7 '+pool().length+' tracks in play'); });
}

fetch('pool.min.json').then(r=>r.json()).then(d=>{
  POOL=d;
  const mc={},gc={},dc={};
  // 气质按【映射后的名字】合并计数，避免「怀旧又现代」等同义变体重复出现
  d.forEach(t=>{(t.mood_tags||[]).forEach(m=>{const k=tgm(m);mc[k]=(mc[k]||0)+1});
    (t.genres||[]).forEach(g=>{g=g.toLowerCase();gc[g]=(gc[g]||0)+1});
    const y=parseInt(t.year||'0',10); if(y){const k=Math.floor(y/10)*10; dc[k]=(dc[k]||0)+1}});
  // 全部列出、按曲目数降序（曾只取 top18，池里 220 类流派有 202 类选不到）；
  // 只出现 1 次的长尾也保留——用户就是要靠它捞冷门
  const top=(o,n)=>Object.entries(o).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0]))
    .map(([k,v])=>[k,k+' ('+v+')']);
  fill('#f-mood',top(mc),'\\u5168\\u90e8\\u5fc3\\u60c5');
  fill('#f-genre',top(gc),'\\u5168\\u90e8\\u6d41\\u6d3e');
  fill('#f-decade',Object.keys(dc).sort().map(k=>[k,k+'s ('+dc[k]+')']),'\\u5168\\u90e8\\u5e74\\u4ee3');
  lcd(POOL.length+' tracks loaded \\u00b7 hit space or press the button — one pick at a time');
  const q=new URLSearchParams(location.search).get('t');
  const seed=q?POOL.find(t=>t.id===q):null;
  if(seed){seen.push(seed.id);render(seed);pushRecent(seed);}else{roll();}
});

(function(){
  const ex=document.getElementById('bk-export'), cl=document.getElementById('bk-clear'),
        box=document.getElementById('bk-box'), txt=document.getElementById('bk-text'),
        cp=document.getElementById('bk-copy');
  if(ex)ex.addEventListener('click',()=>{
    if(!hearts.length)return;
    txt.textContent='今晚的篮子 · MUSIC DAILY\\n'+hearts.join('\\n');
    box.classList.add('on'); box.scrollIntoView({behavior:'smooth',block:'center'});});
  if(cl)cl.addEventListener('click',()=>{
    hearts.length=0; sv(hearts); bkRender(false);
    document.querySelectorAll('.heart').forEach(h=>h.classList.remove('on'));});
  if(cp)cp.addEventListener('click',()=>{
    navigator.clipboard.writeText(txt.innerText).then(()=>{
      const o=cp.innerText; cp.innerText='copied \\u2713'; setTimeout(()=>cp.innerText=o,1600);});});
  bkRender(false);
})();

$('#roll').addEventListener('click',()=>{const b=$('#roll');b.classList.remove('ping');void b.offsetWidth;b.classList.add('ping');roll();});
document.addEventListener('keydown',(e)=>{
  const tag=(e.target.tagName||'').toLowerCase();
  if(tag==='input'||tag==='textarea'||tag==='select')return;
  if(e.code==='Space'){e.preventDefault();const b=$('#roll');b.classList.remove('ping');void b.offsetWidth;b.classList.add('ping');roll();}
  else if(e.key==='p'||e.key==='P'){if(cur)toggle(cur);}
});
"""


def build_html(n_total: int) -> str:
    import urllib.parse
    favicon = "data:image/svg+xml," + urllib.parse.quote(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<rect width="24" height="24" fill="#0f0e12"/>'
        '<rect x="5" y="5" width="14" height="14" fill="none" stroke="#f05a24" stroke-width="2"/></svg>')
    boot = f"loading {n_total} tracks…"
    js = (f"const TAGMAP={json.dumps(TAG_MAP, ensure_ascii=False)};\n"
          "const tgm=(x)=>TAGMAP[x]||TAGMAP[String(x).toLowerCase()]||x;\n"
          f"const KNOB={json.dumps(KNOB)};\n"
          f"const PLAY={json.dumps(ICON_PLAY)};\nconst PAUSE={json.dumps(ICON_PAUSE)};\n"
          f"const HEART={json.dumps(ICON_HEART)};\n") + JS
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0f0e12">
<meta name="description" content="从 {n_total} 首曲库里随手另起一首 · melody-first · mood-first">
<title>MUSIC DAILY · shuffle · 今天听点别的</title>
<link rel="icon" href="{favicon}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@100;300;400&family=Space+Mono:wght@400;700&family=Noto+Sans+SC:wght@100;300;400&display=swap" rel="stylesheet">
<style>{CSS}{EXTRA_CSS}{LIGHTBOX_CSS}</style>
</head>
<body>
<nav class="nav">
  <div class="wrap">
    <div class="brand"><span class="sq"></span>MUSIC DAILY</div>
    <div class="serial"><span>mode <b>shuffle</b></span><span>pool <b>{n_total}</b></span>
      <span><a href="daily.html" style="border-bottom:1px solid var(--g300)">← 今日精选</a></span></div>
  </div>
</nav>

<main class="wrap">
  <div class="hero">
    <div class="h-l">
      <h1 class="lc">今天听点别的</h1>
      <div class="en">shuffle · one pick at a time · from the whole pool</div>
    </div>
    <div class="h-r"><span class="big">{n_total}</span>tracks in pool<br>
      <a href="archive/index.html" style="border-bottom:1px solid var(--g300)">往期 archive ↗</a></div>
  </div>

  <div class="lcd">
    <div class="row1"><span class="dot"></span><span id="boot" data-text="{_esc(boot)}"></span>
      <div class="cat-wrap"><div class="cat-move">{ICON_CAT}</div><span class="prop bowl">{ICON_BOWL}</span><span class="prop ball">{ICON_BALL}</span></div></div>
  </div>

  <div class="dice-wrap">
    <div class="filters">
      <div class="fsel"><span class="lbl">mood</span><select id="f-mood"></select></div>
      <div class="fsel"><span class="lbl">genre</span><select id="f-genre"></select></div>
      <div class="fsel"><span class="lbl">decade</span><select id="f-decade"></select></div>
    </div>
    <button id="roll" type="button">{ICON_DICE}<span class="lab">另起一首</span><span class="k">space</span></button>
  </div>
  <div class="hint">按 <kbd>space</kbd> 另起一首 · <kbd>p</kbd> 播放/暂停 · 每首自动播 30 秒试听 · ♥ 丢进今晚的篮子（临时，不进日报收藏）</div>

  <div class="sect">the pick</div>
  <article class="card" id="card"><div class="c-main">rolling…</div></article>

  <div class="sect">刚听过 · recent</div>
  <div class="recent" id="recent"></div>

  <section id="bk-box">
    <div class="h">今晚的篮子 · 导出 <span>本次会话临时 · 关掉页面即清空 · 不进日报收藏</span></div>
    <div class="in">
      <p>复制下列清单 → 网易云 App「新建歌单 → 导入」。想长期留着，请去日报页用 ♥ 收藏。</p>
      <pre id="bk-text"></pre>
      <button class="btn solid" id="bk-copy" type="button" style="margin-top:12px">复制清单 / copy</button>
    </div>
  </section>

  <footer>
    <span>MUSIC DAILY · shuffle</span>
    <span><a href="daily.html" style="border-bottom:1px solid var(--g300)">今日精选 →</a></span>
    <span>cover &amp; preview via public music api · personal use</span>
  </footer>
</main>

<div id="basket" aria-live="polite">
  <svg class="bk-paw" viewBox="0 0 34 34" aria-hidden="true">
    <circle cx="17" cy="17" r="15.6" fill="#1a1a1a" stroke="currentColor" stroke-width="1.1" stroke-opacity=".5"/>
    <g fill="none" stroke="currentColor" stroke-opacity=".22">
      <circle cx="17" cy="17" r="13.4" stroke-width=".5"/><circle cx="17" cy="17" r="10.9" stroke-width=".5"/>
      <circle cx="17" cy="17" r="8.4" stroke-width=".5"/></g>
    <path d="M6.6 9.4A14 14 0 0 1 24.6 6.2" fill="none" stroke="#fff" stroke-width="1.4" stroke-opacity=".3" stroke-linecap="round"/>
    <circle cx="17" cy="17" r="5.4" fill="#f5f5f5"/>
    <circle cx="17" cy="17" r="3.7" fill="none" stroke="#b9b3a8" stroke-width=".3"/>
    <circle cx="17" cy="17" r="2.4" fill="none" stroke="#cbc5ba" stroke-width=".28"/>
    <circle cx="17" cy="17" r=".6" fill="#a8a29a"/>
  </svg>
  <span class="bk-txt">篮子里 <span class="bk-n" id="bk-n">0</span> 首</span>
  <span class="bk-list" id="bk-list"></span>
  <button class="bk-btn" id="bk-export" type="button">导出</button>
  <button class="bk-btn line" id="bk-clear" type="button">倒掉</button>
</div>

<div id="np" aria-live="polite">
  <img id="np-cover" alt="">
  <div id="np-meta"><div id="np-title" class="lc"></div><div id="np-artist"></div></div>
  <button id="np-toggle" class="np-btn" type="button" aria-label="播放/暂停">{ICON_PLAY}{ICON_PAUSE}</button>
  <div id="np-bar"><div id="np-fill"></div></div>
  <span id="np-time" class="mono">0:00 / 0:00</span>
</div>

{LIGHTBOX_HTML}
<script>{js}</script>
<script>{lightbox_js('.big-art')}</script>
<script>{NETEASE_OPEN_JS}</script>
</body>
</html>"""
