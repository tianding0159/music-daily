"""渲染独立的「今天听点别的」随机页（site/random.html）+ 精简池 JSON（site/pool.min.json）。

设计延续日报页的纸张、唱片和猫的视觉语言；支持搜索、筛选、抽取与试听。
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
from ui_common import UI_JS, site_nav
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
    """艺人上下文侧表 {artist: {b:bio, y:年代跨度, i:[{id,title}]}}。

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
        entries = [{"id": t["id"], "title": t["title"]}
                   for t in ts if t.get("id") and t.get("title")][:8]
        if len(entries) > 1:
            e["i"] = entries
        if e:
            out[a] = e
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))


EXTRA_CSS = r"""
/* Random discovery: a quiet record sleeve, with useful filters before the pick. */
body{--player-gap:0px;padding-bottom:calc(36px + var(--player-gap) + var(--sab,0px))}
body.has-player{--player-gap:var(--np-h,76px)}
.random-hero{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:40px;align-items:end;padding:52px 0 36px}
.random-hero h1{font-size:clamp(38px,5.3vw,66px);font-weight:400;letter-spacing:-.055em;line-height:1.15;margin-top:16px}
.random-hero h1 span{color:var(--orange)}
.random-hero .lead{max-width:36em;margin-top:20px}
.pool-stamp{border-left:1px solid var(--g300);padding:6px 0 6px 28px;min-width:160px;color:var(--g600);font-size:12px;line-height:1.8}
.pool-stamp b{display:block;font:400 clamp(36px,4vw,56px) var(--mono);color:var(--ink);letter-spacing:-.06em;line-height:1.2}
.discovery-controls{background:var(--white);border:1px solid var(--g200);padding:20px;margin-top:24px}
.search-row{display:flex;gap:24px;align-items:center;margin-bottom:16px}
.search-row .field{flex:1}.search-row input{background:var(--paper)}
.preview-check{display:flex;align-items:center;gap:8px;font-size:12px;padding-top:22px;white-space:nowrap;min-height:44px;cursor:pointer}
.preview-check input{accent-color:var(--orange);width:18px;height:18px}
.dice-wrap{display:flex;align-items:stretch;gap:12px}
.filters{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;flex:1;min-width:0}
.fsel{display:grid;gap:7px;min-width:0}.fsel .lbl{font-size:12px;color:var(--g900)}
.fsel select{appearance:auto;width:100%;height:46px;padding:8px 10px;background:var(--paper);border:1px solid var(--g200);color:var(--ink);font-size:13px;cursor:pointer;border-radius:0}
#roll{align-self:end;display:flex;align-items:center;justify-content:center;gap:12px;min-height:46px;min-width:190px;padding:9px 18px;border:1px solid var(--orange);background:var(--orange);color:#fff;cursor:pointer;font-size:15px;position:relative;overflow:hidden;transition:background .15s}
#roll:hover{background:#a93a20}#roll:disabled{background:var(--g300);border-color:var(--g300)}
#roll .dice{width:26px;height:26px;flex:none}#roll .k{font:10px var(--mono);opacity:.8}
#roll .vinyl{transform-box:fill-box;transform-origin:center}#roll.rolling .vinyl{animation:vinyl-idle .45s linear infinite}
@keyframes vinyl-idle{to{transform:rotate(360deg)}}
.filter-summary{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:12px;font-size:12px;color:var(--g600)}
#f-reset{border:0;border-bottom:1px solid var(--g300);background:none;color:var(--ink);min-height:36px;padding:4px 0;cursor:pointer;font-size:12px}
.hint{font-size:11px;line-height:1.8;color:var(--g600);margin-top:12px}
.hint kbd{font:10px var(--mono);padding:2px 5px;border:1px solid var(--g200);background:var(--paper)}
#result-box{margin-top:22px}#result-label{font-size:12px;color:var(--g600);margin-bottom:10px}
#result-box .recent{margin-top:0;grid-template-columns:repeat(4,minmax(0,1fr))}
.card{border:1px solid var(--g200);background:var(--white);position:relative;overflow:hidden;margin-top:20px}
.card.in{animation:card-in .3s ease-out both}
@keyframes card-in{from{opacity:.7;transform:translateY(6px)}to{opacity:1;transform:none}}
.card .c-top{display:flex;align-items:center;justify-content:space-between;padding:14px 24px;border-bottom:1px solid var(--g200);gap:16px}
.card .c-no{font:11px var(--mono);color:var(--g600);letter-spacing:.08em}
.card .c-main{display:grid;grid-template-columns:minmax(220px,.85fr) minmax(0,1fr);gap:clamp(24px,4vw,52px);padding:clamp(20px,3vw,36px);align-items:start}
.card .big-art{position:relative;width:100%;aspect-ratio:1;background:var(--ink)}
.cover-open{display:block;width:100%;height:100%;padding:0;border:0;background:transparent;color:inherit;cursor:zoom-in;position:relative}
.cover-open:focus-visible{outline-offset:-4px;z-index:5}
.card .cover{width:100%;height:100%;object-fit:cover;display:block}
.card .cover.ph{display:grid;place-items:center;background:repeating-linear-gradient(45deg,#24211d 0 8px,#1c1916 8px 16px);color:var(--paper);font-size:72px}
.card .big-art .pbtn{left:14px;bottom:14px;width:48px;height:48px;z-index:6}
.card .big-art .pbtn svg{width:17px;height:17px}
.no-preview{position:absolute;left:14px;bottom:14px;padding:7px 10px;background:rgba(0,0,0,.72);color:#fff;font-size:11px;pointer-events:none}
.card .c-hd{min-width:0;align-self:stretch;display:flex;flex-direction:column}
.card .c-title{font-size:clamp(28px,3.3vw,44px);font-weight:400;line-height:1.15;letter-spacing:-.04em;margin:2px 0 0;overflow-wrap:anywhere}
.card .c-artist{font-size:17px;line-height:1.6;margin-top:10px;color:var(--g900);overflow-wrap:anywhere}
.card .c-meta{font-size:11px;color:var(--g600);line-height:1.8;margin-top:12px}
.card .bpm{display:inline-block;margin-left:10px;border-left:2px solid var(--orange);padding-left:8px}
.card .tags{margin-top:14px;gap:6px}.card .tag{font-size:10px;padding:4px 7px}
.card .c-one{font-size:12px;line-height:1.8;color:var(--g600);margin:22px 0 0}
.card .c-why{font-size:clamp(15px,1.5vw,18px);line-height:1.85;margin:12px 0 0;color:var(--g900)}
.card .c-scene{font-size:12px;line-height:1.8;color:var(--g600);margin:14px 0 0}.card .c-scene .k{color:var(--orange);margin-right:8px}
.card .c-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:24px}
.basket-add{background:var(--paper);border:1px solid var(--g300);color:var(--ink);gap:9px;cursor:pointer}
.basket-add svg{width:17px;height:17px}.basket-add.on{border-color:var(--orange);color:var(--orange)}.basket-add.on svg{fill:currentColor}
.card .c-links{display:flex;align-items:center;flex-wrap:wrap;gap:8px;padding-top:20px;margin-top:auto}.card .c-links .btn{font-size:11px;min-height:36px;padding:7px 12px}
#play-status{font-size:12px;line-height:1.8;color:var(--g600);min-height:22px;margin:10px 0 0}
.state-content{padding:42px 24px;text-align:center;max-width:560px;margin:auto}.state-record{display:block;color:var(--orange);font-size:50px;line-height:1.4}
.state-content h2{font-size:22px;line-height:1.5;font-weight:400;margin:10px 0}.state-content p{font-size:13px;line-height:1.9;color:var(--g600)}.state-content .btn{margin-top:20px}
/* A short turntable animation stays separate from immediately readable track information. */
.tt{position:absolute;inset:0;z-index:3;display:grid;place-items:center;pointer-events:none;background:var(--ink);overflow:hidden;animation:tt-out .2s ease-out 1.75s forwards}
.disc-label{position:absolute;inset:40% 0 auto;text-align:center;font:700 10px/1.2 var(--mono);color:#242424}
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


.recent{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-top:1px solid var(--g200);border-left:1px solid var(--g200);margin-top:18px}
.recent .r{display:block;min-width:0;text-align:left;padding:14px 16px;cursor:pointer;background:var(--paper);border:0;border-right:1px solid var(--g200);border-bottom:1px solid var(--g200);color:var(--ink);transition:background .15s}
.recent .r:hover{background:var(--white)}.recent .rt{display:block;font-size:14px;line-height:1.5;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.recent .ra{display:block;font-size:11px;line-height:1.5;color:var(--g600);margin-top:4px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
#basket{position:fixed;left:0;right:0;bottom:calc(var(--player-gap) + var(--sab,0px));z-index:1150;display:none;align-items:center;gap:16px;background:var(--paper);border-top:1px solid var(--g300);padding:10px calc(clamp(16px,4vw,52px) + var(--sar,0px)) 10px calc(clamp(16px,4vw,52px) + var(--sal,0px))}
#basket.on{display:flex}#basket .bk-paw{width:26px;height:26px;flex:none;color:var(--ink)}
.bk-txt{font-size:12px;white-space:nowrap}.bk-n{color:var(--orange);font:18px var(--mono)}
.bk-list{flex:1;font-size:11px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;color:var(--g600)}
.bk-btn{min-height:38px;padding:7px 13px;border:1px solid var(--ink);background:var(--ink);color:var(--paper);font-size:12px;cursor:pointer;white-space:nowrap}.bk-btn.line{background:transparent;color:var(--ink)}
body.has-basket{padding-bottom:calc(100px + var(--player-gap) + var(--sab,0px))}
#bk-box{display:none;border:1px solid var(--g200);background:var(--white);margin-top:28px}#bk-box.on{display:block}
#bk-box .h{display:flex;justify-content:space-between;gap:16px;padding:16px 20px;border-bottom:1px solid var(--g200);font-size:14px}#bk-box .h span{font-size:11px;color:var(--g600)}
#bk-box .in{padding:20px}#bk-box p{font-size:12px;line-height:1.8;color:var(--g600)}
#bk-box pre{border:1px solid var(--g200);background:var(--paper);padding:16px;font:12px/1.9 var(--mono);white-space:pre-wrap;max-height:260px;overflow:auto;margin-top:14px}
#bk-box .btn{margin:14px 8px 0 0}
@media(max-width:760px){
 .random-hero{padding:30px 0 24px;gap:20px}.random-hero h1{font-size:40px}.pool-stamp{min-width:110px;padding-left:20px}.pool-stamp b{font-size:36px}
 .discovery-controls{padding:16px}.search-row{gap:12px}.dice-wrap{flex-wrap:wrap}.filters{flex-basis:100%}#roll{width:100%;min-height:48px}
 .card .c-main{gap:22px;padding:22px;grid-template-columns:minmax(180px,.8fr) minmax(0,1fr)}.card .c-title{font-size:30px}.card .c-top{padding:12px 22px}
 .recent,#result-box .recent{grid-template-columns:repeat(2,minmax(0,1fr))}.bk-list{display:none}.bk-txt{flex:1}.bk-btn{min-height:42px}
}
@media(max-width:520px){
 .random-hero{grid-template-columns:1fr;gap:20px}.random-hero h1{font-size:40px}.random-hero .lead{font-size:13px;margin-top:14px}.pool-stamp{display:none}
 .search-row{display:block}.preview-check{padding-top:8px;min-height:36px}.filters{grid-template-columns:1fr 1fr;gap:12px}.fsel:last-child{grid-column:1 / -1}
 .hint{font-size:10px}.hint .keyboard-hints{display:none}#roll .k{display:none}
 .card .c-main{display:flex;flex-direction:column;gap:24px;padding:18px}.card .big-art{max-width:100%;width:100%}.card .c-title{font-size:32px}
 .card .c-hd{width:100%}.card .c-actions .btn{flex:1}.card .c-top{padding:12px 18px}.card .c-one{margin-top:18px}
 .recent .r{padding:12px}.recent .rt{font-size:12px}.recent .ra{font-size:10px}.filter-summary{font-size:11px}
 #basket{gap:8px;padding:8px calc(14px + var(--sar,0px)) 8px calc(14px + var(--sal,0px))}#basket .bk-paw{width:22px}.bk-btn{padding:7px 10px;font-size:11px}
 #bk-box .h{display:block}#bk-box .h span{display:block;margin-top:6px}
}
@media(prefers-reduced-motion:reduce){.tt{display:none}.card.in{animation:none}#roll.rolling .vinyl{animation:none}}
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
const $=(s)=>document.querySelector(s);
const esc=(s)=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function safeURL(value){try{const u=new URL(value);return /^https?:$/.test(u.protocol)?u.href:''}catch{return ''}}
const strings=(a)=>Array.isArray(a)?a.filter(x=>typeof x==='string'):[];
const searchText=s=>String(s||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase().trim();
let POOL=[], ARTISTS={}, recent=[], current=null, au=null, seen=new Set();
let loaded=false, loadGeneration=0, rollGeneration=0, rollTimer=null, audioGeneration=0, pendingPlay=false;
const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const np=$('#np'), NC=$('#np-cover'), NT=$('#np-title'), NA=$('#np-artist'),
      NBAR=$('#np-bar'), NFILL=$('#np-fill'), NTIME=$('#np-time'), NTOG=$('#np-toggle');
const KEY='md_basket';
function loadBasket(){try{return [...new Set(MD.readList(sessionStorage,KEY,x=>typeof x==='string'&&x.trim().length>0&&x.length<1000))]}catch{return []}}
let hearts=loadBasket();
function saveBasket(){try{sessionStorage.setItem(KEY,JSON.stringify(hearts))}catch{MD.notify('浏览器未允许保存；篮子会保留到本次刷新前。')}}
function bkRender(pop=false){
  const el=$('#basket'), on=hearts.length>0;
  $('#bk-n').textContent=hearts.length;
  $('#bk-list').textContent=hearts.slice(-4).reverse().join(' · ');
  $('#bk-text').textContent=hearts.length?'今晚的篮子 · MUSIC DAILY\n'+hearts.join('\n'):'篮子还是空的。点一首歌旁边的「加入篮子」。';
  $('#bk-copy').disabled=!on;
  el.classList.toggle('on',on);
  document.body.classList.toggle('has-basket',on);
  if(pop&&on&&!reduced){el.classList.remove('pop');void el.offsetWidth;el.classList.add('pop');}
}
const fmt=(s)=>{s=Number.isFinite(s)&&s>0?Math.floor(s):0;return Math.floor(s/60)+':'+String(s%60).padStart(2,'0')};
function lcd(message){$('#boot').textContent=message;}
function playbackStatus(message){$('#play-status').textContent=message;}
function filtersActive(){return ['#f-mood','#f-genre','#f-decade','#f-search'].some(s=>$(s).value.trim())||$('#f-preview').checked;}
function match(t){
  const m=$('#f-mood').value, g=$('#f-genre').value, d=$('#f-decade').value;
  if(m&&!t.mood_tags.map(tgm).includes(m))return false;
  if(g&&!t.genres.some(x=>x.toLowerCase()===g))return false;
  if(d&&Math.floor(parseInt(t.year,10)/10)*10!==Number(d))return false;
  if($('#f-preview').checked&&!t.p)return false;
  const terms=searchText($('#f-search').value).split(/\s+/).filter(Boolean);
  const haystack=searchText([t.title,t.artist,t.album,...t.genres,...t.mood_tags.map(tgm)].join(' '));
  return terms.every(term=>haystack.includes(term));
}
function pool(){return POOL.filter(match);}
function lbData(t){
  const A=(k,v)=>' data-'+k+'="'+esc(v)+'"';
  const ac=ARTISTS[t.artist]||{};
  const entries=Array.isArray(ac.i)?ac.i:[];
  return A('id',t.id)+A('cover',t.c)+A('title',t.title)+A('artist',t.artist)+A('year',t.year)
    +A('years',ac.y||'')+A('g0',t.genres[0]||'')+A('album',t.album)+A('bpm',t.bpm_band||'')
    +A('tags',[...t.genres.slice(0,3),...t.mood_tags.slice(0,3).map(tgm)].join('|'))
    +A('bio',ac.b||'')+A('inpool',JSON.stringify(entries))
    +A('one',t.artist_oneliner||'')+A('why',t.why||'')+A('scene',t.scene||'')
    +A('apple',t.a)+A('spotify','https://open.spotify.com/search/'+encodeURIComponent(t.title+' '+t.artist))
    +A('netease','https://music.163.com/#/search/m/?s='+encodeURIComponent(t.title+' '+t.artist));
}
function knob(s){let n=0;for(const c of s||'x')n+=c.charCodeAt(0);return KNOB[n%KNOB.length];}
function render(t,animate=true){
  const gsel=$('#f-genre').value;
  const g0=t.genres.find(x=>x.toLowerCase()===gsel)||t.genres[0]||'music';
  const art=t.c?'<img class="cover" src="'+esc(t.c)+'" alt="'+esc(t.album||t.title)+' 专辑封面">'
    :'<div class="cover ph" aria-hidden="true">'+esc((t.artist||'?').slice(0,1).toUpperCase())+'</div>';
  const tags=[...t.genres.filter(g=>g!==g0).slice(0,2),...t.mood_tags.slice(0,2).map(tgm)]
    .map(x=>'<span class="tag">'+esc(x)+'</span>').join('');
  const meta=esc([t.year,t.album].filter(Boolean).join(' / '))
    +(t.bpm_band?'<span class="bpm">'+esc(t.bpm_band)+' bpm</span>':'');
  const key=t.title+' - '+t.artist, saved=hearts.includes(key);
  const query=encodeURIComponent(t.title+' '+t.artist);
  const links=(t.a?'<a class="btn solid" href="'+esc(t.a)+'" target="_blank" rel="noopener noreferrer">Apple Music ↗</a>':'')
    +'<a class="btn line" href="https://open.spotify.com/search/'+query+'" target="_blank" rel="noopener noreferrer">Spotify ↗</a>'
    +'<a class="btn line" href="https://music.163.com/#/search/m/?s='+query+'" target="_blank" rel="noopener noreferrer" data-nc="'+esc(t.title+' '+t.artist)+'">网易云 ↗</a>';
  const card=$('#card');card.className='card';card.removeAttribute('aria-busy');
  card.innerHTML='<div class="c-top"><span class="c-no">这一首 · '+String(seen.size).padStart(2,'0')+'</span>'
    +'<span class="c-tag"><span class="m-code" style="background:'+knob(g0)+'">'+esc(g0)+'</span></span></div>'
    +'<div class="c-main"><div class="big-art">'
    +'<button class="cover-open cover-zoom" type="button" aria-label="查看 '+esc(t.title)+' 的专辑与艺人详情"'+lbData(t)+'>'+art+'</button>'
    +(t.p?'<button class="pbtn" id="cpb" type="button" aria-label="播放试听" aria-pressed="false">'+PLAY+PAUSE+'</button>':'<span class="no-preview">暂无试听</span>')
    +'</div><div class="c-hd"><h2 class="c-title" tabindex="-1">'+esc(t.title)+'</h2>'
    +'<div class="c-artist">'+esc(t.artist)+'</div><div class="c-meta">'+meta+'</div><div class="tags">'+tags+'</div>'
    +(t.artist_oneliner?'<p class="c-one">'+esc(t.artist_oneliner)+'</p>':'')
    +(t.why?'<p class="c-why">'+esc(t.why)+'</p>':'')
    +(t.scene?'<p class="c-scene"><span class="k">适合</span> '+esc(t.scene)+'</p>':'')
    +'<div class="c-actions"><button class="btn basket-add'+(saved?' on':'')+'" id="chz" type="button" aria-pressed="'+saved+'">'+HEART+'<span>'+(saved?'已在篮子':'加入篮子')+'</span></button>'
    +'<button class="btn line" id="share-pick" type="button">复制歌曲链接</button></div>'
    +'<div class="c-links">'+links+'</div></div></div>';
  const cover=card.querySelector('img.cover');
  if(cover)cover.addEventListener('error',()=>{const ph=document.createElement('span');ph.className='cover ph';ph.textContent=t.artist.slice(0,1)||'♪';cover.replaceWith(ph);},{once:true});
  if(animate&&!reduced){
    const tt=document.createElement('div');tt.className='tt';tt.setAttribute('aria-hidden','true');
    tt.innerHTML='<div class="deck"><div class="dwrap"><div class="disc"><span class="disc-label">33⅓<br>MD</span></div></div><div class="arm"><i></i><b></b></div><span class="drop"></span></div><span class="led"></span>';
    card.querySelector('.big-art').appendChild(tt);
    setTimeout(()=>tt.remove(),2050);
    requestAnimationFrame(()=>{if(current?.id===t.id)card.classList.add('in');});
  }
  $('#cpb')?.addEventListener('click',toggle);
  $('#chz').addEventListener('click',()=>{
    const i=hearts.indexOf(key);if(i<0)hearts.push(key);else hearts.splice(i,1);
    const on=hearts.includes(key), button=$('#chz');
    button.classList.toggle('on',on);button.setAttribute('aria-pressed',String(on));
    button.querySelector('span').textContent=on?'已在篮子':'加入篮子';
    saveBasket();bkRender(on);MD.notify(on?'已加入今晚的临时篮子':'已从篮子移出');
  });
  $('#share-pick').addEventListener('click',e=>MD.copyText(location.href,e.currentTarget));
  try{const url=new URL(location.href);url.searchParams.set('t',t.id);history.replaceState(null,'',url);}catch{}
}
function mark(on){
  const b=$('#cpb');
  if(b){b.classList.toggle('playing',on);b.setAttribute('aria-pressed',String(on));b.setAttribute('aria-label',on?'暂停试听':'播放试听');b.disabled=pendingPlay;}
  np.classList.toggle('playing',on);
  NTOG.setAttribute('aria-label',on?'暂停试听':'播放试听');NTOG.setAttribute('aria-pressed',String(on));
  NTOG.disabled=!au||pendingPlay;
}
function resetProgress(){NFILL.style.width='0%';NTIME.textContent='0:00 / 0:00';NBAR.setAttribute('aria-valuenow','0');}
function stopPlayback(){
  audioGeneration++;pendingPlay=false;
  const old=au;au=null;
  if(old){old.pause();old.removeAttribute('src');old.load();}
  mark(false);resetProgress();
}
function showPlayer(t){
  NT.textContent=t.title;NA.textContent=t.artist;
  if(t.c){NC.src=t.c;NC.hidden=false;}else{NC.removeAttribute('src');NC.hidden=true;}
  np.classList.add('on');document.body.classList.add('has-player');
}
// play() can reject, including when autoplay is blocked; update controls from actual media events.
// https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/play
async function requestPlay(){
  if(!au||pendingPlay)return;
  const media=au, generation=audioGeneration;pendingPlay=true;mark(false);playbackStatus('正在加载试听…');
  try{await media.play();if(generation===audioGeneration)playbackStatus('正在试听 · 最长 30 秒');}
  catch(error){if(generation!==audioGeneration)return;mark(false);playbackStatus(error.name==='NotAllowedError'?'点击播放按钮，开始 30 秒试听。':'试听暂时不可用，可重试或前往音乐平台。');}
  finally{if(generation===audioGeneration){pendingPlay=false;mark(!media.paused);}}
}
function prepareAudio(t,autoplay){
  showPlayer(t);
  if(!t.p){playbackStatus('这首暂无试听，可前往音乐平台收听。');mark(false);return;}
  const media=new Audio(t.p), generation=audioGeneration;au=media;media.preload='none';
  const active=()=>generation===audioGeneration&&au===media;
  media.addEventListener('play',()=>{if(active())mark(true);});
  media.addEventListener('pause',()=>{if(active()){mark(false);if(!media.ended)playbackStatus('已暂停 · 点击播放继续');}});
  media.addEventListener('ended',()=>{if(active()){mark(false);playbackStatus('试听结束 · 可以重播或另起一首');}});
  media.addEventListener('error',()=>{if(active()){pendingPlay=false;mark(false);playbackStatus('试听加载失败，点击播放重试，或前往音乐平台。');}});
  media.addEventListener('timeupdate',()=>{
    if(!active())return;
    const duration=Math.min(media.duration||30,30), position=Math.min(media.currentTime,duration);
    NFILL.style.width=(position/duration*100)+'%';NTIME.textContent=fmt(position)+' / '+fmt(duration);
    NBAR.setAttribute('aria-valuenow',String(Math.round(position/duration*100)));
    NBAR.setAttribute('aria-valuetext',fmt(position)+'，共 '+fmt(duration));
    if(media.currentTime>=30&&!media.paused){media.pause();playbackStatus('30 秒试听结束 · 点击播放重播');}
  });
  mark(false);playbackStatus('点击播放，试听 30 秒。');if(autoplay)requestPlay();
}
function toggle(){
  if(pendingPlay)return;
  if(!au){if(current?.p)prepareAudio(current,true);return;}
  if(au.paused){if(au.error)au.load();if(au.ended||au.currentTime>=30)au.currentTime=0;requestPlay();}
  else au.pause();
}
NTOG.addEventListener('click',toggle);
$('#np-close').addEventListener('click',()=>{stopPlayback();np.classList.remove('on');document.body.classList.remove('has-player');playbackStatus('播放器已收起；点击封面上的播放按钮可继续。');$('#cpb')?.focus({preventScroll:true});});
NC.addEventListener('error',()=>{NC.hidden=true;});
function seek(fraction){if(!au||!Number.isFinite(au.duration)||au.duration<=0)return;au.currentTime=Math.max(0,Math.min(1,fraction))*Math.min(au.duration,30);}
NBAR.addEventListener('click',e=>{const rect=NBAR.getBoundingClientRect();if(rect.width)seek((e.clientX-rect.left)/rect.width);});
NBAR.addEventListener('keydown',e=>{
  if(!au||!Number.isFinite(au.duration))return;
  if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();
  const duration=Math.min(au.duration,30);
  seek(e.key==='Home'?0:e.key==='End'?1:(au.currentTime+(e.key==='ArrowRight'?5:-5))/duration);
});
function cancelRoll(){rollGeneration++;clearTimeout(rollTimer);rollTimer=null;$('#roll').classList.remove('rolling');$('#roll').removeAttribute('aria-busy');}
function choose(t,autoplay=false,animate=true){
  cancelRoll();stopPlayback();current=t;seen.add(t.id);render(t,animate);prepareAudio(t,autoplay);
  recent=[t,...recent.filter(x=>x.id!==t.id)].slice(0,8);renderTrackButtons('#recent',recent);
  lcd('这一首 · '+t.title+' — '+t.artist);updateCounts();
}
function renderTrackButtons(selector,tracks){
  const node=$(selector);node.replaceChildren();
  tracks.forEach(t=>{
    const button=document.createElement('button');button.type='button';button.className='r';button.dataset.id=t.id;
    button.setAttribute('aria-label','选择 '+t.title+'，'+t.artist);
    const title=document.createElement('span');title.className='rt';title.textContent=t.title;
    const artist=document.createElement('span');artist.className='ra';artist.textContent=t.artist;
    button.append(title,artist);button.addEventListener('click',()=>{choose(t,true,false);$('#card .c-title').focus({preventScroll:true});});
    node.appendChild(button);
  });
}
function cardState(title,detail,action=''){
  const card=$('#card');card.className='card empty';card.removeAttribute('aria-busy');
  card.innerHTML='<div class="state-content"><span class="state-record" aria-hidden="true">◎</span><h2>'+esc(title)+'</h2><p>'+esc(detail)+'</p>'
    +(action?'<button class="btn solid" id="state-action" type="button">'+(action==='retry'?'重新加载':'重置筛选')+'</button>':'')+'</div>';
  if(action)$('#state-action').addEventListener('click',action==='retry'?loadPool:resetFilters);
}
function updateCounts(){
  const matches=pool();$('#filter-count').textContent=loaded?matches.length.toLocaleString()+' 首符合条件 / 共 '+POOL.length.toLocaleString()+' 首':'曲库加载中…';
  $('#f-reset').disabled=!filtersActive();$('#roll').disabled=!loaded||!matches.length;
  $('#result-box').hidden=!filtersActive()||!matches.length;
  $('#result-label').textContent='筛选结果 · '+(matches.length>8?'先看看这 8 首，或继续随机抽取':'点击直接试听');
  renderTrackButtons('#search-results',filtersActive()?matches.slice(0,8):[]);
  return matches;
}
function filtersChanged(){
  if(!loaded)return;cancelRoll();seen.clear();const matches=updateCounts();
  if(!matches.length){stopPlayback();current=null;np.classList.remove('on');document.body.classList.remove('has-player');playbackStatus('');cardState('还没有匹配的歌','换一个关键词，或减少筛选条件。','reset');lcd('0 首符合条件 · 可以重置筛选');}
  else if(!current||!match(current)){stopPlayback();current=null;np.classList.remove('on');document.body.classList.remove('has-player');playbackStatus('');cardState('给下一首留一点悬念',matches.length+' 首准备好了。点「另起一首」，或直接选择上面的搜索结果。');lcd(matches.length+' 首准备好了');}
  else{const badge=$('#card .m-code'), selected=current.genres.find(g=>g.toLowerCase()===$('#f-genre').value)||current.genres[0]||'music';if(badge){badge.textContent=selected;badge.style.background=knob(selected);}}
}
function resetFilters(){['#f-mood','#f-genre','#f-decade','#f-search'].forEach(s=>$(s).value='');$('#f-preview').checked=false;filtersChanged();if(POOL.length)roll(false);}
function roll(autoplay=true){
  if(!loaded||rollTimer!==null)return;
  const list=pool();if(!list.length){filtersChanged();return;}
  let fresh=list.filter(t=>!seen.has(t.id));if(!fresh.length){seen.clear();fresh=list;}
  if(fresh.length>1&&current)fresh=fresh.filter(t=>t.id!==current.id);
  const selected=fresh[Math.floor(Math.random()*fresh.length)];
  const generation=++rollGeneration;$('#roll').classList.add('rolling');$('#roll').setAttribute('aria-busy','true');lcd('唱片转起来了…');
  rollTimer=setTimeout(()=>{if(generation!==rollGeneration)return;rollTimer=null;choose(selected,autoplay);},reduced?0:220);
}
function fill(selector,counts,label,chronological=false){
  const select=$(selector), previous=select.value;select.replaceChildren(new Option(label,''));
  Object.entries(counts).sort((a,b)=>chronological?Number(a[0])-Number(b[0]):b[1]-a[1]||a[0].localeCompare(b[0]))
    .forEach(([key,count])=>select.add(new Option(key+(chronological?'s':'')+' · '+count,key)));
  if([...select.options].some(o=>o.value===previous))select.value=previous;
}
function normalizePool(data){
  if(!Array.isArray(data))throw new Error('invalid pool');
  const ids=new Set();
  return data.filter(t=>t&&typeof t==='object'&&typeof t.id==='string'&&t.id&&typeof t.title==='string'&&t.title&&typeof t.artist==='string'&&t.artist)
    .filter(t=>{if(ids.has(t.id))return false;ids.add(t.id);return true;})
    .map(t=>({...t,c:safeURL(t.c),p:safeURL(t.p),a:safeURL(t.a),genres:strings(t.genres),mood_tags:strings(t.mood_tags),album:typeof t.album==='string'?t.album:''}));
}
// Fetch does not reject HTTP 404/500; validate status and provide a bounded retryable load.
// https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch
async function fetchJSON(url){
  const controller=new AbortController(), timeout=setTimeout(()=>controller.abort(),12000);
  try{const response=await fetch(url,{signal:controller.signal});if(!response.ok)throw new Error('HTTP '+response.status);return await response.json();}
  finally{clearTimeout(timeout);}
}
async function loadPool(){
  const generation=++loadGeneration;loaded=false;cancelRoll();stopPlayback();$('#roll').disabled=true;
  document.querySelectorAll('.filter-control').forEach(el=>el.disabled=true);
  cardState('正在打开唱片箱','曲库加载完成后，就可以搜索、筛选或另起一首。');$('#card').setAttribute('aria-busy','true');lcd('正在加载曲库…');
  try{
    const data=normalizePool(await fetchJSON('pool.min.json'));if(generation!==loadGeneration)return;
    if(!data.length)throw new Error('empty pool');POOL=data;loaded=true;
    const mc=Object.create(null),gc=Object.create(null),dc=Object.create(null);
    data.forEach(t=>{new Set(t.mood_tags.map(tgm)).forEach(k=>mc[k]=(mc[k]||0)+1);new Set(t.genres.map(g=>g.toLowerCase())).forEach(k=>gc[k]=(gc[k]||0)+1);const y=parseInt(t.year,10);if(y){const k=Math.floor(y/10)*10;dc[k]=(dc[k]||0)+1;}});
    fill('#f-mood',mc,'全部心情');fill('#f-genre',gc,'全部流派');fill('#f-decade',dc,'全部年代',true);
    document.querySelectorAll('.filter-control').forEach(el=>el.disabled=false);updateCounts();
    const query=new URLSearchParams(location.search).get('t'), seed=query?POOL.find(t=>t.id===query):null;
    if(seed)choose(seed,false,false);else{if(query)MD.notify('这首歌暂时不在曲库里，先为你换一首。');roll(false);}
  }catch(error){if(generation!==loadGeneration)return;cardState('曲库暂时没打开','检查网络后重试。你在这次会话里的篮子还在。','retry');$('#filter-count').textContent='加载失败';lcd('曲库加载失败 · 可以重试');}
}
async function loadArtists(){
  try{
    const data=await fetchJSON('artists.min.json');
    if(!data||typeof data!=='object'||Array.isArray(data))return;ARTISTS=data;
    const cover=$('#card .cover-open'), ac=current&&ARTISTS[current.artist];
    if(cover&&ac){cover.dataset.bio=typeof ac.b==='string'?ac.b:'';cover.dataset.years=typeof ac.y==='string'?ac.y:'';cover.dataset.inpool=JSON.stringify(Array.isArray(ac.i)?ac.i:[]);$('#lb')?.dispatchEvent(new CustomEvent('refresh',{detail:cover.dataset}));}
  }catch{/* Artist context is optional: the music pool remains usable. */}
}
$('#roll').addEventListener('click',()=>roll(true));
['#f-mood','#f-genre','#f-decade','#f-preview'].forEach(s=>$(s).addEventListener('change',filtersChanged));
$('#f-search').addEventListener('input',filtersChanged);$('#f-reset').addEventListener('click',resetFilters);
$('#bk-export').addEventListener('click',()=>{bkRender();$('#bk-box').classList.add('on');$('#bk-box').scrollIntoView({behavior:reduced?'auto':'smooth',block:'center'});$('#bk-copy').focus({preventScroll:true});});
let clearedBasket=[];
$('#bk-clear').addEventListener('click',()=>{clearedBasket=hearts.slice();hearts=[];saveBasket();bkRender();$('#bk-box').classList.add('on');$('#bk-undo').hidden=false;$('#bk-undo').focus();if(current){const h=$('#chz');h?.classList.remove('on');h?.setAttribute('aria-pressed','false');if(h)h.querySelector('span').textContent='加入篮子';}MD.notify('篮子已清空，可在导出面板撤销。');});
$('#bk-undo').addEventListener('click',()=>{hearts=[...new Set([...hearts,...clearedBasket])];clearedBasket=[];saveBasket();bkRender();$('#bk-undo').hidden=true;$('#bk-copy').focus();if(current&&hearts.includes(current.title+' - '+current.artist)){const h=$('#chz');h?.classList.add('on');h?.setAttribute('aria-pressed','true');if(h)h.querySelector('span').textContent='已在篮子';}MD.notify('已恢复篮子。');});
$('#bk-copy').addEventListener('click',e=>MD.copyText($('#bk-text').textContent,e.currentTarget,$('#bk-text')));
document.addEventListener('keydown',e=>{
  if(e.defaultPrevented||e.repeat||e.ctrlKey||e.metaKey||e.altKey||$('#lb')?.classList.contains('on'))return;
  if(e.target.closest('input,textarea,select,button,a,[role="button"],[role="slider"],[contenteditable="true"]'))return;
  if(e.code==='Space'){e.preventDefault();roll(true);}else if(e.key.toLowerCase()==='p'){e.preventDefault();toggle();}else if(e.key==='/'){e.preventDefault();$('#f-search').focus();}
});
window.addEventListener('pagehide',()=>{cancelRoll();stopPlayback();});
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
    js = UI_JS + (f"const TAGMAP={json.dumps(TAG_MAP, ensure_ascii=False)};\n"
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
{site_nav('random')}

<main class="wrap" id="main">
  <div class="random-hero">
    <div>
      <div class="eyebrow">OFF THE BEATEN TRACK / 随机发现</div>
      <h1>今天，<br>听点<span>别的。</span></h1>
      <p class="lead">放下熟悉的循环，给下一首一点偶然。按心情挑，也可以让唱片自己转到你面前。</p>
    </div>
    <div class="pool-stamp"><b>{n_total:,}</b>首歌，慢慢遇见<br>每次只选一首。</div>
  </div>

  <div class="lcd">
    <div class="row1"><span class="dot"></span><span id="boot" role="status" data-text="{_esc(boot)}">正在打开唱片箱…</span>
      <div class="cat-wrap"><div class="cat-move">{ICON_CAT}</div><span class="prop bowl">{ICON_BOWL}</span><span class="prop ball">{ICON_BALL}</span></div></div>
  </div>

  <section class="discovery-controls" aria-label="搜索和筛选曲库">
  <div class="search-row">
    <label class="field search-field" for="f-search">找一首歌、一位音乐人，或一种声音
      <input class="filter-control" id="f-search" type="search" placeholder="搜索歌名、艺人、专辑、流派…" autocomplete="off" disabled>
    </label>
    <label class="preview-check"><input class="filter-control" id="f-preview" type="checkbox" disabled>只看有试听的歌</label>
  </div>
  <div class="dice-wrap">
    <div class="filters">
      <label class="fsel" for="f-mood"><span class="lbl">心情</span><select class="filter-control" id="f-mood" disabled><option value="">全部心情</option></select></label>
      <label class="fsel" for="f-genre"><span class="lbl">流派</span><select class="filter-control" id="f-genre" disabled><option value="">全部流派</option></select></label>
      <label class="fsel" for="f-decade"><span class="lbl">年代</span><select class="filter-control" id="f-decade" disabled><option value="">全部年代</option></select></label>
    </div>
    <button id="roll" type="button" disabled>{ICON_DICE}<span class="lab">另起一首</span><span class="k">SPACE</span></button>
  </div>
  <div class="filter-summary"><span id="filter-count" role="status">曲库加载中…</span><button id="f-reset" type="button" disabled>重置筛选</button></div>
  <div class="hint"><span class="keyboard-hints"><kbd>space</kbd> 另起一首 · <kbd>p</kbd> 播放 / 暂停 · <kbd>/</kbd> 搜索　</span>试听最长 30 秒 · 篮子只保留在本次会话</div>
  <section id="result-box" hidden aria-labelledby="result-label"><p id="result-label"></p><div class="recent" id="search-results"></div></section>
  </section>

  <div class="sect">给现在的你 / THE PICK</div>
  <article class="card" id="card" aria-busy="true"><div class="state-content">正在加载曲库…</div></article>
  <p id="play-status" role="status"></p>

  <div class="sect">刚刚遇见 / RECENT PICKS</div>
  <div class="recent" id="recent"></div>

  <section id="bk-box">
    <div class="h">今晚的篮子 <span>本次会话临时保存 · 与今日精选的长期收藏独立</span></div>
    <div class="in">
      <p>复制下列清单 → 网易云 App「新建歌单 → 导入」。想长期留着，请去日报页用 ♥ 收藏。</p>
      <pre id="bk-text"></pre>
      <button class="btn solid" id="bk-copy" type="button">复制清单</button>
      <button class="btn line" id="bk-undo" type="button" hidden>撤销清空</button>
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
  <button class="bk-btn line" id="bk-clear" type="button">清空</button>
</div>

<div id="np" role="region" aria-label="试听播放器">
  <img id="np-cover" alt="">
  <div id="np-meta"><div id="np-title"></div><div id="np-artist"></div></div>
  <button id="np-toggle" class="np-btn" type="button" aria-label="播放试听" aria-pressed="false" disabled>{ICON_PLAY}{ICON_PAUSE}</button>
  <div id="np-bar" role="slider" tabindex="0" aria-label="试听进度" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><div id="np-fill"></div></div>
  <span id="np-time" class="mono">0:00 / 0:00</span>
  <button id="np-close" class="np-btn" type="button" aria-label="停止并收起播放器">×</button>
</div>

{LIGHTBOX_HTML}
<script>{js}</script>
<script>{lightbox_js('.cover-open')}</script>
<script>{NETEASE_OPEN_JS}</script>
</body>
</html>"""
