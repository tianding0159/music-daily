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
  padding:calc(clamp(14px,4vw,40px) + var(--sat, 0px))
          calc(clamp(14px,4vw,40px) + var(--sar, 0px))
          calc(clamp(14px,4vw,40px) + var(--sab, 0px))
          calc(clamp(14px,4vw,40px) + var(--sal, 0px));
  align-items:center; justify-content:center}
#lb.on{display:flex}
#lb .veil{position:absolute; inset:0; background:rgba(10,9,12,.86);
  backdrop-filter:blur(7px); -webkit-backdrop-filter:blur(7px);
  animation:lb-veil .26s ease-out both}
@keyframes lb-veil{from{opacity:0}to{opacity:1}}
#lb .sheet{position:relative; z-index:1; width:min(880px,100%); max-height:92svh;
  display:grid; grid-template-columns:minmax(0,300px) minmax(0,1fr);
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
#lb .info{padding:clamp(18px,2.6vw,28px); overflow:auto; display:flex; flex-direction:column}
#lb .kicker{font-family:var(--mono); font-size:var(--fs-10); letter-spacing:.16em;
  text-transform:uppercase; color:var(--g600); display:flex; align-items:center; gap:9px}
#lb .kicker::after{content:""; flex:1; height:1px; background:var(--g200)}
#lb h3{font-size:clamp(26px,3.4vw,36px); font-weight:400; line-height:1.24;
  letter-spacing:-.025em; margin-top:11px;
  padding-bottom:.1em; overflow:visible}
#lb .ar{font-family:var(--mono); font-size:var(--fs-15); text-transform:uppercase;
  letter-spacing:.1em; color:var(--g900); margin-top:5px}
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
#lb .pool a{font-family:var(--sans); font-size:12px; letter-spacing:.01em;
  border:1px solid var(--g200); padding:10px 12px; color:var(--g900); background:var(--white);
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
  transition:background .15s, border-color .15s}
#lb .lb-links a:hover{background:var(--ink); color:var(--white); border-color:var(--ink)}
#lb .x{position:absolute; right:0; top:0; z-index:3; width:42px; height:42px;
  border:none; border-left:1px solid var(--g200); border-bottom:1px solid var(--g200);
  background:var(--paper); color:var(--ink); cursor:pointer; font-family:var(--mono);
  font-size:16px; line-height:1; transition:background .15s}
#lb .x:hover{background:var(--ink); color:var(--white)}
/* 封面可点：给个手型 + 悬停微亮 + 右下角放大镜提示 */
.cover-zoom{cursor:zoom-in}
.cover-zoom::after{content:"⤢"; position:absolute; right:6px; bottom:6px; z-index:2;
  width:20px; height:20px; display:grid; place-items:center; font-size:11px;
  background:rgba(15,14,18,.72); color:#fff; opacity:0; transition:opacity .18s;
  pointer-events:none}
.cover-zoom:hover::after{opacity:1}
@media(max-width:720px){
  #lb .sheet{grid-template-columns:1fr; max-height:88svh; overflow:auto}
  #lb .big{aspect-ratio:16/11}
  #lb .info{padding:16px}
  #lb h3{font-size:24px}
}
@media(prefers-reduced-motion:reduce){
  #lb .veil,#lb .sheet,#lb .big img{animation:none}
}
"""

LIGHTBOX_HTML = """<div id="lb" role="dialog" aria-modal="true" aria-labelledby="lb-artist" aria-hidden="true">
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


def lightbox_js(trigger_sel: str, base_prefix: str = '') -> str:
    """Render accessible details; sibling links always use canonical track IDs."""
    return r"""
(function(){
  const lb=document.getElementById('lb');if(!lb)return;
  const $=id=>document.getElementById(id), triggerSelector=__TRIGGER__, randomPage=__RANDOM_PAGE__;
  let last=null, activeData=null, previousOverflow='';
  function safeURL(value){try{const u=new URL(value);return /^https?:$/.test(u.protocol)?u.href:''}catch{return ''}}
  function node(tag,text,className){const n=document.createElement(tag);if(text!=null)n.textContent=String(text);if(className)n.className=className;return n;}
  function entries(raw){
    try{const parsed=JSON.parse(raw||'[]');return Array.isArray(parsed)?parsed.filter(x=>x&&typeof x.id==='string'&&x.id&&typeof x.title==='string'&&x.title):[];}catch{return [];}
  }
  function renderContext(d){
    $('lb-artist').textContent=d.artist||'';
    $('lb-sub').textContent=[d.years||d.year,d.g0].filter(Boolean).join(' · ');
    $('lb-tags').replaceChildren(...(d.tags||'').split('|').filter(Boolean).map(t=>node('span',t)));
    const songs=entries(d.inpool);
    $('lb-inpool').replaceChildren(...songs.map(song=>{
      const link=node('a',song.title);link.href=randomPage+'?t='+encodeURIComponent(song.id);
      if(song.id===d.id){link.className='cur';link.setAttribute('aria-current','true');}
      return link;
    }));
    $('lb-inpool-w').hidden=songs.length<2;
    [['bio','lb-bio'],['one','lb-one'],['why','lb-why'],['scene','lb-scene']].forEach(([key,id])=>{
      $(id).textContent=d[key]||'';const wrapper=$(id+'-w');if(wrapper)wrapper.hidden=!d[key];
    });
    $('lb-trkname').textContent=[d.title,d.album,d.year,d.bpm].filter(Boolean).join(' · ');
    $('lb-trk-w').hidden=!(d.title||d.why||d.scene);
  }
  function open(d,trigger){
    if(!lb.classList.contains('on')){last=trigger||document.activeElement;previousOverflow=document.body.style.overflow;}
    activeData={...d};$('lb-big').replaceChildren();
    const cover=safeURL(d.cover), placeholder=()=>node('div',(d.artist||'?').slice(0,1).toUpperCase(),'ph');
    if(cover){
      const img=node('img');img.src=cover.replace(/\/(\d+)x(\d+)(bb)?\.(jpg|png)/i,'/600x600bb.$4');img.alt=(d.album||d.title||'')+' 专辑封面';
      img.addEventListener('error',()=>img.replaceWith(placeholder()),{once:true});$('lb-big').appendChild(img);
    }else $('lb-big').appendChild(placeholder());
    if(d.album||d.year){const meta=node('div',null,'yr');meta.append(node('span',d.album||''),node('span',d.year||''));$('lb-big').appendChild(meta);}
    renderContext(d);$('lb-links').replaceChildren();
    [['apple','Apple Music ↗'],['spotify','Spotify ↗'],['netease','网易云 ↗']].forEach(([key,label])=>{
      const url=safeURL(d[key]);if(!url)return;
      const link=node('a',label);link.href=url;link.target='_blank';link.rel='noopener noreferrer';
      if(key==='netease')link.dataset.nc=[d.title,d.artist].filter(Boolean).join(' ');
      $('lb-links').appendChild(link);
    });
    lb.classList.add('on');lb.setAttribute('aria-hidden','false');document.body.style.overflow='hidden';inertKids(true);lb.querySelector('.x').focus();
  }
  function inertKids(on){
    for(const el of document.body.children){
      if(el===lb)continue;
      if(on&&!el.hasAttribute('inert')){el.setAttribute('inert','');el._lbInert=true;}
      else if(!on&&el._lbInert){el.removeAttribute('inert');el._lbInert=false;}
    }
  }
  function close(){
    if(!lb.classList.contains('on'))return;
    lb.classList.remove('on');lb.setAttribute('aria-hidden','true');document.body.style.overflow=previousOverflow;inertKids(false);activeData=null;
    if(last?.isConnected)last.focus();
  }
  lb.addEventListener('refresh',event=>{
    if(!activeData||event.detail.id!==activeData.id)return;
    activeData={...activeData,...event.detail};renderContext(activeData);
  });
  document.addEventListener('click',event=>{
    const target=event.target.closest?event.target:null;if(!target)return;
    if(target.closest('#lb [data-close]')){close();return;}
    if(target.closest('.pbtn'))return;
    const trigger=target.closest(triggerSelector);if(!trigger)return;
    if(!trigger.dataset.title&&!trigger.dataset.cover)return;event.preventDefault();open(trigger.dataset,trigger);
  });
  document.addEventListener('keydown',event=>{
    if(lb.classList.contains('on')){
      if(event.key==='Escape'){event.preventDefault();close();return;}
      // Also constrain Tab on older browsers without inert support.
      if(event.key==='Tab'){
        const focusables=[...lb.querySelectorAll('button,a[href],[tabindex="0"]')].filter(el=>!el.hidden&&el.getClientRects().length);
        const first=focusables[0],last=focusables[focusables.length-1];
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
        else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
      }
      return;
    }
    if(event.defaultPrevented||event.repeat||!['Enter',' ','Spacebar'].includes(event.key)||event.target.closest?.('.pbtn'))return;
    const trigger=event.target.closest?.(triggerSelector);if(!trigger||trigger.tagName==='BUTTON')return;
    if(!trigger.dataset.title&&!trigger.dataset.cover)return;event.preventDefault();open(trigger.dataset,trigger);
  });
})();
""".replace('__TRIGGER__', json.dumps(trigger_sel)).replace('__RANDOM_PAGE__', json.dumps(base_prefix + 'random.html'))
