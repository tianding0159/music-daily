"""渲染独立的「今天听点别的」随机页（site/random.html）+ 精简池 JSON（site/pool.min.json）。

设计延续日报页的工程 / 网格视觉语言（Inter 极细 + Space Mono、方角、发丝线、方格纸、LCD 绿），
但交互是"拆盲盒"：一次只给一首、巨型摇一摇按钮 + LCD 洗牌动画 + 30s 试听自动播。
纯前端随机（读 pool.min.json），零后端；收藏与日报页共用 localStorage 的 md_hearts。

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
.fsel select{appearance:none; width:100%; height:100%; min-height:56px; padding:10px 28px 10px 14px;
  border:none; background:transparent; color:var(--ink); cursor:pointer;
  font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase; letter-spacing:.04em}
.fsel::after{content:"▾"; position:absolute; right:11px; top:50%; transform:translateY(-50%);
  font-family:var(--mono); font-size:var(--fs-10); color:var(--g600); pointer-events:none}
.fsel .lbl{position:absolute; left:14px; top:6px; font-family:var(--mono); font-size:9px;
  color:var(--g500); text-transform:uppercase; letter-spacing:.1em; pointer-events:none}
.fsel select{padding-top:20px}
#roll{flex:0 0 auto; min-width:clamp(160px,26vw,260px); border:none; cursor:pointer;
  background:var(--ink); color:var(--white); font-family:var(--mono); font-size:var(--fs-20);
  text-transform:uppercase; letter-spacing:.08em; padding:18px 26px; display:flex;
  align-items:center; justify-content:center; gap:12px; transition:background .2s, transform .1s}
#roll:hover{background:var(--g1000)}
#roll:active{transform:scale(.985)}
#roll.rolling{background:var(--green-d)}
#roll .k{font-size:var(--fs-10); color:var(--g300); letter-spacing:.06em}
#roll .dice{width:23px; height:15px; display:inline-block; flex:none}
#roll .dice g{transition:transform .2s}
#roll:hover .a1{transform:translateX(1.5px)}
#roll:hover .a2{transform:translateX(-1.5px)}
#roll.rolling .a1{animation:sw1 .42s ease-in-out infinite}
#roll.rolling .a2{animation:sw2 .42s ease-in-out infinite}
@keyframes sw1{0%,100%{transform:translateX(0)}50%{transform:translateX(3px)}}
@keyframes sw2{0%,100%{transform:translateX(0)}50%{transform:translateX(-3px)}}
.hint{font-family:var(--mono); font-size:var(--fs-10); color:var(--g600); margin-top:8px}
.hint b{color:var(--ink); font-weight:400}
.hint kbd{border:1px solid var(--g300); padding:1px 6px; background:var(--white)}

/* 单张大卡 */
.card{border:1px solid var(--g300); background:var(--paper); margin-top:var(--sp-md);
  opacity:0; transform:translateY(6px); transition:opacity .35s ease-out, transform .35s ease-out}
.card.in{opacity:1; transform:none}
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
.card .c-one{font-family:var(--mono); font-size:var(--fs-10); color:var(--g600);
  line-height:1.7; margin-top:14px}
.card .c-why{font-size:var(--fs-20); font-weight:300; line-height:1.5; margin-top:10px}
.card .c-scene{font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase;
  color:var(--g900); margin-top:14px}
.card .c-scene .k{color:var(--orange)}
.card .c-links{display:flex; gap:8px; margin-top:auto; padding-top:18px; align-items:center; flex-wrap:wrap}
.card.empty .c-main{color:var(--g500); justify-content:center; text-align:center;
  font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase; padding:var(--sp-xl)}

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
  .card{opacity:1; transform:none; transition:none}
  #roll.rolling .dice{animation:none}
}
"""

ICON_DICE = (
    # 双向箭头「⇄」：换/另起的语义直给，线条极简、任何尺寸都清楚，与站内 ↗ ▸ 同一符号语言
    '<svg class="dice" viewBox="0 0 22 14" shape-rendering="geometricPrecision" aria-hidden="true">'
    '<g class="a1" fill="#fff"><rect x="1" y="3.4" width="15" height="1.5"/>'
    '<path d="M15 1 L21 4.15 L15 7.3 Z"/></g>'
    '<g class="a2" fill="#fff"><rect x="6" y="9.1" width="15" height="1.5"/>'
    '<path d="M7 6.7 L1 9.85 L7 13 Z"/></g>'
    '</svg>')

JS = """
const $=(s)=>document.querySelector(s);
let POOL=[], seen=[], cur=null, recent=[];
const au=new Audio();
const np=$('#np'), NC=$('#np-cover'), NT=$('#np-title'), NA=$('#np-artist'),
      NBAR=$('#np-bar'), NFILL=$('#np-fill'), NTIME=$('#np-time'), NTOG=$('#np-toggle');
const KEY='md_hearts';
const ld=()=>{try{return JSON.parse(localStorage.getItem(KEY)||'[]')}catch(e){return []}};
const sv=(a)=>{try{localStorage.setItem(KEY,JSON.stringify(a))}catch(e){}};
let hearts=ld();
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
  const meta=[t.year,t.album,t.bpm_band?('bpm '+t.bpm_band):''].filter(Boolean).join(' / ');
  const on=hearts.indexOf(t.title+' - '+t.artist)>=0?' on':'';
  const links=(t.a?'<a class="btn solid" href="'+t.a+'" target="_blank" rel="noopener">listen \\u2197</a>':'')
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
  requestAnimationFrame(()=>card.classList.add('in'));
  const pb2=$('#cpb'); if(pb2)pb2.addEventListener('click',()=>toggle(t));
  const hz=$('#chz'); if(hz)hz.addEventListener('click',()=>{
    const k=hz.dataset.k,i=hearts.indexOf(k);
    if(i>=0)hearts.splice(i,1);else hearts.push(k);
    sv(hearts);hz.classList.toggle('on',hearts.indexOf(k)>=0);});
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

$('#roll').addEventListener('click',roll);
document.addEventListener('keydown',(e)=>{
  const tag=(e.target.tagName||'').toLowerCase();
  if(tag==='input'||tag==='textarea'||tag==='select')return;
  if(e.code==='Space'){e.preventDefault();roll();}
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
    <button id="roll" type="button">{ICON_DICE}另起一首<span class="k">space</span></button>
  </div>
  <div class="hint">按 <kbd>space</kbd> 另起一首 · <kbd>p</kbd> 播放/暂停 · 每首自动播 30 秒试听 · ♥ 收藏与日报页共用</div>

  <div class="sect">the pick</div>
  <article class="card" id="card"><div class="c-main">rolling…</div></article>

  <div class="sect">刚听过 · recent</div>
  <div class="recent" id="recent"></div>

  <footer>
    <span>music daily · shuffle</span>
    <span><a href="index.html" style="border-bottom:1px solid var(--g300)">今日精选 →</a></span>
    <span>cover &amp; preview via public music api · personal use</span>
  </footer>
</main>

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
