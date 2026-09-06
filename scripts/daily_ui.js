// Progressive enhancement: music and navigation remain visible without JavaScript.
(() => {
  const $ = id => document.getElementById(id);
  const cards = [...document.querySelectorAll('article.mod')];
  const query = $('track-search'), genre = $('track-genre'), only = $('fav-only');
  let hearts = [];
  try { hearts = [...new Set(MD.readList(localStorage, 'md_hearts'))]; } catch (_) {}
  let favoritesOnly = false;
  const normalize = value => String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().trim();
  function applyFilter() {
    const terms = normalize(query?.value || '').split(/\s+/).filter(Boolean);
    let hits = 0, favorites = 0;
    cards.forEach(card => {
      const saved = hearts.includes(card.dataset.k);
      favorites += Number(saved);
      const haystack = normalize(card.dataset.search);
      const shown = terms.every(term => haystack.includes(term)) &&
        (!genre?.value || card.dataset.genre === genre.value) && (!favoritesOnly || saved);
      card.hidden = !shown;
      if (shown) hits++;
      const heart = card.querySelector('.heart');
      heart.classList.toggle('on', saved); heart.setAttribute('aria-pressed', String(saved));
      heart.setAttribute('aria-label', (saved ? '取消收藏：' : '收藏：') + card.dataset.k);
    });
    if ($('fav-n')) $('fav-n').textContent = favorites;
    if ($('filter-count')) $('filter-count').textContent = `显示 ${hits} / ${cards.length} 首`;
    if ($('no-tracks')) $('no-tracks').hidden = hits > 0;
    only?.setAttribute('aria-pressed', String(favoritesOnly)); only?.classList.toggle('active', favoritesOnly);
    if ($('fav-lb')) $('fav-lb').textContent = favoritesOnly ? '♥ 已收藏' : '♡ 只看收藏';
    if ($('fav-export')) $('fav-export').textContent = `导出收藏${hearts.length ? ' · ' + hearts.length : ''}`;
  }
  function updateExport() {
    if ($('fav-text')) $('fav-text').textContent = hearts.length
      ? `我收藏的 · MUSIC DAILY（共 ${hearts.length} 首）\n${hearts.join('\n')}` : '还没有收藏。点歌曲右上角的爱心，喜欢的歌会留在这里。';
    if ($('fav-copy')) $('fav-copy').disabled = !hearts.length;
  }
  cards.forEach(card => card.querySelector('.heart').addEventListener('click', () => {
    const key = card.dataset.k;
    hearts = hearts.includes(key) ? hearts.filter(x => x !== key) : [...hearts, key];
    try { localStorage.setItem('md_hearts', JSON.stringify(hearts)); }
    catch (_) { MD.notify('浏览器暂时无法保存，收藏只保留到本页关闭'); }
    applyFilter(); updateExport();
  }));
  query?.addEventListener('input', applyFilter); genre?.addEventListener('change', applyFilter);
  only?.addEventListener('click', () => { favoritesOnly = !favoritesOnly; applyFilter(); });
  function resetFilters(){if(query)query.value='';if(genre)genre.value='';favoritesOnly=false;applyFilter();}
  $('filter-reset')?.addEventListener('click', resetFilters);
  $('empty-reset')?.addEventListener('click', () => {resetFilters();query?.focus();});
  $('fav-export')?.addEventListener('click', () => {
    updateExport(); $('fav-box').hidden = false; $('fav-box').scrollIntoView({block:'start',behavior:'smooth'});
  });
  $('fav-close')?.addEventListener('click', () => {$('fav-box').hidden=true;$('fav-export').focus();});
  $('nc-btn')?.addEventListener('click', () => MD.copyText($('nc-text').textContent,$('nc-btn'),$('nc-text')));
  $('fav-copy')?.addEventListener('click', () => MD.copyText($('fav-text').textContent,$('fav-copy'),$('fav-text')));
  $('copy-issue')?.addEventListener('click', () => MD.copyText($('nc-text').textContent,$('copy-issue')));
  window.addEventListener('storage', event => {
    if (event.key === 'md_hearts' || event.key === null) {
      try {hearts=[...new Set(MD.readList(localStorage,'md_hearts'))];}catch(_){hearts=[];}
      applyFilter(); updateExport();
    }
  });
  $('share-btn')?.addEventListener('click', async () => {
    const url = location.href.split('#')[0];
    if(navigator.share) {
      try {await navigator.share({title:document.title,url});return;}
      catch(error){if(error.name==='AbortError')return;}
    }
    MD.copyText(url,$('share-btn'));
  });
  const target = new URLSearchParams(location.search).get('t');
  if (target) {
    const card = cards.find(x => x.dataset.id === target);
    if (card) {card.classList.add('selected-track');card.scrollIntoView({block:'center'});}
  }
  applyFilter(); updateExport();

  // A single Audio owns every preview. A generation token isolates late rejections.
  // https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/play
  const audio = new Audio(); audio.preload = 'none';
  const player=$('np'), toggle=$('np-toggle'), seek=$('np-bar');
  const buttons=[...document.querySelectorAll('.pbtn')];
  let current=null, generation=0, failed=new Set();
  function playing(on){
    buttons.forEach(button=>{const active=on&&button===current;button.classList.toggle('playing',active);button.setAttribute('aria-pressed',String(active));});
    player.classList.toggle('playing',on);toggle.setAttribute('aria-label',on?'暂停试听':'播放试听');
  }
  function fail(error, token){
    if(token!==generation||error?.name==='AbortError')return;
    playing(false);
    if(error?.name==='NotAllowedError'){MD.notify('点一下播放键即可开始试听');return;}
    if(current){failed.add(current);current.classList.add('dead');current.title='试听暂不可用，点击可重试';}
    MD.notify('这首暂时无法试听，可以打开音乐平台收听');
    $('np-artist').textContent='试听暂不可用 · 点击播放键重试';
  }
  function resume(){
    const token=generation;
    if(audio.error){audio.load();if(current)failed.delete(current);}
    try {const promise=audio.play();if(promise?.catch)promise.catch(error=>fail(error,token));}
    catch(error){fail(error,token);}
  }
  function load(button){
    if(!button)return;
    ++generation;audio.pause();audio.removeAttribute('src');audio.load();playing(false);current=button;
    $('np-fill').style.width='0%';$('np-time').textContent='0:00';
    if(!button.dataset.src){player.classList.remove('on');current=null;MD.notify('这首暂无试听，请打开音乐平台');return;}
    audio.src=button.dataset.src;
    const cover=$('np-cover');cover.hidden=!button.dataset.cover;if(button.dataset.cover)cover.src=button.dataset.cover;
    $('np-title').textContent=button.dataset.title;$('np-artist').textContent=button.dataset.artist;
    player.classList.add('on');resume();
  }
  function step(direction){
    const visible=buttons.filter(button=>!button.closest('article').hidden&&!failed.has(button));
    if(!visible.length){MD.notify('当前筛选没有可试听曲目');return;}
    const index=visible.indexOf(current);
    load(visible[index<0?0:(index+direction+visible.length)%visible.length]);
  }
  function togglePlayback(){if(!current){step(1);return;}audio.paused?resume():audio.pause();}
  buttons.forEach(button=>button.addEventListener('click',()=>{
    if(button===current&&!failed.has(button))togglePlayback();else{failed.delete(button);load(button);}
  }));
  toggle.addEventListener('click',togglePlayback);
  $('play-issue')?.addEventListener('click',()=>{
    const first=buttons.find(button=>!button.closest('article').hidden);
    if(first){failed.delete(first);load(first);}else MD.notify('当前筛选没有可试听曲目');
  });
  $('np-prev').addEventListener('click',()=>step(-1));$('np-next').addEventListener('click',()=>step(1));
  $('np-close').addEventListener('click',()=>{++generation;audio.pause();audio.removeAttribute('src');audio.load();playing(false);player.classList.remove('on');current?.focus();current=null;});
  audio.addEventListener('playing',()=>{failed.delete(current);current?.classList.remove('dead');if(current)$('np-artist').textContent=current.dataset.artist;playing(true);});
  audio.addEventListener('pause',()=>playing(false));
  audio.addEventListener('error',()=>{if(audio.error)fail(audio.error,generation);});
  audio.addEventListener('ended',()=>{playing(false);step(1);});
  const fmt=seconds=>`${Math.floor(seconds/60)}:${String(Math.floor(seconds%60)).padStart(2,'0')}`;
  audio.addEventListener('timeupdate',()=>{
    if(!Number.isFinite(audio.duration)||audio.duration<=0)return;
    const duration=Math.min(30,audio.duration);
    if(audio.currentTime>=30){audio.pause();step(1);return;}
    const percent=Math.min(100,audio.currentTime/duration*100);
    $('np-fill').style.width=percent+'%';$('np-time').textContent=fmt(audio.currentTime)+' / '+fmt(duration);
    seek.setAttribute('aria-valuenow',String(Math.round(percent)));seek.setAttribute('aria-valuetext',fmt(audio.currentTime));
  });
  seek.addEventListener('click',event=>{
    if(!Number.isFinite(audio.duration))return;const rect=seek.getBoundingClientRect();
    audio.currentTime=Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width))*Math.min(30,audio.duration);
  });
  seek.addEventListener('keydown',event=>{
    if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)||!Number.isFinite(audio.duration))return;
    event.preventDefault();event.stopPropagation();
    const duration=Math.min(30,audio.duration);
    audio.currentTime=event.key==='Home'?0:event.key==='End'?duration:Math.max(0,Math.min(duration,audio.currentTime+(event.key==='ArrowRight'?5:-5)));
  });
  document.addEventListener('keydown',event=>{
    if(event.defaultPrevented||event.ctrlKey||event.metaKey||event.altKey||event.repeat)return;
    if(event.target.closest('input,textarea,select,button,a,[contenteditable=true],[role=button],[role=slider]'))return;
    if($('lb')?.classList.contains('on')||document.querySelector('.manual-copy'))return;
    if(event.code==='Space'){event.preventDefault();togglePlayback();}
  });
})();
