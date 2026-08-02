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

LIGHTBOX_CSS = """
/* ── 封面放大 + 艺人详情 ── */
#lb{position:fixed; inset:0; z-index:2000; display:none; padding:clamp(14px,4vw,40px);
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
#lb h3{font-size:clamp(26px,3.4vw,36px); font-weight:100; line-height:1.24;
  letter-spacing:-.015em; margin-top:11px; text-transform:lowercase;
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
#lb .pool a{font-family:var(--mono); font-size:9px; letter-spacing:.04em;
  border:1px solid var(--g200); padding:4px 8px; color:var(--g900); background:var(--white);
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

LIGHTBOX_HTML = """<div id="lb" role="dialog" aria-modal="true" aria-label="专辑详情">
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


def lightbox_js(trigger_sel: str) -> str:
    """trigger_sel：点了会开浮层的元素选择器（日报 '.art'，随机页 '.big-art'）。"""
    return """
(function(){
  var lb=document.getElementById('lb'); if(!lb) return;
  var $=function(i){return document.getElementById(i)};
  var last=null;

  // iTunes 缩略图按既定命名规则换更大尺寸；非 iTunes 的 URL 原样返回
  function big(u){ return u ? u.replace(/\\/(\\d+)x(\\d+)(bb)?\\.(jpg|png)/i, '/600x600bb.$4') : ''; }

  function esc(s){ var d=document.createElement('div'); d.textContent=s==null?'':s; return d.innerHTML; }

  function open(d){
    last=document.activeElement;
    $('lb-big').innerHTML = d.cover
      ? '<img src="'+esc(big(d.cover))+'" alt="">'
      : '<div class="ph">'+esc((d.artist||'?').slice(0,1).toUpperCase())+'</div>';
    if(d.year || d.album){
      $('lb-big').insertAdjacentHTML('beforeend',
        '<div class="yr"><span>'+esc(d.album||'')+'</span><span>'+esc(d.year||'')+'</span></div>');
    }
    // 主体是音乐人：大标题放艺人名，副行放年代跨度与流派
    $('lb-artist').textContent = d.artist||'';
    var sub=[]; if(d.years) sub.push(d.years); else if(d.year) sub.push(d.year);
    if(d.g0) sub.push(d.g0);
    $('lb-sub').textContent = sub.join(' · ');
    $('lb-tags').innerHTML = (d.tags||'').split('|').filter(Boolean)
      .map(function(t){return '<span>'+esc(t)+'</span>'}).join('');
    // 本站收录该艺人的其它曲目（当前这首标 cur）
    var inp=(d.inpool||'').split('|').filter(Boolean);
    $('lb-inpool').innerHTML = inp.map(function(x){
      var cur = x===d.title ? ' class="cur"' : '';
      return '<a href="?t='+encodeURIComponent(x)+'"'+cur+'>'+esc(x)+'</a>';
    }).join('');
    $('lb-inpool-w').style.display = inp.length>1 ? '' : 'none';
    // 这一首（次要块）
    $('lb-trkname').textContent = [d.title, d.album, d.year, d.bpm].filter(Boolean).join(' · ');
    [['bio','lb-bio'],['one','lb-one'],['why','lb-why'],['scene','lb-scene']].forEach(function(p){
      var v=d[p[0]]||'';
      $(p[1]).textContent=v;
      var w=$(p[1]+'-w'); if(w) w.style.display = v ? '' : 'none';   // 该段没内容就整块收起
    });
    $('lb-trk-w').style.display = (d.why||d.scene) ? '' : 'none';
    var lk=[];
    if(d.apple)   lk.push('<a href="'+esc(d.apple)+'" target="_blank" rel="noopener">apple music ↗</a>');
    if(d.spotify) lk.push('<a href="'+esc(d.spotify)+'" target="_blank" rel="noopener">spotify ↗</a>');
    if(d.netease) lk.push('<a href="'+esc(d.netease)+'" target="_blank" rel="noopener">netease ↗</a>');
    $('lb-links').innerHTML = lk.join('');
    lb.classList.add('on');
    document.body.style.overflow='hidden';
    lb.querySelector('.x').focus();
  }
  function close(){
    lb.classList.remove('on');
    document.body.style.overflow='';
    if(last && last.focus) last.focus();
  }

  document.addEventListener('click', function(e){
    if(e.target.closest('[data-close]')){ close(); return; }
    // 点播放键不开浮层
    if(e.target.closest('.pbtn')) return;
    var h=e.target.closest('SEL'); if(!h) return;
    var d=h.dataset; if(!d.title && !d.cover) return;
    e.preventDefault(); open(d);
  });
  addEventListener('keydown', function(e){
    if(e.key==='Escape' && lb.classList.contains('on')) close();
  });
})();
""".replace("SEL", trigger_sel)
