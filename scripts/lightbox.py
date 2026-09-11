"""封面点开大图 + 艺人详情浮层（日报与随机页共用一份）。

为什么抽出来：两页封面结构不同（日报 `.art`、随机页 `.big-art`），但浮层本身
应当完全一致。两边各写一份必然漂移——这个项目已经在 TAG_MAP、pbtn 规则上
各栽过一次，所以这里一开始就做成单一来源。

用法：
    from lightbox import LIGHTBOX_CSS, LIGHTBOX_HTML, lightbox_js
    ... CSS + LIGHTBOX_CSS ... {LIGHTBOX_HTML} ... <script>{lightbox_js(sel)}</script>

数据从触发元素的 data-* 读，不额外请求：封面大图直接把 iTunes 的 100x100
缩略图 URL 换成 600x600（同一 CDN 的既定命名规则）。
"""
from __future__ import annotations

import json

LIGHTBOX_CSS = """
/* ── 封面放大 + 艺人详情 ── */
/* 四边都要加安全区：实测 iPhone 14 Pro standalone 下，.sheet 距顶 52px
   而刘海是 59px —— 贴在 .sheet 右上角的关闭键整个埋在刘海底下，【浮层关不掉】。
   这比顶栏被埋严重得多（顶栏只是看不见，浮层是操作不了）。
   变量在 render_grid 的 :root 里定义，本文件的样式注入同一个文档，直接继承。 */
#lb{position:fixed; inset:0; z-index:2000; display:none;
  padding:calc(clamp(12px,3vw,28px) + var(--sat, 0px))
          calc(clamp(12px,3vw,28px) + var(--sar, 0px))
          calc(clamp(12px,3vw,28px) + var(--sab, 0px))
          calc(clamp(12px,3vw,28px) + var(--sal, 0px));
  align-items:center; justify-content:center; overscroll-behavior:contain}
#lb.on{display:flex}
#lb .veil{position:absolute; inset:0; background:rgba(10,9,12,.86);
  backdrop-filter:blur(7px); -webkit-backdrop-filter:blur(7px);
  animation:lb-veil .26s ease-out both}
@keyframes lb-veil{from{opacity:0}to{opacity:1}}
#lb .sheet{position:relative; z-index:1; width:min(820px,100%);
  max-height:calc(100svh - 2 * clamp(12px,3vw,28px) - var(--sat, 0px) - var(--sab, 0px));
  display:grid; grid-template-columns:minmax(0,280px) minmax(0,1fr);
  background:var(--paper); border:1px solid var(--g1000); overflow:hidden;
  animation:lb-in .38s cubic-bezier(.16,1,.3,1) both}
@keyframes lb-in{from{opacity:0; transform:translateY(14px) scale(.965)}
  to{opacity:1; transform:none}}
/* 左：大图。方形，底部压一条铭牌 */
#lb .big{position:relative; background:var(--ink); aspect-ratio:1; overflow:hidden}
#lb .big img{width:100%; height:100%; object-fit:cover; display:block;
  animation:lb-img .5s cubic-bezier(.2,1,.3,1) both}
@keyframes lb-img{from{opacity:0; transform:scale(1.06)}to{opacity:1; transform:none}}
#lb .big .ph{width:100%; height:100%; display:grid; place-items:center;
  font-family:var(--mono); font-size:64px; color:var(--g900); background:var(--g1000)}
#lb .big .yr{position:absolute; left:0; right:0; bottom:0; padding:9px 13px;
  font-family:var(--mono); font-size:var(--fs-10); letter-spacing:.1em;
  text-transform:uppercase; color:var(--white);
  background:linear-gradient(transparent,rgba(0,0,0,.78) 40%);
  display:flex; justify-content:space-between; gap:10px}
/* 右：详情 */
#lb .info{padding:clamp(18px,2.6vw,24px); min-height:0; min-width:0;
  overflow:auto; overscroll-behavior:contain; scrollbar-width:thin;
  display:flex; flex-direction:column}
#lb .kicker{font-family:var(--mono); font-size:var(--fs-10); letter-spacing:.16em;
  text-transform:uppercase; color:var(--g600); display:flex; align-items:center; gap:9px;
  padding-right:28px}
#lb .kicker::after{content:""; flex:1; height:1px; background:var(--g200)}
#lb h3{font-size:clamp(26px,3.4vw,36px); font-weight:100; line-height:1.24;
  letter-spacing:-.015em; margin-top:11px; text-transform:lowercase;
  padding-bottom:.1em; overflow:visible; overflow-wrap:anywhere}
#lb .ar{font-family:var(--mono); font-size:var(--fs-15); text-transform:uppercase;
  letter-spacing:.1em; color:var(--g900); margin-top:5px; overflow-wrap:anywhere}
#lb .meta{font-family:var(--mono); font-size:var(--fs-10); color:var(--g600);
  margin-top:11px; line-height:1.7}
#lb .tags{display:flex; flex-wrap:wrap; gap:5px; margin-top:12px}
#lb .tags span{font-family:var(--mono); font-size:9px; letter-spacing:.06em;
  text-transform:uppercase; border:1px solid var(--g200); padding:3px 7px; color:var(--g900)}
#lb .sec{margin-top:16px}
#lb .sec .lb-t{font-family:var(--mono); font-size:9px; letter-spacing:.14em;
  text-transform:uppercase; color:var(--orange); margin-bottom:5px}
#lb .sec p{font-size:var(--fs-20); font-weight:300; line-height:1.62}
#lb .sec.mono p{font-family:var(--mono); font-size:var(--fs-10); color:var(--g600); line-height:1.75}
/* bio 是主体，字号比别的段大一档 */
#lb #lb-bio{font-size:var(--fs-20); font-weight:300; line-height:1.72}
#lb .sec#lb-bio-w{margin-top:14px}
/* 本站收录的曲目：可点，跳到那一首 */
#lb .pool{display:flex; flex-wrap:wrap; gap:5px}
#lb .pool a{font-family:var(--mono); font-size:10px; letter-spacing:.04em;
  border:1px solid var(--g200); padding:4px 8px; color:var(--g900); background:var(--white);
  display:inline-flex; align-items:center; min-height:32px; overflow-wrap:anywhere;
  transition:background .14s, color .14s}
#lb .pool a:hover{background:var(--ink); color:var(--white); border-color:var(--ink)}
#lb .pool a.cur{background:var(--ink); color:var(--white); border-color:var(--ink)}
/* 「这一首」降级成次要块：加左边线、字号收小 */
#lb .sec.trk{border-left:2px solid var(--g200); padding-left:11px; margin-top:18px}
#lb .sec.trk .tk{font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase;
  letter-spacing:.06em; color:var(--ink); margin-bottom:5px}
#lb .sec.trk p{font-size:var(--fs-15); line-height:1.6; color:var(--g900)}
#lb .sec.trk p.sc{font-family:var(--mono); font-size:9px; color:var(--g600);
  margin-top:6px; line-height:1.7}
#lb .lb-links{display:flex; flex-wrap:wrap; gap:7px; margin-top:auto; padding-top:20px}
#lb .lb-links a{font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase;
  letter-spacing:.06em; border:1px solid var(--g300); padding:8px 13px; color:var(--ink);
  display:inline-flex; align-items:center; min-height:44px;
  transition:background .15s, border-color .15s}
#lb .lb-links a:hover{background:var(--ink); color:var(--white); border-color:var(--ink)}
#lb .x{position:absolute; right:0; top:0; z-index:3; width:44px; height:44px;
  border:none; border-left:1px solid var(--g200); border-bottom:1px solid var(--g200);
  background:var(--paper); color:var(--ink); cursor:pointer; font-family:var(--mono);
  font-size:16px; line-height:1; transition:background .15s}
#lb .x:hover{background:var(--ink); color:var(--white)}
#lb a:focus-visible,#lb button:focus-visible{outline:2px solid var(--orange); outline-offset:-3px}
/* 封面可点：给个手型 + 悬停微亮 + 右下角放大镜提示 */
.cover-zoom{cursor:zoom-in}
.cover-zoom::after{content:"⤢"; position:absolute; right:6px; bottom:6px; z-index:2;
  width:20px; height:20px; display:grid; place-items:center; font-size:11px;
  background:rgba(15,14,18,.72); color:#fff; opacity:0; transition:opacity .18s;
  pointer-events:none}
.cover-zoom:hover::after{opacity:1}
@media(max-width:720px){
  #lb .sheet{grid-template-columns:1fr; grid-template-rows:auto minmax(0,1fr)}
  /* 方形封面完整显示；只有详情滚动，关闭键始终留在右上角。 */
  #lb .big{width:min(220px,32svh,100%); aspect-ratio:1; justify-self:center; margin-top:12px}
  #lb .info{padding:16px}
  #lb h3{font-size:24px}
}
@media(prefers-reduced-motion:reduce){
  #lb .veil,#lb .sheet,#lb .big img{animation:none}
}
"""

LIGHTBOX_HTML = """<div id="lb" role="dialog" aria-modal="true" aria-label="专辑详情" aria-hidden="true" tabindex="-1">
  <div class="veil" data-close></div>
  <div class="sheet">
    <button class="x" type="button" data-close aria-label="关闭">✕</button>
    <div class="big" id="lb-big"></div>
    <div class="info">
      <div class="kicker" id="lb-kick">artist</div>
      <h3 id="lb-artist"></h3>
      <div class="ar" id="lb-sub"></div>
      <div class="tags" id="lb-tags"></div>
      <div class="sec" id="lb-bio-w"><p id="lb-bio"></p></div>
      <div class="sec" id="lb-one-w"><div class="lb-t">在音乐地图上</div><p id="lb-one"></p></div>
      <div class="sec" id="lb-inpool-w"><div class="lb-t">本站收录</div>
        <div class="pool" id="lb-inpool"></div></div>
      <div class="sec trk" id="lb-trk-w"><div class="lb-t">这一首</div>
        <p class="tk" id="lb-trkname"></p>
        <p id="lb-why"></p>
        <p class="sc" id="lb-scene"></p></div>
      <div class="lb-links" id="lb-links"></div>
    </div>
  </div>
</div>"""


def lightbox_js(trigger_sel: str, random_url: str = "random.html") -> str:
    """封面选择器与当前页到随机页的路径；往期日报需传 ../random.html。"""
    return """
(function(){
  var lb=document.getElementById('lb'); if(!lb) return;
  var $=function(i){return document.getElementById(i)};
  var last=null, previousOverflow='', inerted=[];

  // iTunes 缩略图按既定命名规则换更大尺寸；非 iTunes 的 URL 原样返回
  function big(u){ return u ? u.replace(/\\/(\\d+)x(\\d+)(bb)?\\.(jpg|png)/i, '/600x600bb.$4') : ''; }

  function esc(s){
    var d=document.createElement('div'); d.textContent=s==null?'':s;
    return d.innerHTML.replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }
  function webUrl(value){
    try{
      var u=new URL(value);
      return u.protocol==='https:' || u.protocol==='http:' ? u.href : '';
    }catch(_){ return ''; }
  }
  function artistContext(d){
    var sub=[]; if(d.years) sub.push(d.years); else if(d.year) sub.push(d.year);
    if(d.g0) sub.push(d.g0);
    $('lb-sub').textContent = sub.join(' · ');
    $('lb-bio').textContent = d.bio||'';
    $('lb-bio-w').style.display = d.bio ? '' : 'none';
    // 本站收录跳到随机页，并用艺人名区分同名歌曲。
    var inp=(d.inpool||'').split('|').filter(Boolean);
    $('lb-inpool').innerHTML = inp.map(function(x){
      var cur = x===d.title ? ' class="cur"' : '';
      var url=RANDOM_URL+'?t='+encodeURIComponent(x)+'&artist='+encodeURIComponent(d.artist||'');
      return '<a href="'+esc(url)+'"'+cur+'>'+esc(x)+'</a>';
    }).join('');
    $('lb-inpool-w').style.display = inp.length>1 ? '' : 'none';
  }

  function open(d, trigger){
    // 存【触发元素】而不是 document.activeElement —— 鼠标点击时 activeElement
    // 是 body（点 div 不给焦点），于是关闭后焦点掉回 body，键盘用户要从头 Tab。
    // 2026-08-04 实测：修前 Esc 后 activeElement 就是 <body class="anim">。
    if(!lb.classList.contains('on')){
      last = trigger || document.activeElement;
      previousOverflow = document.body.style.overflow;
    }
    var cover=webUrl(d.cover);
    $('lb-big').innerHTML = cover
      ? '<img src="'+esc(big(cover))+'" alt="">'
      : '<div class="ph">'+esc((d.artist||'?').slice(0,1).toUpperCase())+'</div>';
    if(d.year || d.album){
      $('lb-big').insertAdjacentHTML('beforeend',
        '<div class="yr"><span>'+esc(d.album||'')+'</span><span>'+esc(d.year||'')+'</span></div>');
    }
    // 主体是音乐人：大标题放艺人名，副行放年代跨度与流派
    $('lb-artist').textContent = d.artist||'';
    artistContext(d);
    $('lb-tags').innerHTML = (d.tags||'').split('|').filter(Boolean)
      .map(function(t){return '<span>'+esc(t)+'</span>'}).join('');
    // 这一首（次要块）
    $('lb-trkname').textContent = [d.title, d.album, d.year, d.bpm].filter(Boolean).join(' · ');
    [['one','lb-one'],['why','lb-why'],['scene','lb-scene']].forEach(function(p){
      var v=d[p[0]]||'';
      $(p[1]).textContent=v;
      var w=$(p[1]+'-w'); if(w) w.style.display = v ? '' : 'none';   // 该段没内容就整块收起
    });
    $('lb-trk-w').style.display = (d.why||d.scene) ? '' : 'none';
    var lk=[];
    ['apple','spotify','netease'].forEach(function(name){
      var url=webUrl(d[name]);
      if(url) lk.push('<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">'+
        (name==='apple' ? 'apple music' : name)+' ↗</a>');
    });
    $('lb-links').innerHTML = lk.join('');
    lb.classList.add('on');
    lb.setAttribute('aria-hidden','false');
    document.body.style.overflow='hidden';
    // inert 隔离背后页面；Tab 时另按当前可见控件循环，避免焦点进入浏览器栏，
    // 同时兼容未实现 inert 的浏览器。
    inertKids(true);
    lb.querySelector('.info').scrollTop=0;
    lb.querySelector('.x').focus({preventScroll:true});
  }
  // 除 #lb 外的 body 子节点整体 inert / 恢复。只动我们设过的那些，
  // 免得把页面本来就有的 inert 属性给清掉。
  function inertKids(on){
    if(!on){
      inerted.forEach(function(el){el.removeAttribute('inert')});
      inerted=[];
      return;
    }
    var kids = document.body.children;
    for(var i=0;i<kids.length;i++){
      var el = kids[i];
      if(el === lb) continue;
      if(!el.hasAttribute('inert')){ el.setAttribute('inert',''); inerted.push(el); }
    }
  }
  function close(){
    if(!lb.classList.contains('on')) return;
    lb.classList.remove('on');
    document.body.style.overflow=previousOverflow;
    inertKids(false);
    // 焦点归位要在解除 inert 【之后】—— 在 inert 状态下 focus() 是无效的，
    // 焦点会掉回 body，用户按 Tab 得从头再来。
    if(last && last.isConnected && last.focus) last.focus({preventScroll:true});
    lb.setAttribute('aria-hidden','true');
    last=null;
  }

  document.addEventListener('click', function(e){
    if(lb.contains(e.target) && e.target.closest('[data-close]')){ close(); return; }
    if(lb.classList.contains('on')) return;
    // 点播放键不开浮层
    if(e.target.closest('.pbtn')) return;
    var h=e.target.closest('SEL'); if(!h) return;
    var d=h.dataset; if(!d.title && !d.cover) return;
    e.preventDefault(); open(d, h);
  });
  document.addEventListener('musicdaily:artist-context', function(e){
    if(lb.classList.contains('on') && last===e.target) artistContext(last.dataset);
  });
  document.addEventListener('keydown', function(e){
    if(lb.classList.contains('on')){
      // 不让页面播放器的全局快捷键响应浮层里的操作。
      e.stopPropagation();
      if(e.key==='Escape'){ e.preventDefault(); close(); return; }
      if(e.key==='Tab'){
        var focusable=Array.from(lb.querySelectorAll('a[href],button:not([disabled]),[tabindex]:not([tabindex="-1"])'))
          .filter(function(el){return el.getClientRects().length>0});
        var first=focusable[0]||lb, end=focusable[focusable.length-1]||lb;
        var active=document.activeElement;
        if(!lb.contains(active) || active===lb || (e.shiftKey ? active===first : active===end)){
          e.preventDefault(); (e.shiftKey ? end : first).focus();
        }
      }
      return;
    }
    // 封面卡片声明了 role="button" + tabindex="0"，那就必须响应 Enter / Space ——
    // 原生 <button> 自带这个行为，用 div 扮演按钮就得自己补齐。
    // 之前只绑了 click：键盘用户能聚焦到封面（还能看到焦点环），按下去毫无反应，
    // 于是那个焦点环和浮层里的焦点 trap 对他们全是白做的。
    if(e.key !== 'Enter' && e.key !== ' ' && e.key !== 'Spacebar') return;
    if(e.defaultPrevented || e.repeat || e.altKey || e.ctrlKey || e.metaKey) return;
    var h = e.target.closest && e.target.closest('SEL');
    if(!h) return;
    // 原生按钮由浏览器触发 click；旧封面内的播放键也保留自身操作。
    if(e.target.closest('button,a,input,textarea,select,[contenteditable="true"],.pbtn')) return;
    var d = h.dataset; if(!d.title && !d.cover) return;
    e.preventDefault();                           // Space 默认会滚动页面
    e.stopPropagation();
    open(d, h);
  }, true);
})();
""".replace("SEL", trigger_sel).replace("RANDOM_URL", json.dumps(random_url))
