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
#roll .k{font-size:var(--fs-10); color:var(--g300); letter-spacing:.06em; position:relative; z-index:1}
#roll .lab{position:relative; z-index:1}
/* 按下时从中心荡开的波纹 */
#roll::after{content:""; position:absolute; left:50%; top:50%; width:8px; height:8px;
  background:rgba(255,255,255,.28); transform:translate(-50%,-50%) scale(0); opacity:0}
#roll.ping::after{animation:ping .5s ease-out}
@keyframes ping{0%{transform:translate(-50%,-50%) scale(0);opacity:.7}
  100%{transform:translate(-50%,-50%) scale(34);opacity:0}}
/* 图标 */
#roll .dice{width:40px; height:36px; display:inline-block; flex:none; position:relative; z-index:1;
  image-rendering:pixelated}
#roll .dice g{transform-box:fill-box; transform-origin:center}
#roll .dice .paw{transform-origin:72% 95%; transition:transform .18s cubic-bezier(.34,1.56,.64,1)}
#roll:hover .dice .paw{transform:translateY(-2.5px) rotate(-4deg)}
#roll:active .dice .paw{transform:translateY(1px)}
#roll.rolling .dice .paw{animation:paw-tap .42s ease-in-out infinite}
#roll.rolling .dice .disc,#roll.rolling .dice .disc-in{animation:disc-wob .42s ease-in-out infinite}
#roll.rolling .dice .note{animation:note-pop .84s ease-out infinite}
@keyframes paw-tap{0%,100%{transform:translateY(-3px) rotate(-5deg)}50%{transform:translateY(1px) rotate(2deg)}}
@keyframes disc-wob{0%,100%{transform:scaleY(1)}50%{transform:scaleY(.78) translateY(1.5px)}}
@keyframes note-pop{0%{opacity:0;transform:translate(0,0)}
  25%{opacity:1;transform:translate(1px,-3px)}
  70%{opacity:.7;transform:translate(3px,-7px)}
  100%{opacity:0;transform:translate(4px,-10px)}}

.hint{font-family:var(--mono); font-size:var(--fs-10); color:var(--g600); margin-top:8px}
.hint b{color:var(--ink); font-weight:400}
.hint kbd{border:1px solid var(--g300); padding:1px 6px; background:var(--white)}

/* 单张大卡 */
.card{border:1px solid var(--g300); background:var(--paper); margin-top:var(--sp-md);
  opacity:0; transform:translateY(8px); transition:opacity .38s ease-out, transform .38s ease-out;
  position:relative; overflow:hidden}
.card.in{opacity:1; transform:none}
/* 揭晓瞬间：顶栏一道扫光 */
.card.in .c-top::after{content:""; position:absolute; left:0; top:0; height:100%; width:38%;
  background:linear-gradient(90deg,transparent,rgba(0,166,81,.16),transparent);
  animation:sweep .75s ease-out 1 forwards; pointer-events:none}
@keyframes sweep{from{transform:translateX(-120%)}to{transform:translateX(360%)}}
/* 封面揭晓：像在唱片箱里一张张往后翻，最后一张落定（flip 层由 JS 塞入前几张候选封面）*/
.card .big-art{perspective:900px}
.card .big-art .cover{animation:art-land .34s cubic-bezier(.2,.9,.3,1.1) both}
@keyframes art-land{from{opacity:0; transform:rotateY(-38deg) translateX(-9%) scale(.96)}
  to{opacity:1; transform:none}}
.flipper{position:absolute; inset:0; pointer-events:none; z-index:2}
.flipper .fc{position:absolute; inset:0; background-size:cover; background-position:center;
  background-color:var(--g100); transform-origin:left center; backface-visibility:hidden;
  box-shadow:2px 0 8px rgba(0,0,0,.18); animation:flip-away .26s ease-in forwards}
@keyframes flip-away{
  0%{transform:rotateY(0) translateZ(0); opacity:1}
  100%{transform:rotateY(-118deg) translateZ(14px); opacity:0}}
/* 文字块错峰上浮 */
.card.in .c-title{animation:rise .42s ease-out .04s both}
.card.in .c-artist{animation:rise .42s ease-out .09s both}
.card.in .c-meta,.card.in .tags{animation:rise .42s ease-out .14s both}
.card.in .c-one,.card.in .c-why{animation:rise .42s ease-out .19s both}
.card.in .c-scene,.card.in .c-links{animation:rise .42s ease-out .24s both}
@keyframes rise{from{opacity:0; transform:translateY(7px)}to{opacity:1; transform:none}}
.card .c-top{display:flex; align-items:center; justify-content:space-between;
  padding:12px 16px; border-bottom:1px solid var(--g100)}
.card .c-no{font-family:var(--mono); font-size:var(--fs-10); color:var(--g600);
  text-transform:uppercase; letter-spacing:.1em}
.card .c-tag{display:inline-flex; gap:8px; align-items:center}
.card .c-main{display:flex; gap:var(--sp-lg); padding:var(--sp-lg); flex-wrap:wrap}
.card .big-art{position:relative; width:clamp(150px,22vw,232px); aspect-ratio:1; flex:none}
.card .big-art .cover{width:100%; height:100%; object-fit:cover; display:block;
  background:var(--g100); border:1px solid var(--g100)}
.card .big-art .cover.ph{display:grid; place-items:center; font-family:var(--mono);
  font-size:var(--fs-40); font-weight:400; color:var(--white); background:var(--ink); border:none;
  background-image:repeating-linear-gradient(45deg,rgba(255,255,255,.06) 0 8px,transparent 8px 16px)}
.card .big-art .pbtn{left:10px; bottom:10px; width:38px; height:38px}
.card .big-art .pbtn svg{width:15px; height:15px}
.card .c-hd{flex:1; min-width:240px; display:flex; flex-direction:column}
.card .c-title{font-size:var(--fs-30); font-weight:100; line-height:1.08; letter-spacing:-.015em}
.card .c-artist{font-family:var(--mono); font-size:var(--fs-15); text-transform:uppercase;
  color:var(--g900); margin-top:8px; letter-spacing:.03em}
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
#basket .bk-paw rect{fill:var(--ink)}
#basket.pop .bk-paw{animation:bk-stamp .42s cubic-bezier(.34,1.56,.64,1)}
@keyframes bk-stamp{0%{transform:translateY(-7px) rotate(-8deg)}55%{transform:translateY(2px) rotate(3deg)}100%{transform:none}}
#basket .bk-txt{font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase;
  color:var(--g900); letter-spacing:.04em; flex:none}
#basket .bk-n{display:inline-block; min-width:1.4em; text-align:center; color:var(--ink);
  font-size:var(--fs-20); font-weight:700; letter-spacing:0}
#basket.pop .bk-n{animation:bk-bump .38s cubic-bezier(.34,1.56,.64,1)}
@keyframes bk-bump{0%{transform:scale(1)}45%{transform:scale(1.45)}100%{transform:scale(1)}}
#basket .bk-list{flex:1; min-width:0; font-family:var(--mono); font-size:var(--fs-10);
  color:var(--g600); white-space:nowrap; overflow:hidden; text-overflow:ellipsis}
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
.recent .r .ra{font-family:var(--mono); font-size:9px; color:var(--g600);
  text-transform:uppercase; margin-top:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis}
@media(max-width:720px){
  .recent{grid-template-columns:repeat(2,1fr)}
  #roll{flex:1 1 100%; min-width:0}
  .fsel{flex:1 1 50%}
}
@media(prefers-reduced-motion:reduce){
  .card,.card .big-art .cover,.flipper,.card.in .c-title,.card.in .c-artist,.card.in .c-meta,.card.in .tags,
  .card.in .c-one,.card.in .c-why,.card.in .c-scene,.card.in .c-links{
    opacity:1; transform:none; transition:none; animation:none; filter:none}
  .card.in .c-top::after,#roll.ping::after{animation:none; display:none}
  #roll .dice g{animation:none !important}
  #roll.rolling .dice{animation:none}
}
"""

ICON_DICE = (
    # 40px 尺寸下的完整叙事：大黑胶（外圈 + 沟槽 + 中孔）+ 萌猫爪压住右上缘（4 圆趾 + 粉肉垫）
    '<svg class="dice" viewBox="0 0 40 36" shape-rendering="crispEdges" aria-hidden="true">'
    # ── 黑胶唱片 ──
    '<g class="disc" fill="#fff">'
    '<rect x="10" y="9" width="16" height="1"/><rect x="7" y="10" width="22" height="1"/>'
    '<rect x="5" y="11" width="26" height="1"/><rect x="4" y="12" width="28" height="14"/>'
    '<rect x="5" y="26" width="26" height="1"/><rect x="7" y="27" width="22" height="1"/>'
    '<rect x="10" y="28" width="16" height="1"/>'
    '</g>'
    '<g class="disc-in" fill="#0f0e12">'
    '<rect x="9" y="13" width="18" height="1" opacity=".45"/>'
    '<rect x="8" y="15" width="20" height="1" opacity=".45"/>'
    '<rect x="8" y="22" width="20" height="1" opacity=".45"/>'
    '<rect x="9" y="24" width="18" height="1" opacity=".45"/>'
    '<rect x="14" y="17" width="8" height="4"/>'
    '</g>'
    '<g class="disc-c" fill="#f05a24"><rect x="16" y="18" width="4" height="2"/></g>'   # 唱片标签（橙心）
    # ── 猫爪：压在右上，4 圆趾 + 掌 + 粉垫 ──
    '<g class="paw">'
    '<g fill="#fff">'
    '<rect x="21" y="2" width="3" height="1"/><rect x="20" y="3" width="5" height="3"/><rect x="21" y="6" width="3" height="1"/>'
    '<rect x="27" y="0" width="3" height="1"/><rect x="26" y="1" width="5" height="3"/><rect x="27" y="4" width="3" height="1"/>'
    '<rect x="33" y="2" width="3" height="1"/><rect x="32" y="3" width="5" height="3"/><rect x="33" y="6" width="3" height="1"/>'
    '<rect x="23" y="7" width="13" height="1"/><rect x="22" y="8" width="15" height="6"/>'
    '<rect x="23" y="14" width="13" height="1"/>'
    '</g>'
    '<g class="pad" fill="#f05a24">'
    '<rect x="26" y="9" width="7" height="4"/>'
    '<rect x="21" y="4" width="3" height="1"/><rect x="27" y="2" width="3" height="1"/><rect x="33" y="4" width="3" height="1"/>'
    '</g>'
    '</g>'
    # ── 音符（按下时从左侧飘）──
    '<g class="note" fill="#fff" opacity="0">'
    '<rect x="1" y="4" width="1" height="6"/><rect x="2" y="3" width="3" height="1"/>'
    '<rect x="0" y="10" width="3" height="2"/>'
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
  if(m && !(t.mood_tags||[]).includes(m))return false;
  if(g && !((t.genres||[]).map(x=>x.toLowerCase()).includes(g)))return false;
  if(d){const y=parseInt(t.year||'0',10); if(!y||Math.floor(y/10)*10!==parseInt(d,10))return false;}
  return true;
}
function pool(){return POOL.filter(match)}

function render(t){
  const art=t.c?('<img class="cover" src="'+t.c+'" alt="">')
                :('<div class="cover ph">'+((t.artist||'?')[0]||'?').toUpperCase()+'</div>');
  const pb=t.p?('<button class="pbtn" id="cpb" type="button" aria-label="\\u8bd5\\u542c 30 \\u79d2">'+PLAY+PAUSE+'</button>'):'';
  const g0=(t.genres||['\\u2014'])[0];
  const tags=[].concat((t.genres||[]).slice(1,3),(t.mood_tags||[]).slice(0,2))
    .map(x=>'<span class="tag">'+x+'</span>').join('');
  const bpmC=(bb)=>{const n=String(bb||'').match(/\\d+/g); if(!n)return '';
    const m=(+n[0]+ +n[n.length-1])/2;
    return m<85?'#0071bb':m<105?'#006837':m<125?'#fab413':'#f05a24';};
  const meta=[t.year,t.album].filter(Boolean).join(' / ')
    +(t.bpm_band?('<span class="bpm" style="--bc:'+bpmC(t.bpm_band)+'">'+t.bpm_band+' bpm</span>'):'');
  const on=hearts.indexOf(t.title+' - '+t.artist)>=0?' on':'';
  const links=(t.a?'<a class="btn solid" href="'+t.a+'" target="_blank" rel="noopener">listen</a>':'')
    +'<a class="btn line" href="https://open.spotify.com/search/'+encodeURIComponent(t.title+' '+t.artist)+'" target="_blank" rel="noopener">spotify \\u2197</a>'
    +'<a class="btn line" href="https://music.163.com/#/search/m/?s='+encodeURIComponent(t.title+' '+t.artist)+'" target="_blank" rel="noopener">netease \\u2197</a>'
    +'<button class="heart'+on+'" id="chz" type="button" data-k="'+(t.title+' - '+t.artist).replace(/"/g,'&quot;')+'" aria-label="\\u6536\\u85cf">'+HEART+'</button>';
  const card=$('#card');
  card.className='card';
  card.innerHTML='<div class="c-top"><span class="c-no">pick \\u00b7 '+String(seen.length).padStart(3,'0')+' / '+pool().length+'</span>'
    +'<span class="c-tag"><span class="m-code" style="background:'+knob(g0)+'">'+g0+'</span></span></div>'
    +'<div class="c-main"><div class="big-art">'+art+pb+'</div>'
    +'<div class="c-hd"><div class="c-title lc">'+t.title+'</div>'
    +'<div class="c-artist">'+t.artist+'</div><div class="c-meta">'+meta+'</div>'
    +'<div class="tags" style="margin-top:10px">'+tags+'</div>'
    +'<div class="c-one">'+(t.artist_oneliner||'')+'</div>'
    +'<div class="c-why">'+(t.why||'')+'</div>'
    +'<div class="c-scene"><span class="k">use \\u25b8</span> '+(t.scene||'')+'</div>'
    +'<div class="c-links">'+links+'</div></div></div>';
  // 翻唱片：往封面上叠几张候选封面，依次快速翻走，露出这次抽到的
  (function(){
    const art=card.querySelector('.big-art'); if(!art)return;
    const shuf=POOL.filter(x=>x.c&&x.id!==t.id).sort(()=>Math.random()-0.5).slice(0,5);
    if(!shuf.length)return;
    const fl=document.createElement('div'); fl.className='flipper';
    shuf.forEach((x,k)=>{
      const d=document.createElement('div'); d.className='fc';
      d.style.backgroundImage='url("'+x.c+'")';
      d.style.zIndex=String(shuf.length-k);
      d.style.animationDelay=(k*0.055)+'s';
      fl.appendChild(d);
    });
    art.appendChild(fl);
    setTimeout(()=>fl.remove(), 700);
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
  const btn=$('#roll'); btn.classList.add('rolling');
  const t0=Date.now(), spin=setInterval(()=>{
    const s=fresh[Math.floor(Math.random()*fresh.length)];
    lcd('\\u25b8 '+s.title+' \\u2014 '+s.artist);
    if(Date.now()-t0>620){
      clearInterval(spin); btn.classList.remove('rolling');
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
  d.forEach(t=>{(t.mood_tags||[]).forEach(m=>mc[m]=(mc[m]||0)+1);
    (t.genres||[]).forEach(g=>{g=g.toLowerCase();gc[g]=(gc[g]||0)+1});
    const y=parseInt(t.year||'0',10); if(y){const k=Math.floor(y/10)*10; dc[k]=(dc[k]||0)+1}});
  const top=(o,n)=>Object.entries(o).sort((a,b)=>b[1]-a[1]).slice(0,n).map(([k,v])=>[k,k+' ('+v+')']);
  fill('#f-mood',top(mc,14).map(([k,lbl])=>[k,(TAGMAP[k]||TAGMAP[k.toLowerCase()]||k)+lbl.slice(lbl.indexOf(' ('))]),'\\u5168\\u90e8\\u6c14\\u8d28');
  fill('#f-genre',top(gc,18),'\\u5168\\u90e8\\u6d41\\u6d3e');
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
    txt.textContent='今晚的篮子 · music daily\\n'+hearts.join('\\n');
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
<title>music daily · shuffle · 今天听点别的</title>
<link rel="icon" href="{favicon}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@100;300;400&family=Space+Mono:wght@400;700&family=Noto+Sans+SC:wght@100;300;400&display=swap" rel="stylesheet">
<style>{CSS}{EXTRA_CSS}</style>
</head>
<body>
<nav class="nav">
  <div class="wrap">
    <div class="brand lc"><span class="sq"></span>music daily</div>
    <div class="serial"><span>mode <b>shuffle</b></span><span>pool <b>{n_total}</b></span>
      <span><a href="index.html" style="border-bottom:1px solid var(--g300)">← 今日精选</a></span></div>
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
      <div class="cat-wrap">{ICON_CAT}<span class="prop bowl">{ICON_BOWL}</span><span class="prop ball">{ICON_BALL}</span></div></div>
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
    <span>music daily · shuffle</span>
    <span><a href="index.html" style="border-bottom:1px solid var(--g300)">今日精选 →</a></span>
    <span>cover &amp; preview via public music api · personal use</span>
  </footer>
</main>

<div id="basket" aria-live="polite">
  <svg class="bk-paw" viewBox="0 0 24 22" shape-rendering="crispEdges" aria-hidden="true">
    <rect x="3" y="3" width="3" height="3"/><rect x="8" y="1" width="3" height="3"/>
    <rect x="13" y="1" width="3" height="3"/><rect x="18" y="3" width="3" height="3"/>
    <rect x="5" y="7" width="14" height="4"/><rect x="6" y="11" width="12" height="1"/>
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

<script>{js}</script>
</body>
</html>"""
