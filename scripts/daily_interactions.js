// Inlined by render_grid.py: no extra request, shared by today's and archive issues.
const boot = document.getElementById('boot');
if (boot) boot.textContent = boot.dataset.text || '';

async function copyPanel(textId, buttonId) {
  const panel = document.getElementById(textId), button = document.getElementById(buttonId);
  if (!panel || !button) return;
  const original = button.dataset.label || button.textContent;
  button.dataset.label = original;
  clearTimeout(button.copyTimer);
  try {
    if (!navigator.clipboard) throw new Error('clipboard unavailable');
    await navigator.clipboard.writeText(panel.textContent);
    button.textContent = '已复制 ✓';
  } catch (_) {
    const range = document.createRange();
    range.selectNodeContents(panel);
    const selection = window.getSelection();
    if (selection) { selection.removeAllRanges(); selection.addRange(range); }
    button.textContent = '已选中清单，请长按或按 Ctrl+C 复制';
  }
  button.copyTimer = setTimeout(() => { button.textContent = original; }, 2400);
}
function copyNC() { return copyPanel('nc-text', 'nc-btn'); }
function copyFav() { return copyPanel('fav-text', 'fav-copy'); }

// A new Audio per source isolates late errors/playing events after rapid switching.
// Only a current play() attempt may change controls (including resume and autoplay).
(() => {
  const buttons = Array.from(document.querySelectorAll('.pbtn'));
  const np = document.getElementById('np');
  if (!np) return;
  const cover = document.getElementById('np-cover'), title = document.getElementById('np-title');
  const artist = document.getElementById('np-artist'), seek = document.getElementById('np-seek');
  const time = document.getElementById('np-time'), toggle = document.getElementById('np-toggle');
  let audio = null, current = null, attempt = 0, failures = 0, pending = false;
  const failed = new Set();
  const fmt = value => { const n = Math.floor(Number.isFinite(value) ? Math.max(0, value) : 0); return Math.floor(n / 60) + ':' + String(n % 60).padStart(2, '0'); };
  const available = () => buttons.filter(b => !b.closest('.mod').classList.contains('hidden'));
  function mark(on) {
    if (current) {
      current.classList.toggle('playing', on);
      current.setAttribute('aria-label', (on ? '暂停试听 ' : '试听 ') + current.dataset.title);
      current.setAttribute('aria-pressed', String(on));
    }
    np.classList.toggle('playing', on);
    toggle.setAttribute('aria-label', on ? '暂停试听' : '播放试听');
  }
  function busy(on) {
    pending = on;
    np.setAttribute('aria-busy', String(on));
    if (current) current.classList.toggle('loading', on);
  }
  function progress() {
    const duration = audio && audio.duration;
    const ready = Number.isFinite(duration) && duration > 0;
    seek.disabled = !ready;
    seek.value = ready ? Math.min(100, audio.currentTime / duration * 100) : 0;
    time.textContent = fmt(audio && audio.currentTime) + ' / ' + fmt(duration);
    seek.setAttribute('aria-valuetext', time.textContent);
  }
  function fail(source, message) {
    if (audio !== source || !source.playRequested || source.failureReported) return;
    source.failureReported = true;
    busy(false); mark(false);
    failed.add(current.dataset.src);
    current.classList.add('dead');
    current.title = '暂时无法试听，再点一次重试';
    current.setAttribute('aria-label', '重新试听 ' + current.dataset.title);
    failures++;
    const candidates = available().filter(b => !failed.has(b.dataset.src));
    if (failures < 6 && candidates.length) step(1, true);
    else artist.textContent = message + '，点播放重试';
  }
  async function play() {
    if (!audio) return;
    const source = audio, ticket = ++attempt;
    source.playRequested = true;
    busy(true);
    try {
      await source.play();
      if (source !== audio || ticket !== attempt) return;
      busy(false); mark(true);
      failures = 0;
      failed.delete(current.dataset.src);
      current.classList.remove('dead');
      current.removeAttribute('title');
    } catch (error) {
      if (source !== audio || ticket !== attempt) return;
      busy(false); mark(false);
      if (error.name === 'AbortError') return;
      if (error.name === 'NotAllowedError') {
        artist.textContent = '点播放键开始试听';
      } else fail(source, '试听暂时不可用');
    }
  }
  function pause() {
    ++attempt;
    busy(false);
    if (audio) { audio.playRequested = false; audio.pause(); }
    mark(false);
  }
  function load(button, skipped = false) {
    pause();
    if (audio) { audio.removeAttribute('src'); audio.load(); }
    current = button;
    const source = new Audio();
    audio = source;
    source.preload = 'none';
    source.src = button.dataset.src;
    cover.hidden = !button.dataset.cover;
    if (button.dataset.cover) cover.src = button.dataset.cover;
    title.textContent = button.dataset.title;
    artist.textContent = skipped ? '上一首取不到音源，已跳到这首' : button.dataset.artist;
    np.classList.add('on');
    progress();
    source.addEventListener('timeupdate', () => { if (source === audio) progress(); });
    source.addEventListener('loadedmetadata', () => { if (source === audio) progress(); });
    source.addEventListener('pause', () => { if (source === audio) mark(false); });
    source.addEventListener('waiting', () => { if (source === audio && source.playRequested && !source.paused) busy(true); });
    source.addEventListener('playing', () => {
      if (source !== audio) return;
      if (!source.playRequested) { source.pause(); return; }
      if (!source.paused) { busy(false); mark(true); }
    });
    source.addEventListener('error', () => fail(source, '连续音源无法试听'));
    source.addEventListener('ended', () => { if (source === audio && source.playRequested) { mark(false); step(1); } });
    play();
  }
  function select(button) {
    failures = 0;
    if (button !== current || !audio || audio.error || failed.has(button.dataset.src)) load(button);
    else if (pending || !audio.paused) pause();
    else play();
  }
  function step(direction, skipped = false) {
    const list = available();
    if (!list.length) { pause(); artist.textContent = '当前筛选没有可试听歌曲'; return; }
    const index = list.indexOf(current);
    for (let offset = 1; offset <= list.length; offset++) {
      const next = list[((index < 0 ? (direction > 0 ? -1 : 0) : index) + direction * offset + list.length * 2) % list.length];
      if (!skipped || !failed.has(next.dataset.src)) { load(next, skipped); return; }
    }
    pause(); artist.textContent = '当前音源无法试听，点播放重试';
  }
  buttons.forEach(button => button.addEventListener('click', () => select(button)));
  toggle.addEventListener('click', () => { const button = current || available()[0]; if (button) select(button); });
  document.getElementById('np-prev').addEventListener('click', () => { failures = 0; step(-1); });
  document.getElementById('np-next').addEventListener('click', () => { failures = 0; step(1); });
  seek.addEventListener('input', () => {
    if (audio && Number.isFinite(audio.duration) && audio.duration > 0) {
      audio.currentTime = Math.max(0, Math.min(100, Number(seek.value))) / 100 * audio.duration;
      progress();
    }
  });
  document.addEventListener('keydown', event => {
    if (event.defaultPrevented || event.repeat || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.target.closest('button,a,input,textarea,select,[contenteditable], [role=button]')) return;
    const modal = document.getElementById('lb');
    if (modal && modal.classList.contains('on')) return;
    if (event.code === 'Space') { event.preventDefault(); toggle.click(); }
    else if (current && event.key === 'ArrowRight') { event.preventDefault(); step(1); }
    else if (current && event.key === 'ArrowLeft') { event.preventDefault(); step(-1); }
  });
})();

// Existing long-term browser favorites remain separate from shuffle's session basket.
(() => {
  const key = 'md_hearts', cards = Array.from(document.querySelectorAll('.mod[data-k]'));
  const count = document.getElementById('fav-n'), only = document.getElementById('fav-only');
  const search = document.getElementById('track-search'), note = document.getElementById('filter-note');
  const empty = document.getElementById('empty-list'), box = document.getElementById('fav-box');
  const text = document.getElementById('fav-text');
  function read() {
    try {
      const parsed = JSON.parse(localStorage.getItem(key) || '[]');
      return new Set(Array.isArray(parsed) ? parsed.filter(x => typeof x === 'string' && x.trim()) : []);
    } catch (_) { return null; }
  }
  let hearts = read() || new Set(), saveWarning = false;
  const normalize = value => value.normalize('NFKC').toLocaleLowerCase().trim();
  const index = new Map(cards.map(card => [card, normalize(card.querySelector('.hd').textContent)]));
  function refresh() {
    const terms = normalize(search.value).split(/\s+/).filter(Boolean);
    const favorites = document.body.classList.contains('fav-mode');
    let hits = 0, visible = 0;
    cards.forEach(card => {
      const selected = hearts.has(card.dataset.k), button = card.querySelector('.heart');
      if (selected) hits++;
      button.classList.toggle('on', selected);
      button.setAttribute('aria-pressed', String(selected));
      button.setAttribute('aria-label', (selected ? '取消收藏 ' : '收藏 ') + card.querySelector('.title').textContent);
      const show = (!favorites || selected) && terms.every(term => index.get(card).includes(term));
      card.classList.toggle('hidden', !show);
      card.hidden = !show;
      if (show) visible++;
    });
    document.querySelectorAll('.mod.fill').forEach(fill => { fill.hidden = !visible || visible % 2 === 0; });
    count.textContent = hits;
    only.classList.toggle('active', favorites);
    only.setAttribute('aria-pressed', String(favorites));
    empty.hidden = visible > 0;
    document.getElementById('empty-message').textContent = favorites ? '本期没有符合条件的收藏，试试清除搜索或查看全部。' : '没有找到这首歌，试试歌名、艺人或风格。';
    note.textContent = (saveWarning ? '收藏暂存在当前页面，浏览器未能保存。 · ' : '') + '显示 ' + visible + ' / ' + cards.length + ' 首';
    text.textContent = hearts.size ? '我收藏的 · MUSIC DAILY（含往期，共 ' + hearts.size + ' 首）\n' + Array.from(hearts).join('\n') : '（还没有收藏。点歌曲右上角的 ♥ 即可）';
  }
  cards.forEach(card => card.querySelector('.heart').addEventListener('click', () => {
    if (!saveWarning) hearts = read() || hearts;
    const value = card.dataset.k;
    if (hearts.has(value)) hearts.delete(value); else hearts.add(value);
    try { localStorage.setItem(key, JSON.stringify(Array.from(hearts))); saveWarning = false; }
    catch (_) { saveWarning = true; }
    refresh();
  }));
  only.addEventListener('click', () => { document.body.classList.toggle('fav-mode'); refresh(); });
  search.addEventListener('input', refresh);
  document.getElementById('filter-reset').addEventListener('click', () => {
    search.value = ''; document.body.classList.remove('fav-mode'); refresh(); search.focus();
  });
  document.getElementById('fav-export').addEventListener('click', () => {
    refresh(); box.style.display = 'block'; box.scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
  });
  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) { hearts = read() || new Set(); saveWarning = false; refresh(); }
  });
  refresh();
})();

(() => {
  const button = document.getElementById('share-btn');
  if (!button || (!navigator.share && !navigator.clipboard)) return;
  button.hidden = false;
  const label = navigator.share ? '分享这期' : '复制本期链接';
  button.textContent = label;
  button.addEventListener('click', async () => {
    if (button.disabled) return;
    button.disabled = true;
    try {
      if (navigator.share) await navigator.share({title: document.title, url: location.href.split('#')[0]});
      else { await navigator.clipboard.writeText(location.href.split('#')[0]); button.textContent = '链接已复制 ✓'; }
    } catch (error) {
      if (error.name !== 'AbortError') button.textContent = '请复制地址栏链接';
    } finally {
      button.disabled = false;
      setTimeout(() => { button.textContent = label; }, 2000);
    }
  });
})();
