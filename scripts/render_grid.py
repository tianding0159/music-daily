"""渲染工业 / 瑞士国际主义(Swiss)风格的每日日报网页（纯 Python 模板，零依赖）。

设计规范（自研的工程/网格美学，不隶属任何特定品牌）：
- 字体：Univers Next Pro 的免费替身 Inter 100/300（极细）+ Space Mono（技术数据）+ Noto Sans SC；
  标题小写、正文字重 300、层级靠字号不靠加粗。
- 配色：底 #f5f5f5（非纯白）、字 #0f0e12（非纯黑）、发丝灰阶、蓝 #0071bb / LCD 绿 #006837 /
  强调橙 #f05a24。多色做流派分类色标。
- 版式：12 栏网格、方角（border-radius:0）、几乎无阴影、发丝线 + 工程方格纸分格、vw/clamp 间距。
- 动效：极度克制、.2s、hover opacity:.7、播放键 scale(.94)+bulge、LCD 跑马灯 + boot 打字机、
  卡片 IntersectionObserver 分级进场。

公开接口 build_html(date_str, tracks, issue_no, netease_text) 与 render.py 一致。
"""
from __future__ import annotations

import html
from pathlib import Path
import re
import urllib.parse

# LCD 上的像素小猫（绿屏设备宠物感）：会眨眼(cat-eyes)、甩尾(cat-tail)、轻轻呼吸摇摆(整体 bob)
# Q 版像素猫（chibi 比例：头身 1:1、大圆眼带高光、橘白奶牛配色 + 粉肉垫/粉腮）
def _cat_pose(cls: str, body: str) -> str:
    return (f'<svg class="cat pose {cls}" viewBox="0 0 22 21" shape-rendering="crispEdges" aria-hidden="true">'
            f'{body}</svg>')


# 共用：大脑袋（占画面上 2/3）+ 大圆眼 + 粉腮 + 橘斑
_HEAD = (
    '<g class="fur">'                                                  # 白底大头
    '<rect x="3" y="1" width="3" height="2"/><rect x="12" y="1" width="3" height="2"/>'   # 耳朵
    '<rect x="2" y="2" width="14" height="9"/><rect x="1" y="4" width="16" height="6"/>'
    '</g>'
    '<g class="fur2">'                                                 # 橘色斑纹（额头 + 右脸）
    '<rect x="3" y="1" width="3" height="2"/><rect x="2" y="2" width="4" height="2"/>'
    '<rect x="12" y="4" width="4" height="4"/>'
    '</g>'
    '<g class="cat-eyes">'                                             # 粗横线眼（呆呆的）
    '<rect x="4" y="6" width="4" height="1"/><rect x="10" y="6" width="4" height="1"/>'
    '</g>'
    '<rect class="mouth" x="8" y="8" width="2" height="1"/>'           # 小嘴上提，贴近眼睛
    '<rect class="blush" x="2" y="9" width="2" height="1"/><rect class="blush" x="14" y="9" width="2" height="1"/>')

# ① 站立（矮胖四肢）
ICON_CAT_STAND = _cat_pose("p-stand",
    '<g class="cat-tail fur"><rect x="16" y="12" width="2" height="2"/><rect x="17" y="10" width="2" height="2"/>'
    '<rect x="18" y="9" width="2" height="2"/></g>' + _HEAD +
    '<g class="fur"><rect x="4" y="12" width="10" height="4"/>'
    '<rect x="4" y="16" width="3" height="2"/><rect x="11" y="16" width="3" height="2"/></g>'
    '<g class="fur2"><rect x="10" y="12" width="4" height="2"/></g>'
    '<g class="pad"><rect x="4" y="16" width="3" height="1"/><rect x="11" y="16" width="3" height="1"/></g>')

# ② 蹲坐（团成一团）
ICON_CAT_SIT = _cat_pose("p-sit",
    '<g class="cat-tail fur"><rect x="16" y="14" width="3" height="2"/><rect x="18" y="12" width="2" height="2"/></g>'
    + _HEAD +
    '<g class="fur"><rect x="4" y="11" width="10" height="5"/><rect x="3" y="13" width="12" height="3"/></g>'
    '<g class="pad"><rect x="5" y="15" width="2" height="1"/><rect x="11" y="15" width="2" height="1"/></g>')

# ③ 伸懒腰（身体拉长、屁股翘）
ICON_CAT_STRETCH = _cat_pose("p-stretch",
    '<g class="cat-tail fur"><rect x="18" y="5" width="2" height="2"/><rect x="19" y="3" width="2" height="2"/></g>'
    '<g class="fur"><rect x="2" y="2" width="3" height="2"/><rect x="8" y="1" width="3" height="2"/>'
    '<rect x="1" y="3" width="11" height="5"/><rect x="0" y="5" width="14" height="4"/>'
    '<rect x="13" y="4" width="6" height="6"/>'
    '<rect x="1" y="9" width="3" height="2"/><rect x="14" y="10" width="3" height="3"/></g>'
    '<g class="fur2"><rect x="13" y="4" width="6" height="2"/></g>'
    '<g class="cat-eyes"><rect x="2" y="5" width="3" height="1"/></g>'
    '<rect class="nose" x="0" y="6" width="1" height="1"/>'
    '<g class="pad"><rect x="1" y="10" width="3" height="1"/></g>')

# ④ 舔爪（歪头 + 抬爪）
ICON_CAT_LICK = _cat_pose("p-lick",
    '<g class="cat-tail fur"><rect x="16" y="14" width="3" height="2"/><rect x="18" y="13" width="2" height="2"/></g>'
    + _HEAD +
    '<g class="fur"><rect x="4" y="11" width="10" height="5"/>'
    '<rect x="8" y="8" width="3" height="5"/></g>'                       # 抬起的前爪
    '<g class="pad"><rect x="8" y="8" width="3" height="1"/><rect x="5" y="15" width="2" height="1"/></g>')

# ⑤ 趴睡（摊平 + 闭眼 + Zzz）
ICON_CAT_SLEEP = _cat_pose("p-sleep",
    '<g class="cat-tail fur"><rect x="17" y="15" width="3" height="1"/><rect x="19" y="14" width="2" height="1"/></g>'
    '<g class="fur"><rect x="3" y="6" width="3" height="2"/><rect x="12" y="6" width="3" height="2"/>'
    '<rect x="2" y="7" width="14" height="7"/><rect x="1" y="9" width="16" height="5"/>'
    '<rect x="14" y="11" width="5" height="4"/></g>'
    '<g class="fur2"><rect x="3" y="6" width="3" height="2"/><rect x="12" y="9" width="4" height="3"/></g>'
    '<g class="cat-eyes"><rect x="4" y="10" width="3" height="1"/><rect x="11" y="10" width="3" height="1"/></g>'
    '<rect class="nose" x="8" y="11" width="2" height="1"/>'
    '<rect class="blush" x="2" y="11" width="2" height="1"/>'
    '<g class="zzz"><rect x="17" y="4" width="3" height="1"/><rect x="19" y="5" width="1" height="1"/>'
    '<rect x="17" y="6" width="3" height="1"/></g>')

ICON_CAT = (ICON_CAT_STAND + ICON_CAT_SIT + ICON_CAT_STRETCH + ICON_CAT_LICK + ICON_CAT_SLEEP)

# 道具：食盆（带小鱼骨）、毛线球
ICON_BOWL = ('<svg viewBox="0 0 14 8" shape-rendering="crispEdges" aria-hidden="true">'
             '<rect class="fish" x="4" y="0" width="4" height="1"/><rect class="fish" x="3" y="1" width="1" height="1"/>'
             '<rect class="fish" x="8" y="1" width="1" height="1"/>'
             '<rect class="food" x="3" y="2" width="8" height="1"/>'
             '<rect x="1" y="3" width="12" height="1"/><rect x="2" y="4" width="10" height="3"/></svg>')
ICON_BALL = ('<svg viewBox="0 0 8 8" shape-rendering="crispEdges" aria-hidden="true">'
             '<rect x="1" y="1" width="6" height="6"/><rect class="hl" x="1" y="1" width="2" height="2"/>'
             '<rect class="yarn" x="3" y="2" width="1" height="4"/><rect class="yarn" x="2" y="4" width="4" height="1"/></svg>')

# 试听播放/暂停键（叠在封面左下，播放 iTunes 公开 30s previewUrl；仅预览、非整曲）
ICON_PLAY = '<svg class="i-play" viewBox="0 0 10 10" aria-hidden="true"><path d="M2 1 L9 5 L2 9 Z"/></svg>'
ICON_PAUSE = '<svg class="i-pause" viewBox="0 0 10 10" aria-hidden="true"><rect x="2" y="1" width="2.6" height="8"/><rect x="5.4" y="1" width="2.6" height="8"/></svg>'

# 上一首/下一首（整期贯穿播放）+ 收藏心形（filled 由 .on 控制色）
ICON_PREV = '<svg viewBox="0 0 12 10" aria-hidden="true"><rect x="1" y="1" width="2" height="8"/><path d="M11 1 L4 5 L11 9 Z"/></svg>'
ICON_NEXT = '<svg viewBox="0 0 12 10" aria-hidden="true"><path d="M1 1 L8 5 L1 9 Z"/><rect x="9" y="1" width="2" height="8"/></svg>'
ICON_HEART = '<svg class="i-heart" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>'

# 工程编码色思路的一组多色 + 补色，做流派分类色标（小面积）
KNOB = ["#0071bb", "#006837", "#f05a24", "#fab413", "#b81d13", "#0f0e12"]


def _knob(seed: str) -> str:
    return KNOB[sum(ord(c) for c in (seed or "x")) % len(KNOB)]


# 站点绝对地址。Open Graph 的 og:url / og:image 必须是绝对 URL —— 相对路径
# 在微信、Twitter 这些抓取端会解析失败，卡片就退化成一条光秃秃的链接。
# 这里是唯一来源，改域名只改这一处。
SITE_URL = "https://tianding0159.github.io/music-daily/"

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
/* hidden 是 HTML 语义属性（同时把元素从无障碍树摘除），必须是硬约束。
   靠 UA 样式表的 [hidden]{display:none} 顶不住：任何组件类只要声明 display
   就把它盖掉 —— 实测 .tbtn{display:inline-flex} 让分享按钮的「没有 share 也
   没有 clipboard 就别显示」门禁完全失效（JS 关掉时按钮照样占 74×36px、
   点了毫无反应；微信内置 webview 正是这种环境）。
   用 !important 表达「这是硬约束」，比给每个组件类打 :not([hidden]) 补丁可靠。 */
[hidden]{display:none !important}
:root{
  /* ── iOS 安全区 ──────────────────────────────────────────────
     四页都声明了 viewport-fit=cover（这是让 env() 返回非零的前提，
     同时也意味着内容真的会铺到刘海/home 条底下）。此前一处 safe-area
     都没用，加到主屏 standalone 打开时实测（iPhone 14 Pro，顶 59px / 底 34px）：
       · 顶栏 nav 高 53px，整条【完全埋在】刘海下，不是压掉一角
       · 吸底播放器 76px 被 home 条压掉 34px，播放键点不到
       · 浮层关闭键距顶 52px < 59px，浮层【关不掉】——这条最严重
     浏览器里 env() 一律是 0，所以加它对普通网页零影响，纯粹是补 standalone。
     fallback 写 0px 而不是省略：老 Safari 不认 env() 时整条声明会被丢弃。 */
  --sat:env(safe-area-inset-top, 0px);
  --sar:env(safe-area-inset-right, 0px);
  --sab:env(safe-area-inset-bottom, 0px);
  --sal:env(safe-area-inset-left, 0px);
  /* 播放器实际占位高度 = 自身高度 + 底部安全区。随机页的篮子要叠在它上方，
     此前两处各写死 76px（#np 的 height 与 #basket 的 bottom），
     加了安全区就会错位 —— 抽成变量，一处改两处跟。 */
  --np-h:76px;
  --white:#fff; --paper:#f5f5f5; --ink:#0f0e12;
  --g100:#e5e5e5; --g200:#ccc; --g300:#b2b2b2; --g500:#a1a7af;
  --g600:#767676; --g900:#4d4d4d; --g1000:#272727;
  --blue:#0071bb; --green:#00a651; --green-d:#006837; --orange:#f05a24;
  --red:#b81d13; --yellow:#fab413;
  --sans:"Inter","Noto Sans SC","Helvetica Neue",Arial,sans-serif;
  /* Space Mono 不含汉字。栈里必须显式给中文字体，否则中文落到【操作系统默认】——
     Windows 是雅黑、Linux 可能是文泉驿，同一页在不同机器上长得不一样。
     2026-08-03 实测（CDP getPlatformFontsForNode）：页面 44 处中文都在这条栈上，
     全部走了系统回退。Noto Sans SC 本来已在 --sans 里引过，复用不增加网络请求。 */
  --mono:"Space Mono","JetBrains Mono","Noto Sans SC",ui-monospace,Menlo,monospace;
  --fs-10:clamp(11px,.92vw,13px); --fs-15:clamp(14px,1.1vw,15px);
  --fs-20:clamp(15px,1.5vw,20px); --fs-25:clamp(19px,2.1vw,27px);
  --fs-30:clamp(23px,2.7vw,36px); --fs-40:clamp(34px,5vw,68px);
  --sp-xs:clamp(4px,.5vw,6px); --sp-sm:clamp(8px,1vw,12px);
  --sp-md:clamp(12px,1.5vw,18px); --sp-lg:clamp(18px,2.3vw,28px);
  --sp-xl:clamp(28px,4vw,52px);
}
html{scroll-behavior:smooth}

/* ── 键盘焦点 ────────────────────────────────────────────────
   此前没有任何 :focus-visible 规则，键盘用户只能看浏览器默认蓝环 ——
   跟这套黑白 + 橙的调性完全不搭，且在深色卡片上几乎看不清。
   用 :focus-visible 而不是 :focus：后者会在【鼠标点击】时也亮起，
   那是多数站点把焦点环整个 outline:none 掉的原因，代价是键盘用户彻底失明。
   :focus-visible 只在浏览器判断「用户在用键盘导航」时才亮。
   本站没有任何 outline:none（实测 0 处），所以这里是纯增强、不夺走兜底。 */
:focus-visible{
  outline:2px solid var(--orange);
  outline-offset:2px;
  border-radius:1px;   /* 方角站点上给焦点环一点点圆，避免看着像边框错位 */
}
/* 深色底上（LCD 屏、唱盘控制条）橙色对比不足，改用亮描边 + 橙外圈。
   **浮层不在这一类**：它的 .sheet 与 .x 都是 var(--paper) 浅底 ——
   把亮描边画在同色底上等于隐形，而外扩的橙环又被 .sheet 的 overflow:hidden
   裁掉（.x 贴在右上角），实测橙色只剩左下两边、成了个 L 形拐角。
   浅底就用默认那条橙描边，它本来就够。 */
.lcd :focus-visible,
.deckbox :focus-visible{
  outline-color:#f5f5f5;
  box-shadow:0 0 0 4px var(--orange);
}
/* 浮层的关闭键贴着 .sheet 右上角，向外扩会被裁 —— 内缩画。 */
#lb .x:focus-visible{outline-offset:-3px}
/* 封面这类大块可聚焦区域，焦点环贴边会被 overflow 裁掉 —— 内缩画 */
.cover-zoom:focus-visible{outline-offset:-3px}
body{font-family:var(--sans); font-weight:300; color:var(--ink); background:var(--paper);
  line-height:1.5; letter-spacing:0; -webkit-font-smoothing:antialiased;
  text-rendering:optimizeLegibility; font-feature-settings:"kern" 1,"liga" 1;
  padding-bottom:calc(var(--np-h) + var(--sab)); overscroll-behavior-y:none}
a{color:inherit; text-decoration:none}
.mono{font-family:var(--mono)}
/* 左右吃 inset：横屏时刘海在侧边，纸白内容会被切掉一条。
   顶部不用管 —— .nav 已经加了 padding-top，.wrap 被它自然推下去；
   在这里再加一次会变成双倍留白。 */
.wrap{max-width:1160px; margin:0 auto;
  padding-left:calc(var(--sp-xl) + var(--sal)); padding-right:calc(var(--sp-xl) + var(--sar))}
.lc{text-transform:lowercase}

/* 顶部铭牌导航 */
/* padding-top 而不是 margin/top 位移：底色要一直铺到屏幕最上沿（刘海区也是黑的，
   与 --ink 同色，视觉上连成一体），只把【内容】推到安全区以下。
   用 margin 会在刘海区留出一条纸白，反而更难看。 */
.nav{position:sticky; top:0; z-index:1000; background:var(--ink); color:var(--white);
  border-bottom:1px solid var(--g1000); padding-top:var(--sat)}
.nav .wrap{height:clamp(52px,7vw,66px); display:flex; align-items:center; justify-content:space-between}
.brand{display:flex; align-items:center; gap:10px; font-size:var(--fs-20); font-weight:100; letter-spacing:.01em}
.brand .sq{width:14px; height:14px; background:var(--orange)}
.nav .serial{font-family:var(--mono); font-size:var(--fs-10); color:var(--g300); text-transform:uppercase;
  display:flex; gap:16px; flex-wrap:wrap; justify-content:flex-end}
.nav .serial b{color:var(--white); font-weight:400}

/* Hero */
.hero{padding:var(--sp-xl) 0 var(--sp-lg); display:flex; align-items:flex-end;
  justify-content:space-between; gap:var(--sp-lg); flex-wrap:wrap}
.hero .h-l h1{font-size:var(--fs-40); font-weight:100; line-height:1.02; letter-spacing:-.01em}
.hero .h-l .en{font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase;
  color:var(--g600); margin-top:10px; letter-spacing:.06em}
.hero .h-r{text-align:right; font-family:var(--mono); font-size:var(--fs-10); color:var(--g600);
  text-transform:uppercase; line-height:1.7}
.hero .h-r .big{display:block; font-size:var(--fs-40); font-weight:100; color:var(--ink);
  font-family:var(--sans); line-height:.9; letter-spacing:-.02em}

/* LCD 屏幕模块 */
.lcd{background:#08110c; border:1px solid var(--g1000); color:var(--green);
  font-family:var(--mono); font-size:var(--fs-15); overflow:hidden; position:relative; margin-bottom:var(--sp-md)}
.lcd .row1{display:flex; align-items:center; gap:10px; padding:9px 16px; min-height:46px; border-bottom:1px solid #12241a}
.lcd .dot{width:8px; height:8px; border-radius:50%; background:var(--green); flex:none;
  box-shadow:0 0 8px var(--green); animation:blink 1.3s steps(1) infinite}
.lcd #boot{white-space:pre; overflow:hidden; flex:1; min-width:0; text-overflow:ellipsis}
.lcd #boot .cur{animation:blink .8s steps(1) infinite}
.lcd .cat-wrap{position:relative; width:clamp(104px,15vw,156px); height:34px; flex:none; margin-left:auto;
  align-self:center}
/* 4 套姿态叠在一起，靠 opacity 切换做定格动画；整体走位靠 .cat-wrap 的 travel */
.lcd .pose{position:absolute; right:4px; bottom:0; width:42px; height:38px;
  will-change:transform,opacity; backface-visibility:hidden; -webkit-font-smoothing:none; display:block;
  image-rendering:pixelated; opacity:0; transform-origin:bottom center}
.lcd .pose .fur rect{fill:#ffffff}
.lcd .pose .fur2 rect{fill:#ffffff}
.lcd .pose .cat-eyes rect{fill:#2b2620}
.lcd .pose .glint{fill:#ffffff}
.lcd .pose .nose{fill:var(--orange)}
.lcd .pose .mouth{fill:var(--orange)}
.lcd .pose .blush{fill:var(--orange); opacity:.42}
.lcd .pose .pad rect{fill:#ffffff}
.lcd .pose .zzz rect{fill:#9c9282}
/* SVG 元素上的 transform 动画【默认不走合成器】：浏览器每帧都要重算
   fill-box 的边界 → 每帧一次 layout。实测（CDP Performance + 逐条暂停二分）：
   daily 页 1.5 秒内 91 次 layout，暂停 cat-wag 后降到 1 次 —— 一条尾巴动画
   贡献了几乎全部 layout。cat-eyes 同构，一起处理。
   加 will-change + translateZ 把它们各自提成独立合成层，transform 就只在
   合成器线程插值、不再回到主线程做布局。旁边的 .cat-move 早就这么写了，
   这两条是漏的。 */
.lcd .pose .cat-eyes{transform-box:fill-box; transform-origin:center;
  animation:cat-blink 2.2s infinite;
  will-change:transform; backface-visibility:hidden; transform:translateZ(0)}
.lcd .pose .cat-tail{transform-box:fill-box; transform-origin:0% 100%;
  animation:cat-wag .42s ease-in-out infinite alternate;
  will-change:transform; backface-visibility:hidden; transform:translateZ(0)}
/* 走位（整只猫在舞台上来回） */
.lcd .cat-move{position:absolute; inset:0; animation:cat-travel 20s cubic-bezier(.5,0,.5,1) infinite;
  will-change:transform; backface-visibility:hidden; transform:translateZ(0)}
/* travel 必须挂内层 .cat-move —— 挂 .cat-wrap 的话道具是它的子元素、会跟着猫一起平移，
   猫与饭盆间距恒定，"走过去吃饭"就永远走不到。 */
/* 9 个动作（20s 一轮，放慢到看得清每个动作）：
   ①走去饭盆 ②低头吃 ③走回 ④伸懒腰 ⑤追球左右扑 ⑥连跳 ⑦坐下舔爪 ⑧趴下打盹 ⑨起身抖毛归位 */
@keyframes cat-travel{
  0%,6%{transform:translateX(0)}         /* 呆：站着（1.2s） */
  13%,27%{transform:translateX(-64px)}   /* 走去饭盆 → 吃（吃的这段不移动） */
  33%{transform:translateX(-64px)}       /* 呆：吃完抬头（1.2s，原地） */
  38%,47%{transform:translateX(-28px)}   /* 走回来 → 伸懒腰（伸的这段不移动） */
  53%{transform:translateX(-28px)}       /* 呆：伸完站定（1.2s，原地） */
  57%{transform:translateX(14px)}        /* 追球：右扑 */
  60%{transform:translateX(-18px)}       /*       左扑 */
  62%{transform:translateX(6px)}         /*       右扑 */
  64%,76%{transform:translateX(-4px)}    /* 呆 → 坐下舔爪（原地） */
  93%{transform:translateX(-4px)}        /* 趴睡（整段原地） */
  97%,100%{transform:translateX(0)}}     /* 起身抖毛归位 + 呆 */
/* 姿态时间轴（5 套姿态切换支撑 9 个动作） */
.lcd .p-stand{animation:pose-stand 20s steps(1) infinite, cat-bob .58s ease-in-out infinite}
.lcd .p-sit{animation:pose-sit 20s steps(1) infinite, cat-eat 20s ease-in-out infinite}
.lcd .p-stretch{animation:pose-stretch 20s steps(1) infinite, cat-stretch 20s ease-in-out infinite}
.lcd .p-lick{animation:pose-lick 20s steps(1) infinite, cat-lick 20s ease-in-out infinite}
.lcd .p-sleep{animation:pose-sleep 20s steps(1) infinite, cat-sleep 20s ease-in-out infinite}
@keyframes pose-stand{0%{opacity:1}13%{opacity:0}27%{opacity:1}38%{opacity:0}
  47%{opacity:1}64%{opacity:0}93%{opacity:1}100%{opacity:1}}
@keyframes pose-sit{0%{opacity:0}13%{opacity:1}27%{opacity:0}100%{opacity:0}}
@keyframes pose-stretch{0%{opacity:0}38%{opacity:1}47%{opacity:0}100%{opacity:0}}
@keyframes pose-lick{0%{opacity:0}64%{opacity:1}76%{opacity:0}100%{opacity:0}}
@keyframes pose-sleep{0%{opacity:0}76%{opacity:1}93%{opacity:0}100%{opacity:0}}
/* 各动作细节 */
@keyframes cat-bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-1.5px)}}
@keyframes cat-eat{0%,15%{transform:translateY(0) rotate(0)}
  17%{transform:translateY(3px) rotate(5deg)}19%{transform:translateY(0) rotate(3deg)}
  21%{transform:translateY(3px) rotate(5deg)}23%{transform:translateY(0) rotate(3deg)}
  25%{transform:translateY(3px) rotate(5deg)}27%,100%{transform:translateY(0) rotate(0)}}
@keyframes cat-stretch{0%,39%{transform:scaleX(1)}41.5%{transform:scaleX(1.22) translateX(-4px)}
  44.5%{transform:scaleX(1.22) translateX(-4px)}47%,100%{transform:scaleX(1)}}
@keyframes cat-lick{0%,66%{transform:rotate(0)}68.5%{transform:rotate(-12deg)}70%{transform:rotate(-3deg)}
  71.5%{transform:rotate(-12deg)}73%{transform:rotate(-3deg)}74%,100%{transform:rotate(0)}}
@keyframes cat-sleep{0%,78%{transform:translateY(0)}
  81%{transform:translateY(3px)}84%{transform:translateY(2px)}
  87%{transform:translateY(3px)}90%{transform:translateY(2px)}92%,100%{transform:translateY(0)}}
/* ⑥ 连跳（叠在 stand 上） */
.lcd .p-stand{animation:pose-stand 20s steps(1) infinite, cat-bob .58s ease-in-out infinite,
  cat-hop 20s ease-in-out infinite}
@keyframes cat-hop{0%,56%{transform:translateY(0)}
  58%{transform:translateY(-9px) scaleY(1.1)}60%{transform:translateY(0) scaleY(.93)}
  61.5%{transform:translateY(-6px) scaleY(1.06)}63%,93%{transform:translateY(0) scale(1)}
  /* 起身抖毛，抖完留一段站定（呆） */
  95%{transform:rotate(6deg)}96.5%{transform:rotate(-5deg)}98%{transform:rotate(3deg)}
  99%,100%{transform:none}}
@keyframes cat-blink{0%,90%,100%{transform:scaleY(1)}95%{transform:scaleY(.1)}}
@keyframes cat-wag{from{transform:rotate(-26deg)}to{transform:rotate(22deg)}}
/* 道具：饭盆(吃饭期) / 球(追球期被扑得乱弹) */
.lcd .prop{position:absolute; bottom:1px; image-rendering:pixelated; opacity:0}
.lcd .prop.bowl{left:6px; width:17px} .lcd .prop.bowl svg{display:block; width:17px}
.lcd .prop.ball{right:0; width:10px} .lcd .prop.ball svg{display:block; width:10px}
.lcd .prop.bowl{animation:prop-bowl 20s ease-in-out infinite}
.lcd .prop.ball{animation:prop-ball 20s ease-in-out infinite}
.lcd .prop.bowl rect{fill:#e9e9e9} .lcd .prop.bowl .food{fill:#b9b9b9}
.lcd .prop.ball rect{fill:#f2f2f2} .lcd .prop.ball .hl{fill:#c8c8c8}
@keyframes cat-breathe{50%{transform:scaleY(1.03)}}
@keyframes prop-bowl{0%{opacity:0}8%,31%{opacity:1}34%,100%{opacity:0}}
@keyframes prop-ball{
  0%,52%{opacity:0; transform:translate(0,0)}
  54%{opacity:1; transform:translate(0,0)}
  57%{opacity:1; transform:translate(-20px,-12px)}
  59%{opacity:1; transform:translate(5px,0)}
  61%{opacity:1; transform:translate(-14px,-9px)}
  62.5%{opacity:1; transform:translate(3px,0)}
  64%{opacity:.7; transform:translate(-6px,-4px)}
  66%,100%{opacity:0; transform:translate(0,0)}}
.lcd .ticker{padding:8px 0; position:relative; -webkit-mask-image:linear-gradient(90deg,transparent,#000 4%,#000 96%,transparent);
  mask-image:linear-gradient(90deg,transparent,#000 4%,#000 96%,transparent)}
.lcd .track{display:inline-block; white-space:nowrap; padding-left:100%; color:#3fae6f;
  animation:marquee 26s linear infinite}
.lcd:hover .track{animation-play-state:paused}
.lcd .track b{color:var(--green); font-weight:700}
.lcd .track i{color:#1f6b42; font-style:normal; margin:0 14px}
@keyframes blink{50%{opacity:.2}}
@keyframes marquee{to{transform:translateX(-50%)}}

/* 规格条 */
.spec{border:1px solid var(--g300); font-family:var(--mono);
  font-size:var(--fs-10); text-transform:uppercase; color:var(--g600);
  /* 前三格是短单值，genres 是 6 个流派的长串，给它更宽的列：
     等分下它要折 5 行、把整条撑到 127px；给 2fr 后 2 行就排完，另外三格不再空一大片。
     不用省略号——这一格本来就是给人看全流派构成的。 */
  display:grid; grid-template-columns:1fr 1fr 1fr 2.2fr; align-items:stretch}
/* 各格：内容顶部对齐 + 同一行高，四格自然等高等齐；genres 长串照常折行，
   折出来的行也和其它格共用同一条基线网格（line-height 一致）。 */
.spec div{padding:10px 14px; border-right:1px solid var(--g100); min-width:0;
  display:flex; align-items:flex-start; gap:7px; line-height:1.65}
.spec div:last-child{border-right:none}
.spec b{color:var(--ink); font-weight:700; letter-spacing:.02em; min-width:0;
  /* genres 要看完整，不截断 —— 这一格本来就是给人看全流派构成的 */
  overflow-wrap:anywhere}

/* 分区标题 */
.sect{font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase; letter-spacing:.14em;
  color:var(--ink); margin:var(--sp-lg) 0 var(--sp-sm); display:flex; align-items:center; gap:12px}
.sect::after{content:""; flex:1; height:1px; background:var(--ink)}

/* 工程方格纸模块网格 */
.grid{display:grid; grid-template-columns:repeat(2,1fr);
  border-top:1px solid var(--g300); border-left:1px solid var(--g300)}
.mod{border-right:1px solid var(--g300); border-bottom:1px solid var(--g300);
  background:var(--paper); display:flex; flex-direction:column; position:relative}
.anim .mod{opacity:0; transform:translateY(8px); transition:opacity .4s ease-out, transform .4s ease-out}
.anim .mod.in{opacity:1; transform:none}
.mod.fill{background:
  repeating-linear-gradient(0deg,transparent,transparent 21px,var(--g100) 21px,var(--g100) 22px),
  repeating-linear-gradient(90deg,transparent,transparent 21px,var(--g100) 21px,var(--g100) 22px)}
.m-top{display:flex; align-items:center; justify-content:space-between; padding:10px 14px;
  border-bottom:1px solid var(--g100)}
.m-num{font-family:var(--mono); font-size:var(--fs-25); font-weight:400; line-height:1; letter-spacing:-.02em}
.m-code{display:inline-flex; align-items:center; gap:6px; font-family:var(--mono); font-size:var(--fs-10);
  text-transform:uppercase; color:var(--white); padding:3px 8px}
.m-main{display:flex; gap:var(--sp-md); padding:var(--sp-md) var(--sp-md) 0}
.art{position:relative; width:clamp(84px,9vw,104px); aspect-ratio:1; flex:none; align-self:flex-start}
.art>button.cover-zoom{display:block; width:100%; height:100%; border:0; padding:0; background:transparent; cursor:pointer; color:inherit}
.cover{width:100%; height:100%; object-fit:cover; display:block; background:var(--g100);
  border:1px solid var(--g100); transition:opacity .2s}
.cover.ph{display:grid; place-items:center; font-family:var(--mono); font-size:var(--fs-30);
  color:var(--white); background:var(--ink); border:none}
.art:hover .cover{opacity:.82}
.pbtn{position:absolute; left:4px; bottom:4px; width:40px; height:40px; display:grid; place-items:center;
  background:var(--ink); color:var(--white); border:none; padding:0; cursor:pointer; opacity:.9;
  transition:transform .15s, opacity .2s, background .2s}
.pbtn:hover{opacity:1}
.pbtn:active{transform:scale(.9)}
.pbtn svg{width:11px; height:11px; fill:var(--white); display:block}
.pbtn .i-pause{display:none}
.pbtn.playing{background:var(--green-d); opacity:1}
/* 试听失效：给出可见的「不可用」态，而不是让它看起来还能点 */
.pbtn.dead{background:var(--g300); opacity:.55; cursor:not-allowed}
.pbtn.dead svg{fill:var(--g600)}
.pbtn.dead::after{content:"×"; position:absolute; font-size:13px; line-height:1;
  color:var(--white); font-family:var(--mono)}
.pbtn.dead .i-play,.pbtn.dead .i-pause{display:none}
.pbtn.playing .i-play{display:none}
.pbtn.playing .i-pause{display:block}
/* 底部 now-playing 条：封面键触发后浮现，显当前曲/进度/播放暂停，与封面键联动 */
/* height 保持 76px（内容区不变），额外用 padding-bottom 吃掉 home 条，
   box-sizing:border-box 下总高变成 76+sab、内容仍居中在上面那 76px 里。
   左右也吃 inset：横屏时刘海会在侧边。 */
#np{position:fixed; left:0; right:0; bottom:0; z-index:1200; display:none; align-items:center; gap:clamp(8px,1.2vw,14px);
  background:var(--ink); color:var(--white); border-top:1px solid var(--g1000);
  height:calc(var(--np-h) + var(--sab)); padding:0 clamp(16px,4vw,52px) var(--sab);
  padding-left:calc(clamp(16px,4vw,52px) + var(--sal));
  padding-right:calc(clamp(16px,4vw,52px) + var(--sar))}
#np.on{display:flex}
#np-cover{width:52px; height:52px; flex:none; object-fit:cover; background:var(--g1000)}
#np-meta{flex:none; width:clamp(110px,20vw,240px); min-width:0}
#np-title{font-size:var(--fs-15); font-weight:300; white-space:nowrap; overflow:hidden; text-overflow:ellipsis}
#np-artist{font-family:var(--mono); font-size:var(--fs-10); color:var(--g300); text-transform:uppercase;
  letter-spacing:.09em; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-top:3px}
.np-btn{width:34px; height:34px; flex:none; display:grid; place-items:center; cursor:pointer;
  background:var(--green-d); color:var(--white); border:none; transition:transform .15s}
.np-btn:active{transform:scale(.9)}
.np-btn svg{width:13px; height:13px; fill:var(--white); display:block}
.np-btn .i-pause{display:none}
#np.playing .np-btn .i-play{display:none}
#np.playing .np-btn .i-pause{display:block}
#np-bar{flex:1; min-width:40px; height:4px; background:var(--g1000); position:relative; cursor:pointer}
#np-fill{position:absolute; left:0; top:0; bottom:0; width:0; background:var(--green)}
#np-time{flex:none; min-width:82px; text-align:right; font-family:var(--mono); font-size:var(--fs-10); color:var(--g300)}
@media(max-width:720px){#np-meta{width:clamp(90px,32vw,160px)} #np-time{display:none}}
#np-prev,#np-next{width:30px; height:30px} #np-prev svg,#np-next svg{width:12px; height:10px}
.heart{background:none; border:none; padding:0; margin-left:4px; width:44px; height:40px; flex:none; cursor:pointer; line-height:0}
.heart svg{width:18px; height:18px; fill:var(--g300); transition:fill .15s, transform .15s}
.heart:hover svg{fill:var(--g600)}
.heart.on svg{fill:var(--red)}
.heart:active svg{transform:scale(.85)}
.tools{display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-top:var(--sp-md)}
.tbtn{font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase; padding:8px 12px; cursor:pointer;
  border:1px solid var(--ink); background:var(--paper); color:var(--ink); display:inline-flex; align-items:center; gap:6px; transition:opacity .2s}
.tbtn:hover{opacity:.7}
.tbtn.active{background:var(--ink); color:var(--white)}
.tbtn.line{background:transparent}
.mod.hidden{display:none}
.arc{border-top:1px solid var(--g300); border-left:1px solid var(--g300); margin-top:var(--sp-md)}
.arc a{display:flex; align-items:baseline; gap:var(--sp-md); padding:14px 16px;
  border-right:1px solid var(--g300); border-bottom:1px solid var(--g300); transition:background .15s}
.arc a:hover{background:var(--white)}
.arc .d{font-family:var(--mono); font-size:var(--fs-15); color:var(--ink); flex:none; width:110px}
.arc .no{font-family:var(--mono); font-size:var(--fs-10); color:var(--g600); flex:none}
.arc .t{font-size:var(--fs-15); font-weight:300; color:var(--g900); min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap}
.hd{flex:1; min-width:0}
.title{font-size:var(--fs-25); font-weight:300; line-height:1.25; letter-spacing:-.01em; overflow-wrap:anywhere}
.artist{font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase; color:var(--g900);
  margin-top:5px; letter-spacing:.09em}
.meta{font-family:var(--mono); font-size:var(--fs-10); color:var(--g600); margin-top:7px; line-height:1.6}
.bpm{display:inline-block; margin-left:8px; padding:1px 6px 1px 5px; border:1px solid var(--g200);
  border-left:3px solid var(--bc,var(--g300)); color:var(--g900); letter-spacing:.04em; white-space:nowrap}
.tags{display:flex; flex-wrap:wrap; gap:5px; margin-top:8px}
.tag{font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase; padding:2px 7px;
  background:var(--g100); color:var(--g900)}
.body{padding:var(--sp-md); display:flex; flex-direction:column; flex:1}
.one{font-family:var(--mono); font-size:var(--fs-10); color:var(--g600); line-height:1.65; margin-bottom:7px}
.why{font-size:var(--fs-15); font-weight:300; line-height:1.7}
.scene{font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase; color:var(--g900);
  margin-top:auto; padding-top:11px}
.scene .k{color:var(--orange)}
.links{display:flex; gap:7px; margin-top:11px; flex-wrap:wrap}
.btn{font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase; padding:8px 12px;
  cursor:pointer; transition:opacity .2s; border:1px solid var(--ink)}
.btn.solid{background:var(--ink); color:var(--white)}
.btn.line{background:transparent; color:var(--ink)}
.btn:hover{opacity:.7}
.src{font-family:var(--mono); font-size:var(--fs-10); color:var(--g500); margin-top:10px; letter-spacing:.02em}
.src a{border-bottom:1px solid var(--g300)}

/* 导出面板 */
.export{border:1px solid var(--g300); margin-top:var(--sp-lg); background:var(--white)}
/* 只看收藏时，整期的网易云导入块和当前视图矛盾，隐去；#fav-box 是收藏导出，要留 */
body.fav-mode .export:not(#fav-box){display:none}
.export .h{display:flex; justify-content:space-between; align-items:center; padding:12px 16px;
  border-bottom:1px solid var(--g100); font-family:var(--mono); font-size:var(--fs-10);
  text-transform:uppercase; letter-spacing:.04em}
.export .h span{color:var(--g600)}
.export .in{padding:var(--sp-md)}
.export p{font-family:var(--mono); font-size:var(--fs-10); color:var(--g600); margin-bottom:10px; text-transform:none}
.export pre{border:1px solid var(--g100); background:var(--paper); padding:14px; font-family:var(--mono);
  font-size:var(--fs-10); line-height:1.8; white-space:pre-wrap; max-height:280px; overflow:auto}

footer{display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px; margin-top:var(--sp-lg);
  padding:var(--sp-lg) 0; font-family:var(--mono); font-size:var(--fs-10); text-transform:uppercase;
  color:var(--g600); border-top:1px solid var(--g300)}

@media(max-width:720px){
  .grid{grid-template-columns:1fr}
  .hero{align-items:flex-start}
  .m-main{flex-direction:row}
  .spec{grid-template-columns:repeat(2,1fr)}
  .spec div:nth-child(2n){border-right:none}
  .spec div:nth-child(-n+2){border-bottom:1px solid var(--g100)}
}

/* ── 竖屏（手机）适配：以 iPhone 390×844 为基准 ──
   问题都是实测出来的，不是猜的：①logo「MUSIC DAILY」被折成两行
   ②顶栏右侧 serial 三段挤成两排 ③规格条四列在 390 下每格都折行、genres 那格压成竖带
   ④大数字与右侧说明断开 ⑤卡片内封面+文字并排太挤 */
@media(max-width:520px){
  /* 覆盖 padding-inline 会整条替换掉基础规则里的 calc()，丢掉左右安全区。
     ≤520px 正是手机 —— 最需要安全区的那批设备（竖屏 left/right inset 为 0 所以
     当前无感，横屏窄设备与未来机型会中）。 */
  .wrap{padding-left:calc(16px + var(--sal)); padding-right:calc(16px + var(--sar))}
  /* 顶栏：logo 不许折行，右侧信息只留最要紧的两段 */
  .nav .wrap{height:52px}
  .brand{font-size:14px; gap:8px; white-space:nowrap; flex:none}
  .brand .sq{width:11px; height:11px}
  .nav .serial{gap:10px; flex-wrap:nowrap; font-size:9px; overflow:hidden}
  .nav .serial>*:nth-child(n+3){display:none}   /* 只留前两段，别挤成两排 */
  /* Hero：大数字与说明并成一行，别各占一块 */
  .hero{padding:20px 0 14px; gap:12px; align-items:flex-end}
  .hero .h-l h1{font-size:34px}
  .hero .h-l .en{margin-top:7px; font-size:9px; letter-spacing:.04em}
  .hero .h-r{line-height:1.5; font-size:9px}
  .hero .h-r .big{font-size:30px; display:inline-block; margin-right:6px}
  /* 竖屏：390px 放四列每格都折行，改两列（保持原样式，只是换行数） */
  .spec{grid-template-columns:repeat(2,1fr)}
  .spec div{padding:8px 12px}
  .spec div:nth-child(2n){border-right:none}
  .spec div:nth-child(-n+2){border-bottom:1px solid var(--g100)}
  /* 工具按钮：一行放不下就整行铺满，别半截换行 */
  .tools{gap:7px}
  .tools .tbtn{flex:1 1 calc(50% - 4px); justify-content:center; padding:9px 8px; font-size:10px}
  /* 卡片：封面与文字改上下叠，封面横铺（竖屏并排 130px 封面太憋） */
  .m-main{flex-direction:row; gap:12px; padding:12px 12px 0}
  .m-main .art{width:88px; aspect-ratio:1}
  .m-top{padding:4px 8px 4px 12px}
  .body{padding:12px}
  /* LCD：猫和跑马灯在窄屏共存，缩小猫舞台 */
  .lcd .row1{min-height:40px; padding:7px 12px; gap:7px}
  .lcd .cat-wrap{transform:scale(.85); transform-origin:center bottom}
  footer{flex-direction:column; gap:6px; text-align:center}
}
/* 原有铭牌、网格与色盘内的操作细节。 */
button,input,select,a{-webkit-tap-highlight-color:transparent; touch-action:manipulation}
button,input,select{font:inherit}
.nav .wrap{gap:16px}
.nav .site-links{display:flex; gap:18px; margin-left:auto; flex:none; font:12px var(--mono)}
.nav .site-links a{display:flex; align-items:center; min-height:44px; border-bottom:2px solid transparent; color:var(--g200)}
.nav .site-links a:hover,.nav .site-links a[aria-current=page]{color:var(--white); border-bottom-color:var(--orange)}
.nav .nav-meta{font-size:10px; flex:none}
.daily-page .hero{padding-top:clamp(22px,3vw,36px)}
.daily-page .m-top{padding-block:4px}
.daily-page .grid{grid-template-columns:repeat(2,minmax(0,1fr))}
.daily-page .one{color:#666; line-height:1.75}
.daily-page .src{color:var(--g600)}
.daily-page .tools .tbtn,.daily-page .links .btn{min-height:40px; display:inline-flex; align-items:center; justify-content:center}
.track-search{display:flex; flex:1 1 210px; align-items:center; gap:8px; border:1px solid var(--g300); padding:0 10px; min-height:40px}
.track-search span{font:11px var(--mono); color:var(--g600); flex:none}
.track-search input{min-width:0; width:100%; border:0; border-radius:0; background:transparent; color:var(--ink); font-size:14px; padding:8px 0}
.track-search:focus-within{outline:2px solid var(--orange); outline-offset:1px}
.track-search input:focus-visible{outline:none}
.filter-note{font:11px var(--mono); color:var(--g600); margin-top:10px; min-height:17px}
.empty-list{padding:24px 16px; border:1px solid var(--g300); text-align:center; font-size:14px}
.empty-list button{margin-top:12px}
.daily-page #np{gap:10px}
.daily-page .np-btn,.daily-page #np-prev,.daily-page #np-next{width:44px; height:44px}
.daily-page #np-meta{width:clamp(110px,20vw,240px)}
#np-seek{flex:1; min-width:60px; width:100%; height:28px; accent-color:var(--green); cursor:pointer}
.daily-page #np[aria-busy=true] #np-toggle{background:var(--g900)}
.daily-page .pbtn.loading{background:var(--g900)}
.daily-page .pbtn.loading::after{content:'…'; position:absolute; inset:0; display:grid; place-items:center; font-size:20px}
.daily-page .pbtn.loading svg{visibility:hidden}
.daily-page .export,.mod{scroll-margin-top:84px}
.arc a{min-height:64px}
.archive-page{padding-bottom:var(--sab)}
@media(max-width:900px){.nav .nav-meta{display:none}}
@media(max-width:720px){
  .daily-page .grid{grid-template-columns:1fr}
  .daily-page #np{height:calc(92px + var(--sab)); padding:8px calc(12px + var(--sar)) calc(28px + var(--sab)) calc(12px + var(--sal)); gap:6px}
  .daily-page{--np-h:92px}
  .daily-page #np-cover{width:40px; height:40px}
  .daily-page #np-meta{flex:1; width:auto}
  .daily-page #np-artist{letter-spacing:.02em}
  #np-seek{position:absolute; bottom:var(--sab); left:calc(12px + var(--sal)); width:calc(100% - 24px - var(--sal) - var(--sar)); margin:0; height:28px}
  .arc a{display:grid; grid-template-columns:1fr auto; gap:4px 12px; padding:12px}
  .arc .t{grid-column:1 / -1; white-space:normal; font-size:13px; line-height:1.6}
}
@media(max-width:520px){
  .nav .wrap{gap:8px}
  .nav .site-links{gap:10px; font-size:11px}
  .daily-page .hero{display:grid; grid-template-columns:minmax(0,1fr) auto; gap:10px; padding:20px 0 14px}
  .daily-page .hero .h-l h1{font-size:32px}
  .daily-page .hero .h-l .en{max-width:190px; font-size:10px; line-height:1.6}
  .daily-page .hero .h-r{font-size:10px}
  .daily-page .hero .h-r .big{display:block; margin:0 0 4px; font-size:32px}
  .daily-page .spec{grid-template-columns:1fr 1fr 1fr}
  .daily-page .spec div{padding:7px 9px; font-size:10px; flex-wrap:wrap; gap:0 5px; border-right:1px solid var(--g100); border-bottom:1px solid var(--g100)}
  .daily-page .spec div:nth-child(3){border-right:0}
  .daily-page .spec div:last-child{grid-column:1 / -1; border:0}
  .daily-page .tools{gap:6px}
  .daily-page .track-search{flex-basis:100%; min-height:44px}
  .daily-page .track-search input{font-size:16px}
  .daily-page .tools .tbtn{flex:1 1 auto; min-height:44px; font-size:11px}
  .daily-page .links .btn{flex:1; min-height:44px; padding:8px}
  .daily-page .title{font-size:21px}
  .daily-page .meta{line-height:1.65; overflow-wrap:anywhere}
  .daily-page .tags{gap:4px}
  .daily-page .tag{font-size:10px; padding:2px 5px}
  .daily-page .m-main .art{width:88px}
  .daily-page .m-code{max-width:210px; font-size:10px}
  .daily-page .export .h{align-items:flex-start; flex-direction:column; gap:4px}
}
@media(prefers-reduced-motion:reduce){
  .anim .mod,.anim .mod.in{opacity:1; transform:none; transition:none}
  .track,.dot,.rec,.pose,.p-sleep,.cat-wrap,.cat-move,.cat-eyes,.cat-tail,.prop{animation:none}
  .pose{opacity:0}
  .p-stand{opacity:1}
  html{scroll-behavior:auto}
}
"""

JS = Path(__file__).with_name("daily_interactions.js").read_text(encoding="utf-8")


def _esc(s) -> str:
    return html.escape(str(s or ""))


def _ncsearch(track: dict) -> str:
    q = urllib.parse.quote(f"{track['title']} {track['artist']}")
    return f"https://music.163.com/#/search/m/?s={q}"


def _spsearch(track: dict) -> str:
    q = urllib.parse.quote(f"{track['title']} {track['artist']}")
    return f"https://open.spotify.com/search/{q}"


# 展示层 tag 归一。mood 的受控词表 SSOT 在 scripts/mood_vocab.py（32 个英文词），
# 这里只做「历史写法 → 受控词」的转发，不再自己维护一份同义词表（那会和词表漂移）。
# genres 已在 pool 里归一为小写，CSS 负责转大写显示。
from lightbox import LIGHTBOX_CSS, LIGHTBOX_HTML, lightbox_js  # noqa: E402
from netease_open import NETEASE_OPEN_JS  # noqa: E402
from mood_vocab import ALIASES as _MOOD_ALIASES  # noqa: E402

TAG_MAP = dict(_MOOD_ALIASES)


def _tag(x: str) -> str:
    """展示用 tag：归一到受控英文词；表外的原样返回（不硬凑中文）。"""
    x = str(x or "").strip()
    return TAG_MAP.get(x, TAG_MAP.get(x.lower(), x))


# BPM 速度分档 → 站内配色（慢蓝 / 中绿 / 偏快黄 / 快橙），按区间中点判定
BPM_TIERS = ((85, "slow", "#0071bb"), (105, "mid", "#006837"),
             (125, "up", "#fab413"), (10 ** 9, "fast", "#f05a24"))


def _bpm_mid(track: dict) -> float:
    ns = re.findall(r"\d+", str(track.get("bpm_band", "")))
    return (int(ns[0]) + int(ns[-1])) / 2 if ns else 0.0


def _bpm(track: dict) -> tuple[str, str]:
    """返回 ('70–120 bpm', 颜色)；缺失返回 ('', '')。颜色按速度分四档。"""
    b = str(track.get("bpm_band", "")).strip()
    if not b:
        return "", ""
    mid = _bpm_mid(track)
    for lim, _name, color in BPM_TIERS:
        if mid < lim:
            return f"{b} bpm", color
    return f"{b} bpm", BPM_TIERS[-1][2]


ARTIST_CTX: dict[str, dict] = {}   # {artist: {bio, years, inpool}}，由 build_daily 注入


def _lb_data(track: dict, artist_ctx: dict | None = None) -> str:
    """浮层要用的 data-*，挂在封面容器上（点封面任意处都能开，不只是图片本身）。

    artist_ctx：该艺人的上下文 {bio, years, inpool}。浮层以音乐人为主体，
    所以 bio 是正文；曲目自身的 why/scene 降级成次要块。
    """
    bpm, _c = _bpm(track)
    # genres 原样，mood_tags 过 _tag（别名归一）—— 混在一起过 _tag 会把
    # 「organic electronic」这个流派改写成 mood 词「organic」，还会与真的
    # organic mood 撞成重复 chip。实测 68 个 chip 被改写、21 首出现重复。
    tags = "|".join(list(track.get("genres") or [])[:3]
                    + [_tag(x) for x in list(track.get("mood_tags") or [])[:3]])
    ctx = artist_ctx or {}
    g0 = (track.get("genres") or [""])[0]
    return (f' data-cover="{_esc(track.get("_cover") or track.get("artwork") or "")}"'
            f' data-title="{_esc(track.get("title", ""))}"'
            f' data-artist="{_esc(track.get("artist", ""))}"'
            f' data-year="{_esc(str(track.get("year", "")))}"'
            f' data-years="{_esc(ctx.get("years", ""))}"'
            f' data-g0="{_esc(g0)}"'
            f' data-album="{_esc(track.get("album", ""))}"'
            f' data-bpm="{_esc(bpm)}" data-tags="{_esc(tags)}"'
            f' data-bio="{_esc(ctx.get("bio", ""))}"'
            f' data-inpool="{_esc("|".join(ctx.get("inpool", [])))}"'
            f' data-one="{_esc(track.get("artist_oneliner", ""))}"'
            f' data-why="{_esc(track.get("why", ""))}"'
            f' data-scene="{_esc(track.get("scene", ""))}"'
            f' data-apple="{_esc(track.get("_apple") or "")}"'
            f' data-spotify="{_esc(_spsearch(track))}"')


def _art(track: dict) -> str:
    art = track.get("_cover") or track.get("artwork") or ""
    if art:
        cover = f'<img class="cover" src="{_esc(art)}" alt="" loading="lazy">'
    else:
        cover = f'<div class="cover ph">{_esc((track.get("artist") or "?")[:1].upper())}</div>'
    prev = track.get("_preview") or ""
    pbtn = (f'<button class="pbtn" type="button" data-src="{_esc(prev)}" '
            f'data-cover="{_esc(art)}" data-title="{_esc(track.get("title",""))}" '
            f'data-artist="{_esc(track.get("artist",""))}" aria-label="试听 30 秒">'
            f'{ICON_PLAY}{ICON_PAUSE}</button>') if prev else ""
    return (f'<div class="art"><button class="cover-zoom" type="button"'
            f' aria-label="查看 {_esc(track.get("title", ""))} 详情"{_lb_data(track, ARTIST_CTX.get(track.get("artist", "")))}>'
            f'{cover}</button>{pbtn}</div>')


def _mod(track: dict, idx: int) -> str:
    g0 = (track.get("genres") or ["—"])[0]
    # 同上：genre chip 原样输出，不过 mood 别名表
    tags = "".join(f'<span class="tag">{_esc(g)}</span>'
                   for g in (track.get("genres") or [])[1:3])
    tags += "".join(f'<span class="tag">{_esc(_tag(m))}</span>' for m in (track.get("mood_tags") or [])[:2])
    links = []
    if track.get("_apple"):
        links.append(f'<a class="btn solid" href="{_esc(track["_apple"])}" target="_blank" rel="noopener">listen</a>')
    links.append(f'<a class="btn line" href="{_spsearch(track)}" target="_blank" rel="noopener">spotify ↗</a>')
    # data-nc 交给 netease_open.js 唤起本机 App；href 保留为无 JS 时的降级
    _ncq = f'{track.get("title", "")} {track.get("artist", "")}'.strip()
    links.append(f'<a class="btn line" href="{_ncsearch(track)}" target="_blank" rel="noopener"'
                 f' data-nc="{_esc(_ncq)}">netease ♫</a>')
    src = ""
    if track.get("source"):
        s = _esc(track["source"])
        src = (f'<a href="{_esc(track["source_url"])}" target="_blank" rel="noopener">{s}</a>'
               if track.get("source_url") else s)
    meta = " / ".join(x for x in [_esc(track.get("year", "")), _esc(track.get("album", ""))] if x)
    bpm, bpm_c = _bpm(track)
    key = f"{track['title']} - {track['artist']}"
    return f"""
    <article class="mod" data-k="{_esc(key)}">
      <div class="m-top">
        <span class="m-num">{idx:02d}</span>
        <span style="display:flex; align-items:center">
          <span class="m-code" style="background:{_knob(g0)}">{_esc(g0)}</span>
          <button class="heart" type="button" data-k="{_esc(key)}" aria-label="收藏 {_esc(track['title'])}" aria-pressed="false">{ICON_HEART}</button>
        </span>
      </div>
      <div class="m-main">
        {_art(track)}
        <div class="hd">
          <div class="title lc">{_esc(track['title'])}</div>
          <div class="artist">{_esc(track['artist'])}</div>
          <div class="meta">{meta}{f'<span class="bpm" style="--bc:{bpm_c}">{_esc(bpm)}</span>' if bpm else ''}</div>
          <div class="tags">{tags}</div>
        </div>
      </div>
      <div class="body">
        <div class="one">{_esc(track.get('artist_oneliner',''))}</div>
        <div class="why">{_esc(track.get('why',''))}</div>
        {('<div class="scene"><span class="k">use ▸</span> ' + _esc(track['scene']) + '</div>') if track.get('scene') else ''}<div class="links">{''.join(links)}</div>
        <div class="src">src · {src}</div>
      </div>
    </article>"""


def build_html(date_str: str, tracks: list[dict], issue_no: int, netease_text: str,
               archive_href: str = "archive/index.html", random_href: str = "random.html",
               prev_date: str = "", next_date: str = "") -> str:
    """prev_date / next_date：相邻两期的日期（空串 = 没有）。

    只有 archive 页会传 —— 首页 daily.html 永远是最新一期，它的「下一期」不存在，
    而「上一期」要跳到 archive/ 子目录，链接前缀不同。分开处理比在模板里
    塞条件判断清楚。
    """
    mods = "\n".join(_mod(t, i) for i, t in enumerate(tracks, 1))
    if len(tracks) % 2 == 1:  # 补一格方格纸填充，让网格成完整矩形
        mods += '\n<div class="mod fill"></div>'
    nc = _esc(netease_text)
    js = JS
    n = len(tracks)
    pending = sum(t.get("selection_status") == "discovery_not_curated" for t in tracks)
    heading = "今日新发现" if pending == n and n else ("今日推荐" if pending else "今日精选")
    edition_note = f"本期 {pending} 首新发现 · 资料已核对，听感待精选" if pending else "today's selection · daily music report"
    ymd = date_str.replace("-", ".")

    # ── Open Graph 的四个值 ──────────────────────────────────
    # 标题带上期号与日期，摘要用前三首「曲名 — 艺人」——比一句固定标语
    # 有信息量得多：分享出去的人和看到的人都能立刻知道这期有什么。
    _first3 = "、".join(f"{t.get('title','')} — {t.get('artist','')}"
                       for t in tracks[:3] if t.get("title"))
    og_title = f"MUSIC DAILY · 第 {issue_no:03d} 期 · {ymd}"
    og_desc = (f"今日 {n} 首：{_first3}…" if _first3
               else "每日精选 30 首 · melody-first · mood-first · production-first")
    # 往期页在 archive/ 子目录下，URL 要带上；archive_href 指回上一级即说明身处子目录
    og_url = (SITE_URL + f"archive/{date_str}.html"
              if archive_href.startswith("index") else SITE_URL)
    # 首图取当期第一张真实封面；没有就退回站点图标（空 og:image 会让抓取端乱抓图）
    og_img = next((t.get("_cover") for t in tracks if t.get("_cover")), "") \
        or (SITE_URL + "icon-512.png")

    # 上一期 / 下一期。看完今天想看昨天，此前得先回归档页再点 —— 多一次跳转。
    # 在 archive/ 子目录里同级跳转；首页的「上一期」要进子目录。
    _in_archive = archive_href.startswith("index")
    _pfx = "" if _in_archive else "archive/"
    nav_prev = (f'<a class="tbtn line" rel="prev" href="{_pfx}{prev_date}.html">'
                f'← 上一期</a>' if prev_date else "")
    nav_next = (f'<a class="tbtn line" rel="next" href="{_pfx}{next_date}.html">'
                f'下一期 →</a>' if next_date else "")
    genres = sorted({(t.get("genres") or ["—"])[0] for t in tracks})
    genre_line = " · ".join(_esc(g).lower() for g in genres[:6])
    ticker = "".join(
        f'<b>{i:02d}</b> {_esc(t["title"])} <i>—</i> {_esc(t["artist"])}<i>·</i>'
        for i, t in enumerate(tracks, 1)
    )
    boot = f"system ready — {n} tracks loaded · melody-first · mood-first · production-first"
    # archive/ 子页要用 ../ 才能取到根目录的 manifest 与图标。
    # 判据复用 _in_archive（archive_href=="index.html" 即身处子目录）。
    up = "../" if _in_archive else ""
    favicon = "data:image/svg+xml," + urllib.parse.quote(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<rect width="24" height="24" fill="#f05a24"/>'
        '<rect x="5" y="5" width="14" height="14" fill="none" stroke="#0f0e12" stroke-width="2"/></svg>'
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0f0e12">
<meta name="description" content="{_esc(og_desc)}">
<title>MUSIC DAILY · md-{n:02d} · {_esc(date_str)}</title>
<!-- Open Graph：发到微信 / Twitter 时带标题 + 封面 + 摘要，而不是一条裸链接。
     og:image 用当期第一首的封面（iTunes 的 https 绝对地址，零额外成本）；
     没有封面时退回站点图标，宁可用占位也别留空 —— 空 og:image 有些抓取端
     会去页面里乱抓一张图。 -->
<meta property="og:type" content="article">
<meta property="og:site_name" content="MUSIC DAILY">
<meta property="og:title" content="{_esc(og_title)}">
<meta property="og:description" content="{_esc(og_desc)}">
<meta property="og:url" content="{_esc(og_url)}">
<meta property="og:image" content="{_esc(og_img)}">
<meta property="og:locale" content="zh_CN">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{_esc(og_title)}">
<meta name="twitter:description" content="{_esc(og_desc)}">
<meta name="twitter:image" content="{_esc(og_img)}">
<link rel="icon" href="{favicon}">
<!-- PWA：加到手机主屏后有真图标、全屏无地址栏、启动闪屏。
     子目录页面用相对上级前缀取根目录的资源。
     只做 manifest 不做 Service Worker —— 这个站每天出新刊，SW 的缓存失效
     写不对就会让用户看到昨天的日报【而且他不知道】，那类静默失效的代价
     远大于「离线翻往期」的收益。 -->
<link rel="manifest" href="{up}manifest.webmanifest">
<link rel="apple-touch-icon" href="{up}icon-180.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="MD-30">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@100;300;400&family=Space+Mono:wght@400;700&family=Noto+Sans+SC:wght@100;300;400&display=swap" rel="stylesheet">
<style>{CSS}{LIGHTBOX_CSS}</style>
</head>
<body class="daily-page">
<nav class="nav">
  <div class="wrap">
    <a class="brand" href="{up}index.html" aria-label="MUSIC DAILY 首页"><span class="sq"></span>MUSIC DAILY</a>
    <div class="serial nav-meta"><span>issue <b>{issue_no:03d}</b></span><span>{ymd}</span></div>
    <div class="site-links" aria-label="页面导航"><a href="{up}daily.html" aria-current="page">今日</a><a href="{random_href}">随机</a><a href="{archive_href}">往期</a><a href="{up}legacy/{'archive/' + date_str + '.html' if _in_archive else 'daily.html'}">旧版</a></div>
  </div>
</nav>

<main class="wrap">
  <div class="hero">
    <div class="h-l">
      <h1 class="lc">{heading}</h1>
      <div class="en">{edition_note}</div>
    </div>
    <div class="h-r"><span class="big">{n:02d}</span>tracks / daily<br>{ymd}</div>
  </div>

  <div class="lcd">
    <div class="row1"><span class="dot"></span><span id="boot" data-text="{_esc(boot)}"></span><div class="cat-wrap"><div class="cat-move">{ICON_CAT}</div><span class="prop bowl">{ICON_BOWL}</span><span class="prop ball">{ICON_BALL}</span></div></div>
    <div class="ticker"><span class="track">{ticker}{ticker}</span></div>
  </div>

  <div class="spec">
    <div>sort <b>{'new discovery' if pending else 'melody-first'}</b></div><div>bpm <b>{'待核实' if pending else '70–120'}</b></div>
    <div>tracks <b>{n:02d}</b></div><div>genres <b>{genre_line or '—'}</b></div>
  </div>

  <div class="tools">
    <label class="track-search"><span>本期搜索</span><input id="track-search" type="search" placeholder="歌名、艺人、风格" autocomplete="off"></label>
    <button class="tbtn" id="fav-only" type="button" aria-pressed="false"><span id="fav-lb">♥ 只看收藏</span> <span id="fav-n">0</span></button>
    <button class="tbtn line" id="fav-export" type="button">导出收藏</button>
    <button class="tbtn line" id="share-btn" type="button" hidden>分享这期</button>
    {nav_prev}{nav_next}
  </div>
  <p class="filter-note" id="filter-note" role="status"></p>

  <div class="sect">tracklist</div>
  <div class="grid">
    {mods}
  </div>
  <div class="empty-list" id="empty-list" hidden><p id="empty-message"></p><button class="tbtn" id="filter-reset" type="button">显示本期全部</button></div>

  <section class="export">
    <div class="h">data export · 网易云导入 <span>format: title - artist</span></div>
    <div class="in">
      <p>复制下列清单 → 网易云 App「新建歌单 → 导入」，第一行会作为歌单名自动创建。</p>
      <pre id="nc-text">{nc}</pre>
      <button class="btn solid" id="nc-btn" onclick="copyNC()" style="margin-top:12px">复制歌单 / copy</button>
    </div>
  </section>

  <section class="export" id="fav-box" style="display:none">
    <div class="h">我收藏的 · 网易云导入 <span>存在此浏览器 · 跨期累计</span></div>
    <div class="in">
      <p>你在各期点 ♥ 收藏的曲目（本浏览器）。复制 → 网易云「新建歌单 → 导入」。</p>
      <pre id="fav-text"></pre>
      <button class="btn solid" id="fav-copy" onclick="copyFav()" style="margin-top:12px">复制收藏 / copy</button>
    </div>
  </section>

  <footer>
    <span>MUSIC DAILY · md-{n:02d} · issue {issue_no:03d}</span>
    <span>updated 08:00 cst</span>
    <span>cover &amp; preview via public music api · personal use</span>
  </footer>
</main>

<div id="np" role="region" aria-label="试听播放器" aria-busy="false">
  <img id="np-cover" alt="">
  <div id="np-meta" aria-live="polite"><div id="np-title" class="lc"></div><div id="np-artist"></div></div>
  <button id="np-prev" class="np-btn" type="button" aria-label="上一首">{ICON_PREV}</button>
  <button id="np-toggle" class="np-btn" type="button" aria-label="播放/暂停">{ICON_PLAY}{ICON_PAUSE}</button>
  <button id="np-next" class="np-btn" type="button" aria-label="下一首">{ICON_NEXT}</button>
  <input id="np-seek" type="range" min="0" max="100" step="0.1" value="0" aria-label="试听进度" disabled>
  <span id="np-time" class="mono">0:00 / 0:00</span>
</div>

{LIGHTBOX_HTML}
<script>{js}</script>
<script>{lightbox_js('.cover-zoom', up + 'random.html')}</script>
<script>{NETEASE_OPEN_JS}</script>
</body>
</html>"""


def build_archive_index(issues: list[dict]) -> str:
    """往期索引页（site/archive/index.html）：按日期倒序列出所有期。issues 已倒序。"""
    rows = "\n".join(
        f'<a href="{_esc(s["date"])}.html"><span class="d">{_esc(s["date"])}</span>'
        f'<span class="no">issue {int(s.get("issue_no", 0)):03d} / {int(s.get("n", 0)):02d}首</span>'
        f'<span class="t">{_esc(s.get("playlist_title", ""))}</span></a>'
        for s in issues
    )
    up = "../"          # 本页固定在 archive/ 子目录
    favicon = "data:image/svg+xml," + urllib.parse.quote(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<rect width="24" height="24" fill="#f05a24"/>'
        '<rect x="5" y="5" width="14" height="14" fill="none" stroke="#0f0e12" stroke-width="2"/></svg>')
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0f0e12">
<title>MUSIC DAILY · archive</title>
<link rel="icon" href="{favicon}">
<!-- PWA：加到手机主屏后有真图标、全屏无地址栏、启动闪屏。
     子目录页面用相对上级前缀取根目录的资源。
     只做 manifest 不做 Service Worker —— 这个站每天出新刊，SW 的缓存失效
     写不对就会让用户看到昨天的日报【而且他不知道】，那类静默失效的代价
     远大于「离线翻往期」的收益。 -->
<link rel="manifest" href="{up}manifest.webmanifest">
<link rel="apple-touch-icon" href="{up}icon-180.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="MD-30">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@100;300;400&family=Space+Mono:wght@400;700&family=Noto+Sans+SC:wght@100;300;400&display=swap" rel="stylesheet">
<style>{CSS}{LIGHTBOX_CSS}</style>
</head>
<body class="archive-page">
<nav class="nav"><div class="wrap">
  <a class="brand" href="../index.html" aria-label="MUSIC DAILY 首页"><span class="sq"></span>MUSIC DAILY</a>
  <div class="serial nav-meta"><span>共 <b>{len(issues)}</b> 期</span></div>
  <div class="site-links" aria-label="页面导航"><a href="../daily.html">今日</a><a href="../random.html">随机</a><a href="index.html" aria-current="page">往期</a><a href="../legacy/archive/index.html">旧版</a></div>
</div></nav>
<main class="wrap">
  <div class="hero"><div class="h-l"><h1 class="lc">往期</h1>
    <div class="en">archive · all issues</div></div>
    <div class="h-r"><span class="big">{len(issues):02d}</span>issues<br><a href="../daily.html" style="border-bottom:1px solid var(--g300)">← 最新一期</a></div>
  </div>
  <div class="arc">
    {rows}
  </div>
  <footer><span>MUSIC DAILY · archive</span><span>{len(issues)} issues · melody-first</span></footer>
</main>
</body>
</html>"""
