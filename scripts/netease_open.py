"""点 netease 按钮时唤起本机网易云 App（而不是开网页）。

为什么不是直达单曲页：需要网易云的 song id，而容器访问不到 music.163.com
（实测 HTTP 000，同时 iTunes 200 —— 是目标站不可达，不是没网），
拿不到 id。所以落到「曲名 + 艺人名」的**App 内搜索结果页**，实际几乎总是第一条。

唤起机制（`orpheus://` 是网易云注册的 scheme，iOS / Android / Win / mac 都认）：
把 scheme 赋给隐藏 iframe.src 而不是 location.href —— 后者在 scheme 未注册时
Safari 会弹「无法打开页面」的报错框，iframe 不会。
然后起一个 1.2s 的定时器兜底跳网页；若 App 真被唤起，页面会转入后台，
`visibilitychange`/`pagehide` 触发，我们据此取消兜底，避免回来时发现多开了一个网页。
"""
from __future__ import annotations

NETEASE_OPEN_JS = """
(function(){
  // orpheus://search/曲名 艺人 —— 网易云 App 的搜索入口（各平台一致）
  function scheme(q){ return 'orpheus://search/' + encodeURIComponent(q); }
  function web(q){ return 'https://music.163.com/#/search/m/?s=' + encodeURIComponent(q); }

  function openApp(q){
    var fallback = null, done = false;
    function cancel(){
      if(done) return; done = true;
      if(fallback){ clearTimeout(fallback); fallback = null; }
      document.removeEventListener('visibilitychange', onHide);
      removeEventListener('pagehide', onHide);
      removeEventListener('blur', onHide);
    }
    // 页面转后台/失焦 = App 被唤起了
    function onHide(){ cancel(); }

    // App 真被唤起 → 本页转后台 → 取消兜底，避免回来时多了一个网页 tab
    document.addEventListener('visibilitychange', onHide);
    addEventListener('pagehide', onHide);
    addEventListener('blur', onHide);

    // 用隐藏 iframe 触发 scheme：scheme 未注册时 location.href 会让 Safari
    // 弹「无法打开页面」，iframe 静默失败
    var f = document.createElement('iframe');
    f.style.cssText = 'display:none;width:0;height:0;border:0';
    f.src = scheme(q);
    document.body.appendChild(f);
    setTimeout(function(){ try{ f.remove(); }catch(e){} }, 1500);

    // 1.2s 没走成就回退网页（没装 App / 桌面浏览器不认 scheme）
    fallback = setTimeout(function(){
      if(done) return;
      done = true;
      window.open(web(q), '_blank', 'noopener');
    }, 1200);
  }

  document.addEventListener('click', function(e){
    var a = e.target.closest('[data-nc]');
    if(!a) return;
    e.preventDefault();
    openApp(a.getAttribute('data-nc'));
  });
})();
"""
