"""Shared navigation, accessible feedback and controls for the static magazine."""
from __future__ import annotations

import html


def site_nav(active: str, prefix: str = "") -> str:
    pages = (("home", "index.html", "唱片室"), ("daily", "daily.html", "今日精选"),
             ("random", "random.html", "听点别的"), ("discover", "discover.html", "新发现"),
             ("archive", "archive/index.html", "往期"))
    links = ""
    for key, path, label in pages:
        current = ' aria-current="page"' if key == active else ""
        links += f'<a href="{html.escape(prefix + path)}"{current}>{label}</a>'
    return ('<a class="skip-link" href="#main">跳到内容</a>'
            '<nav class="nav site-nav" aria-label="主导航"><div class="wrap">'
            f'<a class="brand" href="{html.escape(prefix)}index.html" aria-label="MUSIC DAILY 首页">'
            '<span class="sq" aria-hidden="true"></span>MUSIC DAILY<span class="brand-note">独立音乐日刊</span></a>'
            f'<div class="nav-links">{links}</div></div></nav>')


UI_CSS = r"""
/* Shared magazine controls; the page renderers own their compositions. */
[hidden]{display:none!important}
button,input,select,textarea{font:inherit}
button,a,input,select{-webkit-tap-highlight-color:transparent}
button:disabled{cursor:default;opacity:.5}
button,a{touch-action:manipulation}
:focus-visible{outline:3px solid var(--orange);outline-offset:4px}
.skip-link{position:fixed;left:16px;top:-100px;padding:14px 20px;background:var(--ink);color:white;z-index:9999}
.skip-link:focus{top:12px}
.site-nav{background:var(--paper);color:var(--ink);border-bottom:1px solid var(--g200)}
.site-nav .wrap{height:76px;gap:24px}
.site-nav .brand{font-weight:400;font-size:18px;letter-spacing:-.04em;white-space:nowrap}
.brand-note{font:11px var(--sans);letter-spacing:.08em;margin-left:8px;color:var(--g600)}
.nav-links{display:flex;gap:24px;align-items:center;white-space:nowrap}
.nav-links a{font-size:13px;min-height:44px;display:flex;align-items:center;border-bottom:2px solid transparent}
.nav-links a[aria-current=page]{border-color:var(--orange);color:var(--ink)}
.nav-links a:hover{color:var(--orange)}
.eyebrow{font:12px var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--g600)}
.lead{font-size:15px;line-height:1.8;color:var(--g900);max-width:44em;margin-top:18px}
.primary-action{display:inline-flex;align-items:center;justify-content:center;min-height:48px;padding:12px 22px;background:var(--orange);color:#fff;border:1px solid var(--orange);font-size:14px;cursor:pointer;gap:12px}
.primary-action:hover{background:#a93a20;border-color:#a93a20}
.filterbar{display:flex;align-items:flex-end;gap:12px;flex-wrap:wrap;margin:24px 0 14px}
.field{display:grid;gap:7px;min-width:130px;font-size:12px;color:var(--g900)}
.field.search-field{flex:1;min-width:200px}
.field input,.field select{width:100%;height:46px;padding:10px 12px;background:var(--white);border:1px solid var(--g200);color:var(--ink);border-radius:0;font-size:14px}
.filter-status{font-size:12px;color:var(--g600);display:flex;justify-content:space-between;gap:12px;margin:14px 0}
.empty-state{border:1px dashed var(--g300);padding:40px 24px;text-align:center;color:var(--g900);line-height:1.8}
.empty-state strong{display:block;color:var(--ink);font-size:18px;margin-bottom:6px}
.empty-state button{margin-top:16px}
.tbtn,.btn{min-height:44px;align-items:center;justify-content:center;font-size:12px;text-transform:none}
.tbtn:hover,.btn:hover{opacity:1;background:var(--g100)}
.btn.solid:hover{background:var(--g1000)}
.heart{min-width:44px;min-height:44px;display:inline-grid;place-items:center;padding:0}
.heart svg{width:20px;height:20px}
.pbtn{width:44px;height:44px;left:8px;bottom:8px;opacity:1}
.pbtn svg{width:15px;height:15px}
.np-btn,#np-prev,#np-next{width:44px;height:44px;background:transparent;border:1px solid #57534c}
#np-toggle{background:var(--orange);border-color:var(--orange)}
#np-close{font-size:20px}
#np-bar{min-height:24px;background:linear-gradient(#57534c,#57534c) center / 100% 3px no-repeat}
#np-fill{top:10px;bottom:10px;background:var(--orange);pointer-events:none}
#md-toast{position:fixed;bottom:calc(96px + env(safe-area-inset-bottom,0px));left:50%;transform:translateX(-50%);max-width:calc(100% - 32px);width:max-content;background:var(--ink);color:#fff;font-size:13px;line-height:1.7;padding:12px 20px;z-index:4000;border-left:3px solid var(--orange);pointer-events:none}
.manual-copy{position:fixed;z-index:4001;inset:auto 16px calc(100px + env(safe-area-inset-bottom,0px));max-width:600px;margin:auto;background:var(--paper);border:1px solid var(--ink);padding:16px}
.manual-copy textarea{display:block;width:100%;height:110px;margin:12px 0;padding:10px;font-size:14px}
@media(max-width:760px){
 .site-nav .wrap{height:auto;min-height:68px;flex-wrap:wrap;gap:2px;padding-top:14px;padding-bottom:0}
 .brand-note{display:none}.nav-links{gap:22px;width:100%;justify-content:space-between}.nav-links a{font-size:12px}
 .filterbar{gap:10px}.field.search-field{flex-basis:100%}.field{flex:1}
 #np-cover{width:36px;height:36px}#np-meta{flex:1;width:auto}#np{gap:7px;padding-left:calc(12px + var(--sal));padding-right:calc(12px + var(--sar))}
 #np-bar,#np-prev{display:none}#np-close{width:32px;min-width:32px;border:0}.np-btn,#np-next{width:40px;height:44px}
}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important;scroll-behavior:auto!important}}
"""


UI_JS = r"""
window.MD = (() => {
  let toastTimer;
  function notify(message) {
    let box = document.getElementById('md-toast');
    if (!box) { box = document.createElement('div'); box.id = 'md-toast'; box.setAttribute('role','status'); document.body.append(box); }
    clearTimeout(toastTimer); box.textContent = message; box.hidden = false;
    toastTimer = setTimeout(() => { box.hidden = true; }, 3800);
  }
  function readList(storage, key, validator = x => typeof x === 'string' && x.trim().length > 0) {
    try { const data = JSON.parse(storage.getItem(key) || '[]'); return Array.isArray(data) ? data.filter(validator) : []; }
    catch (_) { return []; }
  }
  // Clipboard writes may reject or be unavailable outside secure contexts.
  // https://developer.mozilla.org/en-US/docs/Web/API/Clipboard/writeText
  async function copyText(text, button, fallbackElement) {
    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error('unavailable');
      await navigator.clipboard.writeText(text); notify('已复制'); return true;
    } catch (_) {
      if (fallbackElement && !fallbackElement.closest('[hidden]')) {
        const range = document.createRange(); range.selectNodeContents(fallbackElement);
        const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
        fallbackElement.scrollIntoView({block:'center'});
        notify('自动复制未成功，清单已选中，请长按或按 Ctrl/Cmd+C 复制');
      } else {
        document.querySelector('.manual-copy')?.remove();
        const panel = document.createElement('section'); panel.className = 'manual-copy';
        const label = document.createElement('label'); label.textContent = '自动复制未成功，请手动复制';
        const input = document.createElement('textarea'); input.value = text; input.readOnly = true; input.setAttribute('aria-label','待复制的文本');
        const close = document.createElement('button'); close.className = 'tbtn'; close.textContent = '完成';
        function dismiss(){panel.remove();button?.focus();}
        close.addEventListener('click',dismiss); panel.addEventListener('keydown',e=>{if(e.key==='Escape')dismiss();});
        panel.append(label,input,close); document.body.append(panel); input.focus(); input.select();
      }
      return false;
    }
  }
  return {notify, copyText, readList};
})();
document.addEventListener('error', event => {
  if (event.target instanceof HTMLImageElement) { event.target.classList.add('image-missing'); event.target.alt = event.target.alt || '封面暂不可用'; }
}, true);
"""
