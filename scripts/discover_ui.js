// Metadata and editorial acceptance remain separate; this page only presents discoveries.
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const tracks = JSON.parse($('discovery-data').textContent);
  const PAGE_SIZE = 36;
  const PREVIEW_SECONDS = 30;
  const normalize = value => String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().trim();
  const savedKey = track => `${track.title} - ${track.artist}`;
  const haystacks = new Map(tracks.map(t => [t.id, normalize(`${t.title} ${t.artist} ${t.album}`)]));
  const ids = new Map(tracks.map(t => [t.id, t]));
  let hearts = [], onlyFavorites = false, page = 0, filtered = [], buttons = new Map();
  try { hearts = [...new Set(MD.readList(localStorage, 'md_hearts'))]; } catch (_) {}
  const player = $('np'), audio = new Audio(); audio.preload = 'none';
  let current = null, generation = 0, lastPlayTrigger = null;
  const genreNames = {'Alternative':'另类','Electronic':'电子','Jazz':'爵士','Pop':'流行','R&B/Soul':'R&B / 灵魂乐','Rock':'摇滚','Singer/Songwriter':'创作歌手','Folk':'民谣','Indie Rock':'独立摇滚','Ambient':'氛围','Classical':'古典','Worldwide':'世界音乐','Brazilian':'巴西音乐','MPB':'巴西流行','J-Pop':'日本流行','K-Pop':'韩国流行','French Pop':'法语流行','Instrumental':'器乐'};
  function el(tag, className, text) { const node = document.createElement(tag); if (className) node.className = className; if (text !== undefined) node.textContent = text; return node; }
  function iconButton(className, icon, label) { const button = el('button', className); button.type = 'button'; button.innerHTML = icon; button.setAttribute('aria-label', label); return button; }
  function option(select, value, label) { const node = el('option', '', label); node.value = value; select.append(node); }
  [...new Set(tracks.map(t => t.genre).filter(Boolean))].sort().forEach(g => option($('discover-genre'), g, genreNames[g] || g));
  [...new Set(tracks.map(t => t.year.slice(0, 3) + '0').filter(d => /^\d{4}$/.test(d)))].sort().forEach(d => option($('discover-decade'), d, `${d} 年代`));
  ['discover-search', 'discover-genre', 'discover-decade', 'discover-reset', 'discover-favorites', 'discover-export'].forEach(id => { $(id).disabled = false; });
  $('discover-start').disabled = !tracks.some(t => t.preview);

  function syncPlayback() {
    const on = current && !audio.paused && !audio.ended;
    for (const [id, button] of buttons) {
      const active = Boolean(on && current.id === id);
      button.classList.toggle('playing', active); button.setAttribute('aria-pressed', String(active));
      button.setAttribute('aria-label', `${active ? '暂停试听' : '试听'}：${ids.get(id).title}`);
      button.querySelector('span').textContent = active ? '暂停试听' : (ids.get(id).preview ? '试听片段' : '暂无试听');
      button.closest('article').classList.toggle('is-playing', active);
    }
    player.classList.toggle('playing', Boolean(on));
    $('np-toggle').setAttribute('aria-label', on ? '暂停试听' : '播放试听');
  }
  function fail(error, token) {
    if (token !== generation || error?.name === 'AbortError') return;
    syncPlayback();
    MD.notify(error?.name === 'NotAllowedError' ? '点一下播放键即可开始试听' : '这个片段暂时无法播放，可以打开音乐平台收听');
    $('np-artist').textContent = '试听暂不可用 · 点击播放键重试';
  }
  function resume() {
    const token = generation;
    try {
      if (audio.error) audio.load();
      if (audio.currentTime >= previewDuration() - 0.05) audio.currentTime = 0;
      audio.play()?.catch(error => fail(error, token));
    } catch (error) { fail(error, token); }
  }
  function load(track, trigger) {
    if (!track?.preview) { MD.notify('这首暂无试听，可以打开音乐平台'); return; }
    ++generation; audio.pause(); current = track; lastPlayTrigger = trigger || null;
    audio.src = track.preview; $('np-title').textContent = track.title; $('np-artist').textContent = track.artist;
    $('np-cover').hidden = !track.cover; if (track.cover) $('np-cover').src = track.cover;
    $('np-fill').style.width = '0%'; $('np-time').textContent = '0:00';
    $('np-bar').setAttribute('aria-valuenow', '0'); player.classList.add('on'); syncPlayback(); resume();
  }
  function toggle(track, trigger) {
    if (current?.id !== track.id) { load(track, trigger); return; }
    lastPlayTrigger = trigger || lastPlayTrigger;
    audio.paused ? resume() : audio.pause();
  }
  function step(direction) {
    const available = filtered.filter(t => t.preview);
    if (!available.length) { MD.notify('当前筛选没有可试听曲目'); return; }
    const index = available.findIndex(t => t.id === current?.id);
    load(available[index < 0 ? 0 : (index + direction + available.length) % available.length]);
  }
  function exportText() { return hearts.join('\n'); }
  function syncExport() {
    $('discover-export').textContent = `导出收藏${hearts.length ? ` · ${hearts.length}` : ''}`;
    $('discover-export-text').textContent = hearts.length ? exportText() : '还没有收藏，点击歌曲旁的爱心就能留下。';
    $('discover-copy').disabled = !hearts.length; $('discover-download').disabled = !hearts.length;
    $('discover-favorites').classList.toggle('active', onlyFavorites);
    $('discover-favorites').setAttribute('aria-pressed', String(onlyFavorites));
    $('discover-favorites').textContent = onlyFavorites ? '♥ 已收藏' : '♡ 只看收藏';
  }
  function syncHearts() {
    document.querySelectorAll('.discovery-track').forEach(card => {
      const track = ids.get(card.dataset.id), button = card.querySelector('.heart');
      const saved = hearts.includes(savedKey(track)); button.classList.toggle('on', saved);
      button.setAttribute('aria-pressed', String(saved)); button.setAttribute('aria-label', `${saved ? '取消收藏' : '收藏'}：${track.title}`);
    }); syncExport();
  }
  function favorite(track) {
    const key = savedKey(track); hearts = hearts.includes(key) ? hearts.filter(h => h !== key) : [...hearts, key];
    try { localStorage.setItem('md_hearts', JSON.stringify(hearts)); }
    catch (_) { MD.notify('浏览器暂时无法保存，收藏只保留到本页关闭'); }
    if (onlyFavorites) { render(); focusFirstTrack(); } else syncHearts();
  }
  function card(track) {
    const article = el('article', 'discovery-track'); article.dataset.id = track.id;
    const cover = el('div', 'discover-artwork');
    if (track.cover) { const img = el('img'); img.src = track.cover.replace('600x600bb', '160x160bb'); img.alt = ''; img.loading = 'lazy'; img.width = 80; img.height = 80; cover.append(img); }
    else cover.append(el('span', 'discover-cover-missing', '♪'));
    const info = el('div', 'discover-info'); info.append(el('h2', '', track.title), el('p', 'discover-artist', track.artist), el('p', 'discover-album', `${track.album} · ${track.year}`));
    const links = el('div', 'discover-links');
    for (const [url, label] of [[track.apple, 'APPLE MUSIC ↗'], ['https://open.spotify.com/search/' + encodeURIComponent(`${track.artist} ${track.title}`), 'SPOTIFY 搜索 ↗']]) {
      if (!url) continue; const a = el('a', '', label); a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; links.append(a);
    }
    info.append(links);
    const controls = el('div', 'discover-controls');
    const play = iconButton('discover-play', DISCOVERY_ICONS.play + DISCOVERY_ICONS.pause, `试听：${track.title}`); play.append(el('span', '', track.preview ? '试听片段' : '暂无试听')); play.disabled = !track.preview; play.addEventListener('click', () => toggle(track, play)); controls.append(play); buttons.set(track.id, play);
    const heart = iconButton('heart', DISCOVERY_ICONS.heart, `收藏：${track.title}`); heart.addEventListener('click', () => favorite(track)); controls.append(heart);
    article.append(cover, info, controls); return article;
  }
  function render() {
    const terms = normalize($('discover-search').value).split(/\s+/).filter(Boolean), genre = $('discover-genre').value, decade = $('discover-decade').value;
    filtered = tracks.filter(t => terms.every(term => haystacks.get(t.id).includes(term)) && (!genre || t.genre === genre) && (!decade || t.year.slice(0, 3) + '0' === decade) && (!onlyFavorites || hearts.includes(savedKey(t))));
    const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE)); page = Math.min(page, pages - 1);
    buttons = new Map(); const fragment = document.createDocumentFragment(); filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE).forEach(t => fragment.append(card(t))); $('discover-list').replaceChildren(fragment);
    $('discover-count').textContent = `找到 ${filtered.length.toLocaleString('zh-CN')} / ${tracks.length.toLocaleString('zh-CN')} 首`;
    $('discover-page').textContent = `${page + 1} / ${pages}`; $('discover-prev-page').disabled = page === 0; $('discover-next-page').disabled = page + 1 >= pages;
    $('discover-empty').hidden = filtered.length > 0; syncHearts(); syncPlayback();
  }
  function reset() { $('discover-search').value = ''; $('discover-genre').value = ''; $('discover-decade').value = ''; onlyFavorites = false; page = 0; render(); }
  ['discover-search', 'discover-genre', 'discover-decade'].forEach(id => $(id).addEventListener(id === 'discover-search' ? 'input' : 'change', () => { page = 0; render(); }));
  $('discover-reset').addEventListener('click', reset); $('discover-empty-reset').addEventListener('click', () => { reset(); $('discover-search').focus(); });
  $('discover-favorites').addEventListener('click', () => { onlyFavorites = !onlyFavorites; page = 0; render(); });
  function focusFirstTrack() { const title = $('discover-list').querySelector('h2'); if (title) { title.tabIndex = -1; title.focus({preventScroll:true}); } else $('discover-empty-reset').focus({preventScroll:true}); }
  function turn(direction) { page += direction; render(); $('discover-list').scrollIntoView({block:'start', behavior:'auto'}); focusFirstTrack(); }
  $('discover-prev-page').addEventListener('click', () => turn(-1)); $('discover-next-page').addEventListener('click', () => turn(1));
  $('discover-export').addEventListener('click', () => { syncExport(); $('discover-export-box').hidden = false; $('discover-export-box').scrollIntoView({block:'start',behavior:'auto'}); $('discover-copy').focus({preventScroll:true}); });
  $('discover-export-close').addEventListener('click', () => { $('discover-export-box').hidden = true; $('discover-export').focus(); });
  $('discover-copy').addEventListener('click', () => MD.copyText(exportText(), $('discover-copy'), $('discover-export-text')));
  $('discover-download').addEventListener('click', () => {
    const url = URL.createObjectURL(new Blob(['\uFEFF' + exportText()], {type:'text/plain;charset=utf-8'}));
    const a = el('a'); a.href = url; a.download = 'music-daily-favorites.txt'; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  window.addEventListener('storage', event => { if (event.key === 'md_hearts' || event.key === null) { try { hearts = [...new Set(MD.readList(localStorage, 'md_hearts'))]; } catch (_) {} render(); } });
  $('discover-start').addEventListener('click', () => { const track = filtered.find(t => t.preview); if (track) load(track, $('discover-start')); else MD.notify('当前筛选没有可试听曲目'); });
  $('np-toggle').addEventListener('click', () => current ? toggle(current) : step(1)); $('np-prev').addEventListener('click', () => step(-1)); $('np-next').addEventListener('click', () => step(1));
  $('np-close').addEventListener('click', () => { ++generation; audio.pause(); audio.removeAttribute('src'); audio.load(); player.classList.remove('on'); current = null; syncPlayback(); if (lastPlayTrigger?.isConnected) lastPlayTrigger.focus(); else $('discover-start').focus(); });
  audio.addEventListener('playing', () => { if (current) $('np-artist').textContent = current.artist; syncPlayback(); });
  audio.addEventListener('pause', syncPlayback); audio.addEventListener('ended', syncPlayback); audio.addEventListener('error', () => { if (audio.error) fail(audio.error, generation); });
  const fmt = value => `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, '0')}`;
  function previewDuration() { return Number.isFinite(audio.duration) && audio.duration > 0 ? Math.min(audio.duration, PREVIEW_SECONDS) : PREVIEW_SECONDS; }
  audio.addEventListener('timeupdate', () => { if (!Number.isFinite(audio.duration) || audio.duration <= 0) return; const duration = previewDuration(); if (audio.currentTime >= duration && !audio.paused) audio.pause(); const seconds = Math.min(audio.currentTime, duration), percent = seconds / duration * 100; $('np-fill').style.width = `${percent}%`; $('np-time').textContent = `${fmt(seconds)} / ${fmt(duration)}`; $('np-bar').setAttribute('aria-valuenow', String(Math.round(percent))); $('np-bar').setAttribute('aria-valuetext', fmt(seconds)); });
  $('np-bar').addEventListener('click', event => { if (!Number.isFinite(audio.duration)) return; const rect = $('np-bar').getBoundingClientRect(); audio.currentTime = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)) * previewDuration(); });
  $('np-bar').addEventListener('keydown', event => { if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key) || !Number.isFinite(audio.duration)) return; event.preventDefault(); event.stopPropagation(); const duration = previewDuration(); audio.currentTime = event.key === 'Home' ? 0 : event.key === 'End' ? duration : Math.max(0, Math.min(duration, audio.currentTime + (event.key === 'ArrowRight' ? 5 : -5))); });
  document.addEventListener('keydown', event => { if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || event.repeat || event.target.closest('input,textarea,select,button,a,[contenteditable=true],[role=slider]') || document.querySelector('.manual-copy')) return; if (event.code === 'Space' && current) { event.preventDefault(); toggle(current); } });
  render();
})();
