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


def build_artist_json(pool: list[dict], bios: dict[str, str]) -> str:
    """艺人上下文侧表 {artist: {b:bio, y:年代跨度, i:[本站收录曲名]}}。

    为什么单独一张表而不是塞进每首曲子：1169 首里同一位艺人常有多首，
    bio 有一两百字，逐曲重复会把 pool.min.json 撑大好几倍。
    浮层按 artist 名查这张表即可。

    与日报的 _artist_ctx 是同一套语义（bio / years / inpool），
    只是键名压短了 —— 这张表要走网络，日报是内联在 HTML 里的。
    """
    import collections
    by: dict[str, list[dict]] = collections.defaultdict(list)
    for t in pool:
        by[t.get("artist", "")].append(t)
    out: dict[str, dict] = {}
    for a, ts in by.items():
        yrs = sorted(str(t.get("year", "")) for t in ts if t.get("year"))
        e = {}
        if bios.get(a):
            e["b"] = bios[a]
        if yrs:
            e["y"] = yrs[0] if yrs[0] == yrs[-1] else f"{yrs[0]}\u2013{yrs[-1]}"
        titles = [t.get("title", "") for t in ts][:8]
        if len(titles) > 1:
            e["i"] = titles
        if e:
            out[a] = e
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))


EXTRA_CSS = """
/* ── 随机页专属 ───────────────────────────────────────────── */
/* 给吸底播放器让位。派生自 --np-h 并加底部安全区，
   否则 standalone 下最后一张卡被播放器压住。 */
body{padding-bottom:calc(var(--np-h, 76px) + var(--sab, 0px))}
.search-bar{display:flex;align-items:center;gap:12px;margin-top:var(--sp-md);padding:0 14px;
  border:1px solid var(--g300);background:var(--paper);min-height:48px}
.search-bar label{font:10px var(--mono);color:var(--g600);letter-spacing:.06em;flex:none}
.search-bar input{min-width:0;flex:1;border:0;background:transparent;color:var(--ink);font:13px var(--sans);min-height:46px;outline-offset:-2px}
.search-bar button{border:0;border-left:1px solid var(--g200);background:transparent;padding:0 0 0 14px;
  color:var(--g600);font:10px var(--mono);min-height:44px;cursor:pointer}
.search-bar button:disabled{opacity:.45;cursor:default}
.filter-summary{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:8px;
  font:10px/1.7 var(--mono);color:var(--g600)}
.preview-filter{display:flex;align-items:center;gap:6px;min-height:30px;cursor:pointer}
.preview-filter input{accent-color:var(--ink);width:14px;height:14px}
#filter-feedback,#play-status,#search-note,#copy-status{font:11px/1.7 var(--mono);color:var(--g600);margin-top:6px}
#filter-feedback:empty,#search-note:empty,#copy-status:empty{display:none}
#play-status{min-height:19px}
#search-results{grid-template-columns:repeat(3,minmax(0,1fr));margin-top:8px}
#search-results[hidden]{display:none}
.dice-wrap{border:1px solid var(--g300);border-top:0; background:var(--paper); margin-top:0;
  display:flex; flex-wrap:wrap; align-items:stretch}
.filters{display:flex; flex-wrap:wrap; gap:0; flex:1; min-width:260px}
.fsel{position:relative; border-right:1px solid var(--g100); flex:1 1 33%; min-width:110px}
.fsel select{appearance:none; width:100%; height:100%; min-height:60px; padding:10px 28px 10px 14px;
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
  align-items:center; justify-content:center; gap:13px; min-height:60px;
  transition:background .2s, transform .1s}
#roll:hover{background:var(--g1000)}
#roll:disabled{opacity:.5;cursor:default}
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
#roll.rolling .dice .vinyl{animation:vinyl-idle .24s linear both}
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
.card.in{animation:card-in .24s cubic-bezier(.16,1,.3,1) both}
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
.card.in .big-art .cover{animation:cover-set .5s cubic-bezier(.2,1.3,.32,1) 1.75s both}
@keyframes cover-set{0%{opacity:0; transform:scale(1.1) rotate(-4deg); filter:saturate(.5)}
  60%{opacity:1; transform:scale(1.01) rotate(.6deg); filter:saturate(1)}
  100%{opacity:1; transform:none}}
/* 播放键即时可用，唱盘动画不阻塞操作。 */
.card.in .big-art .pbtn{animation:pbtn-in .2s ease-out both}
@keyframes pbtn-in{from{opacity:0; transform:translateY(5px) scale(.86)}to{opacity:1; transform:none}}

/* 信息立即可读；唱盘仍沿用原有完整动效。 */
.card.in .c-title,.card.in .c-artist,.card.in .c-meta,.card.in .tags,.card.in .c-one,
.card.in .c-why,.card.in .c-scene,.card.in .c-links{animation:read-in .2s ease-out both}
@keyframes read-in{from{opacity:.7;transform:translateY(3px)}to{opacity:1;transform:none}}
.card .c-top{display:flex; align-items:center; justify-content:space-between;
  padding:12px 16px; border-bottom:1px solid var(--g100)}
.card .c-no{font-family:var(--mono); font-size:var(--fs-10); color:var(--g600);
  text-transform:uppercase; letter-spacing:.1em}
.card .c-tag{display:inline-flex; gap:8px; align-items:center}
.card .c-main{display:flex; gap:clamp(18px,2.6vw,30px); padding:clamp(16px,2.4vw,28px); flex-wrap:wrap}
.card .big-art{position:relative; width:clamp(150px,22vw,232px); aspect-ratio:1; flex:none;
  align-self:flex-start}   /* 不加这行会被 flex 纵向拉伸成 232×342，圆变椭圆 */
.card .cover-open{display:block;width:100%;height:100%;padding:0;border:0;background:transparent;
  color:inherit;position:relative;cursor:zoom-in}
.card .big-art .cover{width:100%; height:100%; object-fit:cover; display:block;
  background:var(--g100); border:1px solid var(--g100)}
.card .big-art .cover.ph{display:grid; place-items:center; font-family:var(--mono);
  font-size:var(--fs-40); font-weight:400; color:var(--white); background:var(--ink); border:none;
  background-image:repeating-linear-gradient(45deg,rgba(255,255,255,.06) 0 8px,transparent 8px 16px)}
.card .big-art .pbtn{left:10px; bottom:10px; width:44px; height:44px;z-index:5}
.card .big-art .pbtn svg{width:15px; height:15px}
.card .c-hd{flex:1; min-width:240px; display:flex; flex-direction:column; position:relative}
.card .c-hd>*{position:relative; z-index:2}
.card .c-title{font-size:var(--fs-30); font-weight:300; line-height:1.25; letter-spacing:-.015em;
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
.card .c-why{font-size:var(--fs-20); font-weight:300; line-height:1.65; margin-top:10px}
.card .c-scene{font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase;
  color:var(--g900); margin-top:14px}
.card .c-scene .k{color:var(--orange)}
.card .c-links{display:flex; gap:8px; margin-top:auto; padding-top:18px; align-items:center; flex-wrap:wrap}
.card.empty .c-main{color:var(--g500); justify-content:center; text-align:center;
  font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase; padding:var(--sp-xl)}
.card.empty b{font-weight:400;color:var(--ink);font-size:14px}.card.empty p{line-height:1.8;margin:10px 0}.card.empty button{margin-top:8px;min-height:44px;cursor:pointer}

/* 今晚的篮子：临时收藏浮条（贴在 now-playing 条上方；空时不显示）*/
/* bottom 跟着播放器的【实际占位高度】走（--np-h + 底部安全区），
   此前写死 76px = 只等于播放器自身高度。播放器一加安全区就会盖住篮子下沿。
   两处硬编码同一个数字是这次要一起收掉的东西。 */
#basket{position:fixed; left:0; right:0;
  bottom:calc(var(--np-h, 76px) + var(--sab, 0px)); z-index:1150; display:none;
  background:var(--white); border-top:1px solid var(--g300); border-bottom:1px solid var(--g100);
  padding:10px calc(clamp(16px,4vw,52px) + var(--sar, 0px))
          10px calc(clamp(16px,4vw,52px) + var(--sal, 0px));
  align-items:center; gap:clamp(8px,1.4vw,16px);
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
/* 原 134 = 播放器 76 + 篮子 58，两个数都硬编码。改成派生 + 安全区。 */
body.has-basket{padding-bottom:calc(var(--np-h, 76px) + 58px + var(--sab, 0px))}
@media(max-width:720px){
  #basket .bk-list{display:none}
  /* 覆盖 padding 必须带上左右 inset，否则窄屏（最需要安全区的那批设备）丢保护 */
  #basket{gap:8px;
    padding:9px calc(16px + var(--sar, 0px)) 9px calc(16px + var(--sal, 0px))}
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
.recent .r{border:0;border-right:1px solid var(--g300); border-bottom:1px solid var(--g300);text-align:left;color:var(--ink);
  padding:11px 13px; cursor:pointer; background:var(--paper); transition:background .15s; min-width:0}
.recent .r:hover{background:var(--white)}
.recent .r .rt{display:block;font-size:var(--fs-15); font-weight:300; white-space:nowrap;
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
  /* 覆盖 padding-inline 会整条替换掉基础规则里的 calc()，丢掉左右安全区。
     ≤520px 正是手机 —— 最需要安全区的那批设备（竖屏 left/right inset 为 0 所以
     当前无感，横屏窄设备与未来机型会中）。 */
  .wrap{padding-left:calc(16px + var(--sal)); padding-right:calc(16px + var(--sar))}
  .brand{font-size:14px; gap:8px; white-space:nowrap; flex:none}
  .brand .sq{width:11px; height:11px}
  .hero{display:grid;grid-template-columns:minmax(0,1fr) auto;padding:20px 0 14px;gap:12px;align-items:center}
  .hero .h-l{min-width:0}.hero .h-l h1{font-size:32px}.hero .h-l .en{line-height:1.6;overflow-wrap:anywhere}
  .hero .h-r{font-size:9px;line-height:1.7}.hero .h-r .big{font-size:28px;display:block;margin-right:0}
  /* 筛选：改 grid 两列（mood/genre 并排、decade 跨两列）。
     不能用 flex:1 1 50% —— 实测父级 min-width:0 后 .fsel 被压成 1px 宽，
     select 文字整个挤没、只剩 ::after 的 ▾ 箭头。grid 显式分列才稳。 */
  .filters{display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); min-width:0; flex:none; width:100%}
  .fsel{min-width:0;border-bottom:1px solid var(--g100)}
  .fsel:last-child{border-right:none}
  .fsel select{min-height:52px; padding:20px 21px 6px 10px; font-size:12px}
  .fsel .lbl{left:12px; top:6px}
  #roll{min-height:48px; padding:10px 16px; gap:10px; font-size:14px; width:100%}
  #roll .dice{width:26px; height:26px}
  .hint{font-size:9px; line-height:1.9}
  /* the pick：封面横铺在上、文字在下，别在 390px 里硬并排 */
  .card .c-main{flex-direction:column; gap:14px; padding:14px}
  .card .big-art{width:min(100%,220px); max-width:none; aspect-ratio:1;align-self:center}
  .card .c-hd{min-width:0}
  .card .c-title{font-size:26px}
  .card .c-links{gap:6px}
  .card .c-links>*{flex:1 1 calc(50% - 3px); justify-content:center; text-align:center}
  .recent,#search-results{grid-template-columns:repeat(2,minmax(0,1fr))}
  .search-bar{padding:0 10px;gap:8px}.search-bar input{font-size:16px}.search-bar label{font-size:9px}.search-bar button{padding-left:10px}
  /* 原写 bottom:70px —— 播放器【从没】在窄屏改过高度（一直 76px），
     这个 70 是不一致的旧值，篮子下沿被播放器盖住 6px。改为跟 --np-h 联动。 */
  #basket{bottom:calc(var(--np-h, 76px) + var(--sab, 0px));
    padding:8px calc(14px + var(--sar, 0px)) 8px calc(14px + var(--sal, 0px))}
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

JS = r"""
const $=s=>document.querySelector(s);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const normalize=value=>String(value||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase().trim();
const stringList=value=>Array.isArray(value)?value.filter(x=>typeof x==='string'):[];
function mediaURL(value){try{const u=new URL(value);return /^https?:$/.test(u.protocol)?u.href:''}catch{return '';}}
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
let POOL=[],seen=[],cur=null,selected=null,recent=[],ARTISTS={};
let au=null,audioVersion=0,playAttempt=0,rollVersion=0,rollTimer=null,loadVersion=0,loaded=false,playPending=false;
const np=$('#np'),NC=$('#np-cover'),NT=$('#np-title'),NA=$('#np-artist'),NBAR=$('#np-bar'),NFILL=$('#np-fill'),NTIME=$('#np-time'),NTOG=$('#np-toggle');
// The basket remains session-only; daily-page favorites use a different storage/key.
const KEY='md_basket';
function ld(){try{const items=JSON.parse(sessionStorage.getItem(KEY)||'[]');return Array.isArray(items)?[...new Set(items.filter(x=>typeof x==='string'&&x.trim()&&x.length<1000))]:[];}catch{return [];}}
function sv(items){try{sessionStorage.setItem(KEY,JSON.stringify(items));}catch{feedback('当前浏览器无法保存，篮子会保留到本页刷新前。');}}
let hearts=ld();
function bkRender(pop=false){
  const el=$('#basket'),on=hearts.length>0;
  $('#bk-n').textContent=hearts.length;$('#bk-list').textContent=hearts.slice(-4).reverse().join(' · ');
  el.classList.toggle('on',on);document.body.classList.toggle('has-basket',on);
  if(pop&&on&&!reduced){el.classList.remove('pop');void el.offsetWidth;el.classList.add('pop');}
  $('#bk-text').textContent='今晚的篮子 · MUSIC DAILY\n'+hearts.join('\n');$('#bk-copy').disabled=!on;
  if(!on)$('#bk-box').classList.remove('on');
}
const fmt=value=>{value=Number.isFinite(value)&&value>0?Math.floor(value):0;return Math.floor(value/60)+':'+String(value%60).padStart(2,'0');};
function lcd(message){$('#boot').textContent=message;}
function feedback(message){$('#filter-feedback').textContent=message;}
function playback(message){$('#play-status').textContent=message;}
function match(track){
  const mood=$('#f-mood').value,genre=$('#f-genre').value,decade=$('#f-decade').value;
  if(mood&&!track.mood_tags.map(tgm).includes(mood))return false;
  if(genre&&!track.genres.some(x=>x.toLowerCase()===genre))return false;
  if(decade&&Math.floor(parseInt(track.year,10)/10)*10!==Number(decade))return false;
  if($('#f-preview').checked&&!track.p)return false;
  const words=normalize($('#f-search').value).split(/\s+/).filter(Boolean);
  const text=normalize([track.title,track.artist,track.album,...track.genres,...track.mood_tags.map(tgm)].join(' '));
  return words.every(word=>text.includes(word));
}
function pool(){return POOL.filter(match);}
function lbData(t){
  const A=(k,v)=>' data-'+k+'="'+esc(v)+'"';
  // genres 原样输出，【不过 tgm】—— tgm 是 mood 别名表，而「organic electronic」既是池里 115 首的 genre、又是 mood「organic」的别名，过一遍就把流派改写成气质词（实测 68 个 chip 被改写、21 首浮层出现重复 tag）。mood_tags 仍要过 tgm。2026-08-04 审计。
  const tags=[].concat((t.genres||[]).slice(0,3),(t.mood_tags||[]).slice(0,3).map(tgm)).join('|');
  // 艺人上下文来自侧表 ARTISTS（bio / 年代 / 本站收录），日报是内联注入，
  // 这里走网络加载。漏了这三项的话浮层只剩曲目信息、没有音乐人简介 —— 2026-08-03 修。
  const ac=(ARTISTS&&ARTISTS[t.artist])||{};
  return A('cover',t.c)+A('title',t.title)+A('artist',t.artist)+A('year',t.year)
       +A('years',ac.y||'')+A('g0',(t.genres||[''])[0])
       +A('album',t.album)+A('bpm',t.bpm_band||'')+A('tags',tags)
       +A('bio',ac.b||'')+A('inpool',stringList(ac.i).join('|'))
       +A('one',t.artist_oneliner||'')+A('why',t.why||'')+A('scene',t.scene||'')
       +A('apple',t.a||'')+A('spotify','https://open.spotify.com/search/'
         +encodeURIComponent((t.title||'')+' '+(t.artist||'')));
}

function render(t, animate=true){
  const art=t.c?('<img class="cover" src="'+esc(t.c)+'" alt="'+esc(t.album||t.title)+' 专辑封面">')
                :('<span class="cover ph">'+esc(((t.artist||'?')[0]||'?').toUpperCase())+'</span>');
  const pb=t.p?('<button class="pbtn" id="cpb" type="button" aria-label="\u8bd5\u542c 30 \u79d2">'+PLAY+PAUSE+'</button>'):'';
  // badge 优先显示当前筛选中的那个流派。否则筛 dream pop 时，主标签是别的流派的曲子
  // 会显示成「folktronica」「bedroom pop」，看着像筛选串味了（实测 151 首里 74 首如此）
  const gsel=$('#f-genre').value;
  const glist=t.genres.length?t.genres:['\u2014'];
  const g0=(gsel&&glist.some(x=>x.toLowerCase()===gsel))
    ? glist.find(x=>x.toLowerCase()===gsel) : glist[0];
    // genres 原样、moods 过 tgm —— 别整体 map(tgm)，那会把流派
    // 「organic electronic」改写成 mood 词「organic」（见 lbData 处注释）
    const tags=[].concat((t.genres||[]).slice(1,3),
                         (t.mood_tags||[]).slice(0,2).map(tgm))
    .map(x=>'<span class="tag">'+esc(x)+'</span>').join('');
  const bpmC=(bb)=>{const n=String(bb||'').match(/\d+/g); if(!n)return '';
    const m=(+n[0]+ +n[n.length-1])/2;
    return m<85?'#0071bb':m<105?'#006837':m<125?'#fab413':'#f05a24';};
  const meta=esc([t.year,t.album].filter(Boolean).join(' / '))
    +(t.bpm_band?('<span class="bpm" style="--bc:'+bpmC(t.bpm_band)+'">'+esc(t.bpm_band)+' bpm</span>'):'');
  const on=hearts.indexOf(t.title+' - '+t.artist)>=0?' on':'';
  const links=(t.a?'<a class="btn solid" href="'+esc(t.a)+'" target="_blank" rel="noopener">listen</a>':'')
    +'<a class="btn line" href="https://open.spotify.com/search/'+encodeURIComponent(t.title+' '+t.artist)+'" target="_blank" rel="noopener">spotify \u2197</a>'
    +'<a class="btn line" href="https://music.163.com/#/search/m/?s='+encodeURIComponent(t.title+' '+t.artist)+'" target="_blank" rel="noopener"'
    +' data-nc="'+esc(t.title+' '+t.artist)+'">netease \u266b</a>'
    +'<button class="heart'+on+'" id="chz" type="button" data-k="'+esc(t.title+' - '+t.artist)+'" aria-label="\u6536\u85cf">'+HEART+'</button>';
  const card=$('#card');
  card.className='card';card.removeAttribute('aria-busy');
  card.innerHTML='<div class="c-top"><span class="c-no">pick \u00b7 '+String(seen.length).padStart(3,'0')+' / '+pool().length+'</span>'
    +'<span class="c-tag"><span class="m-code" style="background:'+knob(g0)+'">'+esc(g0)+'</span></span></div>'
    +'<div class="c-main"><div class="big-art"><button class="cover-open cover-zoom" type="button"'
    +' aria-label="\u770b\u5927\u56fe\u4e0e\u8be6\u60c5"'
    +lbData(t)+'>'+art+'</button>'+pb+'</div>'
    +'<div class="c-hd"><div class="c-title lc" tabindex="-1">'+esc(t.title)+'</div>'
    +'<div class="c-artist">'+esc(t.artist)+'</div><div class="c-meta">'+meta+'</div>'
    +'<div class="tags" style="margin-top:10px">'+tags+'</div>'
    +'<div class="c-one">'+esc(t.artist_oneliner||'')+'</div>'
    +'<div class="c-why">'+esc(t.why||'')+'</div>'
    +(t.scene?'<div class="c-scene"><span class="k">use \u25b8</span> '+esc(t.scene)+'</div>':'')
    +'<div class="c-links">'+links+'</div></div></div>';
  // 唱针落针 + 唱片起转：封面框先放一张真在转的黑胶，唱臂摆入落针后定格成封面
  if(animate&&!reduced)(function(){
    const art=card.querySelector('.big-art'); if(!art)return;
    const tt=document.createElement('div'); tt.className='tt';
    const LBL='<svg class="vlbl" viewBox="0 0 20 20" aria-hidden="true">'
      +'<defs><path id="dlbl" fill="none" d="M 10 5.1 A 4.9 4.9 0 1 1 9.99 5.1"/></defs>'
      +'<text><textPath href="#dlbl" startOffset="4%">'
      +'33⅓ RPM · LONG PLAY</textPath></text>'
      +'<circle cx="10" cy="10" r=".5" fill="#a8a29a"/></svg>';
    tt.innerHTML='<div class="deck"><div class="dwrap"><div class="disc">'+LBL+'</div></div>'
      +'<div class="arm"><i></i><b></b></div><span class="drop"></span></div>'
      +'<span class="led"></span>';
    art.appendChild(tt);
    setTimeout(()=>tt.remove(), 2050);
  })();
  if(animate&&!reduced)requestAnimationFrame(()=>{if(selected?.id===t.id)card.classList.add('in');});
  const image=card.querySelector('img.cover'); if(image)image.addEventListener('error',()=>{const ph=document.createElement('span');ph.className='cover ph';ph.textContent=t.artist.slice(0,1)||'♪';image.replaceWith(ph);},{once:true});
  const pb2=$('#cpb'); if(pb2)pb2.addEventListener('click',()=>toggle(t));
  const hz=$('#chz'); if(hz)hz.addEventListener('click',()=>{
    const k=hz.dataset.k,i=hearts.indexOf(k);
    const added=i<0;
    if(i>=0)hearts.splice(i,1);else hearts.push(k);
    sv(hearts);hz.classList.toggle('on',hearts.includes(k));hz.setAttribute('aria-pressed',String(hearts.includes(k)));hz.setAttribute('aria-label',hearts.includes(k)?'从临时篮子移出':'加入临时篮子');bkRender(added);});
  if(hz){hz.setAttribute('aria-pressed',String(hearts.includes(t.title+' - '+t.artist)));hz.setAttribute('aria-label',hearts.includes(t.title+' - '+t.artist)?'从临时篮子移出':'加入临时篮子');}
  try{history.replaceState(null,'','?t='+encodeURIComponent(t.id));}catch{}
}
function knob(s){s=s||'x';let n=0;for(const c of s)n+=c.charCodeAt(0);return KNOB[n%KNOB.length];}


function mark(on){
  const label=playPending?'取消加载试听':on?'暂停试听':'播放30秒试听';
  const button=$('#cpb');if(button){button.classList.toggle('playing',on);button.setAttribute('aria-pressed',String(on));button.setAttribute('aria-label',label);button.disabled=false;}
  np.classList.toggle('playing',on);NTOG.setAttribute('aria-label',label);NTOG.disabled=!au;
}
function stopAudio(){
  ++audioVersion;++playAttempt;playPending=false;const previous=au;au=null;
  if(previous){previous.playRequested=false;previous.pause();previous.removeAttribute('src');previous.load();}
  mark(false);NFILL.style.width='0%';NTIME.textContent='0:00 / 0:00';NBAR.setAttribute('aria-valuenow','0');
}
// play() may reject due to autoplay policy or media loading; stale attempts cannot change the new song.
// https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/play
async function resume(){
  if(!au||playPending)return;
  const media=au,version=audioVersion,attempt=++playAttempt;media.playRequested=true;playPending=true;mark(false);playback('正在加载试听…');
  const activeAttempt=()=>version===audioVersion&&au===media&&attempt===playAttempt;
  try{if(media.error)media.load();if(media.currentTime>=30||media.ended)media.currentTime=0;await media.play();if(!media.playRequested){media.pause();return;}if(activeAttempt())playback('正在试听 · 最长30秒');}
  catch(error){if(!activeAttempt())return;media.playRequested=false;playback(error.name==='NotAllowedError'?'点一下播放键，即可开始试听。':'试听暂时不可用，点击播放可重试，或前往音乐平台。');}
  finally{if(activeAttempt()){playPending=false;mark(media.playRequested&&!media.paused);}}
}
function pauseRequested(){if(!au)return;++playAttempt;au.playRequested=false;playPending=false;au.pause();mark(false);playback('已暂停 · 点击播放继续');}
function play(track,autoplay=true){
  cur=track;NT.textContent=track.title;NA.textContent=track.artist;
  NC.hidden=!track.c;if(track.c)NC.src=track.c;else NC.removeAttribute('src');
  if(!track.p){np.classList.remove('on');playback('这首暂无试听，可通过下方链接前往音乐平台。');mark(false);return;}
  const media=new Audio(track.p),version=audioVersion;au=media;media.preload='none';media.playRequested=false;
  const active=()=>version===audioVersion&&au===media;
  media.addEventListener('playing',()=>{if(!active()||!media.playRequested){media.pause();return;}mark(true);playback('正在试听 · 最长30秒');});
  media.addEventListener('pause',()=>{if(active()){mark(false);if(!media.ended&&!playPending)playback('已暂停 · 点击播放继续');}});
  media.addEventListener('ended',()=>{if(active()){media.playRequested=false;mark(false);playback('试听结束 · 可以重播，或另起一首');}});
  media.addEventListener('error',()=>{if(active()&&media.playRequested){media.playRequested=false;playPending=false;mark(false);playback('试听加载失败，点播放重试，或打开音乐平台。');}});
  media.addEventListener('timeupdate',()=>{
    if(!active()||!Number.isFinite(media.duration)||media.duration<=0)return;
    const duration=Math.min(media.duration,30),seconds=Math.min(media.currentTime,duration);
    if(media.currentTime>=30&&!media.paused){pauseRequested();playback('30秒试听结束 · 点击播放可重播');}
    NFILL.style.width=seconds/duration*100+'%';NTIME.textContent=fmt(seconds)+' / '+fmt(duration);
    NBAR.setAttribute('aria-valuenow',String(Math.round(seconds/duration*100)));NBAR.setAttribute('aria-valuetext',fmt(seconds)+' / '+fmt(duration));
  });
  np.classList.add('on');mark(false);playback('点击播放，试听30秒。');if(autoplay)resume();
}
function toggle(track){if(!track?.p)return;if(!cur||cur.id!==track.id||!au){stopAudio();play(track);return;}if(playPending||!au.paused)pauseRequested();else resume();}
NTOG.addEventListener('click',()=>toggle(cur));
NC.addEventListener('error',()=>{NC.hidden=true;});
function seek(fraction){if(!au||!Number.isFinite(au.duration)||au.duration<=0)return;au.currentTime=Math.max(0,Math.min(1,fraction))*Math.min(au.duration,30);}
NBAR.addEventListener('click',event=>{const rect=NBAR.getBoundingClientRect();if(rect.width)seek((event.clientX-rect.left)/rect.width);});
NBAR.addEventListener('keydown',event=>{if(!au||!Number.isFinite(au.duration)||!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();event.stopPropagation();seek(event.key==='Home'?0:event.key==='End'?1:(au.currentTime+(event.key==='ArrowRight'?5:-5))/Math.min(au.duration,30));});
function cancelRoll(){++rollVersion;clearTimeout(rollTimer);rollTimer=null;$('#roll').classList.remove('rolling');$('#roll').removeAttribute('aria-busy');}
function selectTrack(track,autoplay=true,animate=true){cancelRoll();stopAudio();selected=track;if(!seen.includes(track.id))seen.push(track.id);render(track,animate);pushRecent(track);play(track,autoplay);updateMatches();lcd('picked · '+track.title+' — '+track.artist);}
function trackButtons(container,tracks){
  container.replaceChildren();tracks.forEach(track=>{const button=document.createElement('button');button.type='button';button.className='r';button.dataset.id=track.id;
    const title=document.createElement('span');title.className='rt lc';title.textContent=track.title;
    const artist=document.createElement('span');artist.className='ra';artist.textContent=track.artist;button.append(title,artist);
    button.setAttribute('aria-label','选择 '+track.title+'，'+track.artist);button.addEventListener('click',()=>{selectTrack(track,true,false);$('#card .c-title')?.focus({preventScroll:true});});container.appendChild(button);});
}
function pushRecent(track){recent=[track,...recent.filter(x=>x.id!==track.id)].slice(0,8);trackButtons($('#recent'),recent);}
function filtersActive(){return ['#f-search','#f-mood','#f-genre','#f-decade'].some(s=>$(s).value.trim())||$('#f-preview').checked;}
function updateMatches(){
  const matches=pool();$('#filter-count').textContent=loaded?matches.length+' / '+POOL.length+' tracks':'loading…';$('#f-reset').disabled=!filtersActive();$('#roll').disabled=!loaded||!matches.length;
  const searching=Boolean($('#f-search').value.trim());$('#search-results').hidden=!searching||!matches.length;
  $('#search-note').textContent=searching&&matches.length?'点选直接试听'+(matches.length>6?' · 显示前6首，可缩小搜索或随机抽取':''):'';
  trackButtons($('#search-results'),searching?matches.slice(0,6):[]);return matches;
}
function state(title,detail,action=''){
  const card=$('#card');card.className='card empty';card.removeAttribute('aria-busy');
  card.innerHTML='<div class="c-main"><div><b>'+esc(title)+'</b><p>'+esc(detail)+'</p>'+(action?'<button class="btn line" id="state-action" type="button">'+(action==='retry'?'重新加载':'重置筛选')+'</button>':'')+'</div></div>';
  if(action)$('#state-action').addEventListener('click',action==='retry'?loadPool:resetFilters);
}
function filtersChanged(){
  if(!loaded)return;cancelRoll();seen=[];const matches=updateMatches();feedback('');
  if(!matches.length){stopAudio();selected=null;cur=null;np.classList.remove('on');playback('');state('没有匹配曲目','换个关键词，或减少筛选条件。','reset');lcd('0 tracks match · reset filters');}
  else if(!selected||!match(selected)){stopAudio();selected=null;cur=null;np.classList.remove('on');playback('');state(matches.length+' 首符合条件','点「另起一首」，或从搜索结果中选歌。');lcd(matches.length+' tracks in play');}
  else{const badge=$('#card .m-code'),genre=selected.genres.find(g=>g.toLowerCase()===$('#f-genre').value)||selected.genres[0];if(badge&&genre){badge.textContent=genre;badge.style.background=knob(genre);}}
}
function resetFilters(){['#f-search','#f-mood','#f-genre','#f-decade'].forEach(s=>$(s).value='');$('#f-preview').checked=false;filtersChanged();if(loaded&&POOL.length)roll(false);}
function roll(autoplay=true){
  if(!loaded||rollTimer!==null)return;const list=pool();if(!list.length){filtersChanged();return;}
  let fresh=list.filter(t=>!seen.includes(t.id));if(!fresh.length){seen=[];fresh=list;}if(fresh.length>1&&selected)fresh=fresh.filter(t=>t.id!==selected.id);
  const next=fresh[Math.floor(Math.random()*fresh.length)],version=++rollVersion;
  const button=$('#roll');button.classList.add('rolling');button.setAttribute('aria-busy','true');lcd('shuffling…');
  rollTimer=setTimeout(()=>{if(version!==rollVersion)return;rollTimer=null;selectTrack(next,autoplay);},reduced?0:240);
}
function fill(selector,items,label){const select=$(selector),previous=select.value;select.replaceChildren(new Option(label,''));items.forEach(([value,text])=>select.add(new Option(text,value)));if([...select.options].some(o=>o.value===previous))select.value=previous;}
function normalizePool(data){
  if(!Array.isArray(data))throw new Error('invalid pool');const ids=new Set();
  return data.filter(t=>t&&typeof t.id==='string'&&t.id&&typeof t.title==='string'&&t.title&&typeof t.artist==='string'&&t.artist)
    .filter(t=>{if(ids.has(t.id))return false;ids.add(t.id);return true;})
    .map(t=>({...t,genres:stringList(t.genres),mood_tags:stringList(t.mood_tags),c:mediaURL(t.c),p:mediaURL(t.p),a:mediaURL(t.a)}));
}
function findSeed(query){const value=query.get('t'),artist=query.get('artist');return value?(POOL.find(t=>t.id===value)||POOL.find(t=>t.title===value&&(!artist||t.artist===artist))):null;}
// HTTP errors need explicit checks, and a timeout keeps Retry reachable on a stalled request.
// https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch
async function fetchJSON(url){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);try{const response=await fetch(url,{signal:controller.signal});if(!response.ok)throw new Error('HTTP '+response.status);return await response.json();}finally{clearTimeout(timer);}}
async function loadPool(){
  const version=++loadVersion;loaded=false;cancelRoll();stopAudio();feedback('');$('#roll').disabled=true;
  document.querySelectorAll('.filter-control').forEach(control=>control.disabled=true);state('正在加载曲库','载入后可搜索、筛选或另起一首。');$('#card').setAttribute('aria-busy','true');lcd('loading tracks…');
  try{
    const data=normalizePool(await fetchJSON('pool.min.json'));if(version!==loadVersion)return;if(!data.length)throw new Error('empty pool');POOL=data;loaded=true;
    const moods=Object.create(null),genres=Object.create(null),decades=Object.create(null);
    data.forEach(t=>{new Set(t.mood_tags.map(tgm)).forEach(k=>moods[k]=(moods[k]||0)+1);new Set(t.genres.map(g=>g.toLowerCase())).forEach(k=>genres[k]=(genres[k]||0)+1);const year=parseInt(t.year,10);if(year){const k=Math.floor(year/10)*10;decades[k]=(decades[k]||0)+1;}});
    const ranked=counts=>Object.entries(counts).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])).map(([k,n])=>[k,k+' ('+n+')']);
    fill('#f-mood',ranked(moods),'全部心情');fill('#f-genre',ranked(genres),'全部流派');fill('#f-decade',Object.keys(decades).sort().map(k=>[k,k+'s ('+decades[k]+')']),'全部年代');
    document.querySelectorAll('.filter-control').forEach(control=>control.disabled=false);updateMatches();
    const query=new URLSearchParams(location.search),id=query.get('t'),seed=findSeed(query);
    if(seed)selectTrack(seed,false,false);else{if(id)feedback('链接中的歌曲暂未找到，先为你换一首。');roll(false);}
  }catch(error){if(version!==loadVersion)return;state('曲库加载失败','检查网络后再试，今晚的篮子仍保留。','retry');$('#filter-count').textContent='加载失败';lcd('load failed · retry');}
}
async function loadArtists(){try{const data=await fetchJSON('artists.min.json');if(!data||Array.isArray(data)||typeof data!=='object')return;ARTISTS=data;const art=$('#card .cover-open'),context=selected&&ARTISTS[selected.artist];if(art&&context){art.dataset.bio=String(context.b||'');art.dataset.years=String(context.y||'');art.dataset.inpool=stringList(context.i).join('|');art.dispatchEvent(new CustomEvent('musicdaily:artist-context',{bubbles:true,detail:art.dataset}));}}catch{}}
$('#roll').addEventListener('click',()=>roll());
['#f-mood','#f-genre','#f-decade','#f-preview'].forEach(s=>$(s).addEventListener('change',filtersChanged));$('#f-search').addEventListener('input',filtersChanged);$('#f-reset').addEventListener('click',resetFilters);
$('#bk-export').addEventListener('click',()=>{if(!hearts.length)return;bkRender();$('#bk-box').classList.add('on');$('#bk-box').scrollIntoView({behavior:reduced?'auto':'smooth',block:'center'});$('#bk-copy').focus({preventScroll:true});});
$('#bk-clear').addEventListener('click',()=>{hearts=[];sv(hearts);bkRender();const heart=$('#chz');if(heart){heart.classList.remove('on');heart.setAttribute('aria-pressed','false');heart.setAttribute('aria-label','加入临时篮子');}feedback('今晚的篮子已清空。');});
$('#bk-copy').addEventListener('click',async()=>{
  const text=$('#bk-text'),button=$('#bk-copy');button.disabled=true;
  try{if(!navigator.clipboard?.writeText)throw new Error('clipboard unavailable');await navigator.clipboard.writeText(text.textContent);$('#copy-status').textContent='已复制清单。';}
  catch{const range=document.createRange();range.selectNodeContents(text);const selection=getSelection();selection.removeAllRanges();selection.addRange(range);$('#copy-status').textContent='自动复制未成功，清单已选中，可长按或按 Ctrl/Cmd+C 复制。';}
  finally{button.disabled=!hearts.length;}
});
document.addEventListener('keydown',event=>{
  if(event.defaultPrevented||event.repeat||event.ctrlKey||event.metaKey||event.altKey||$('#lb')?.classList.contains('on'))return;
  if(event.target.closest('input,textarea,select,button,a,[role="button"],[role="slider"],[contenteditable="true"]'))return;
  if(event.code==='Space'){event.preventDefault();roll();}else if(event.key.toLowerCase()==='p'){event.preventDefault();toggle(selected);}else if(event.key==='/'){event.preventDefault();$('#f-search').focus();}
});
window.addEventListener('pagehide',()=>{cancelRoll();stopAudio();});
bkRender();loadPool();loadArtists();
"""


def build_html(n_total: int) -> str:
    import urllib.parse
    up = ""             # 本页在站点根目录
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
<!-- PWA：加到手机主屏后有真图标、全屏无地址栏、启动闪屏。
     子目录页面用相对上级前缀取根目录的资源。
     只做 manifest 不做 Service Worker —— 这个站每天出新刊，SW 的缓存失效
     写不对就会让用户看到昨天的日报【而且他不知道】，那类静默失效的代价
     远大于「离线翻往期」的收益。 -->
<link rel="manifest" href="{up}manifest.webmanifest">
<link rel="apple-touch-icon" href="{up}icon-180.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="MD-30">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@100;300;400&family=Space+Mono:wght@400;700&family=Noto+Sans+SC:wght@100;300;400&display=swap" rel="stylesheet">
<style>{CSS}{EXTRA_CSS}{LIGHTBOX_CSS}</style>
</head>
<body>
<nav class="nav">
  <div class="wrap">
    <a class="brand" href="index.html"><span class="sq"></span>MUSIC DAILY</a>
    <div class="serial nav-meta"><span>mode <b>shuffle</b></span><span>pool <b>{n_total}</b></span></div>
    <div class="site-links" aria-label="页面导航"><a href="daily.html">今日</a><a href="random.html" aria-current="page">随机</a><a href="archive/index.html">往期</a><a href="legacy/random.html">旧版</a></div>
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
    <div class="row1"><span class="dot"></span><span id="boot" role="status" data-text="{_esc(boot)}">loading…</span>
      <div class="cat-wrap"><div class="cat-move">{ICON_CAT}</div><span class="prop bowl">{ICON_BOWL}</span><span class="prop ball">{ICON_BALL}</span></div></div>
  </div>

  <div class="search-bar"><label for="f-search">search</label><input class="filter-control" id="f-search" type="search" placeholder="歌名 / 艺人 / 专辑" autocomplete="off" disabled><button id="f-reset" type="button" disabled>重置</button></div>
  <div class="dice-wrap">
    <div class="filters">
      <div class="fsel"><label class="lbl" for="f-mood">mood</label><select class="filter-control" id="f-mood" disabled><option value="">全部心情</option></select></div>
      <div class="fsel"><label class="lbl" for="f-genre">genre</label><select class="filter-control" id="f-genre" disabled><option value="">全部流派</option></select></div>
      <div class="fsel"><label class="lbl" for="f-decade">decade</label><select class="filter-control" id="f-decade" disabled><option value="">全部年代</option></select></div>
    </div>
    <button id="roll" type="button" disabled>{ICON_DICE}<span class="lab">另起一首</span><span class="k">space</span></button>
  </div>
  <div class="filter-summary"><span id="filter-count" role="status">loading…</span><label class="preview-filter"><input class="filter-control" id="f-preview" type="checkbox" disabled>只看有试听</label></div>
  <p id="filter-feedback" role="status"></p>
  <div class="hint"><kbd>space</kbd> 另起一首 · <kbd>p</kbd> 播放/暂停 · 试听最长30秒 · ♥ 今晚的篮子（临时）</div>
  <p id="search-note"></p><div class="recent" id="search-results" hidden aria-label="搜索结果"></div>

  <div class="sect">the pick</div>
  <article class="card" id="card" aria-busy="true"><div class="c-main">loading…</div></article>
  <p id="play-status" role="status"></p>

  <div class="sect">刚听过 · recent</div>
  <div class="recent" id="recent"></div>

  <section id="bk-box">
    <div class="h">今晚的篮子 · 导出 <span>本次会话临时 · 关掉页面即清空 · 不进日报收藏</span></div>
    <div class="in">
      <p>复制下列清单 → 网易云 App「新建歌单 → 导入」。想长期留着，请去日报页用 ♥ 收藏。</p>
      <pre id="bk-text"></pre>
      <button class="btn solid" id="bk-copy" type="button" style="margin-top:12px">复制清单 / copy</button>
      <p id="copy-status" role="status"></p>
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

<div id="np" role="region" aria-label="试听播放器">
  <img id="np-cover" alt="">
  <div id="np-meta"><div id="np-title" class="lc"></div><div id="np-artist"></div></div>
  <button id="np-toggle" class="np-btn" type="button" aria-label="播放/暂停" disabled>{ICON_PLAY}{ICON_PAUSE}</button>
  <div id="np-bar" role="slider" tabindex="0" aria-label="试听进度" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><div id="np-fill"></div></div>
  <span id="np-time" class="mono">0:00 / 0:00</span>
</div>

{LIGHTBOX_HTML}
<script>{js}</script>
<script>{lightbox_js('.cover-open')}</script>
<script>{NETEASE_OPEN_JS}</script>
</body>
</html>"""
