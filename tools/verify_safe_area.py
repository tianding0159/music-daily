"""验证 iOS 安全区（刘海 / home 条）不遮挡任何可交互元素。

**为什么必须注入 inset 而不是直接跑**：容器里的 chromium 没有刘海硬件，
`env(safe-area-inset-*)` 恒为 0 —— 那样跑一遍全绿，但什么都没验到
（0 遮不住任何东西）。所以注入一层 `:root` 覆盖，把四个变量顶成
iPhone 14 Pro 的真实值（顶 59px / 底 34px）。我们的 CSS 全部经由
`var(--sat)` 等消费，因此这样能真实检验"inset 非零时布局对不对"。

**两类判据，缺一不可**：
  ① 元素内容区避开安全区（顶沿 >= inset.top、底沿 >= inset.bottom）
  ② 篮子与吸底播放器不重叠 —— 篮子的风险不是"被安全区遮"而是
     "被播放器盖住"。只查 ① 会让 #basket 那条改动的回归假绿：
     硬编码 76px 照样过 ① 那一关（实测确认过）。

**踩过的两个坑**（都会让结果说谎）：
  · 量之前必须判可见：`display:none` 父容器下的元素是 0×0，
    量出来"内容顶沿 = 0"，会伪装成"被刘海压住"。
  · 撤改动做负向验证时，要撤【当前视口真正生效的那条规则】。
    393px 视口命中 max-width:560px 媒体查询，那里的 #basket 覆盖了基础规则，
    所以撤基础规则毫无效果、测试照样绿 —— 这个假绿骗过我一次。

用法：
    python3 -m http.server 8850 --directory site &
    python3 tools/verify_safe_area.py        # 退出码 0 = 全部避开
"""
import asyncio, sys
from playwright.async_api import async_playwright
P="http://localhost:8850"
OV=":root{--sat:59px !important;--sar:0px !important;--sab:34px !important;--sal:0px !important}"
INS={"top":59,"bottom":34}
async def main():
    bad=[]; ok=0
    async with async_playwright() as p:
        br=await p.chromium.launch()
        ctx=await br.new_context(viewport={"width":393,"height":852}, device_scale_factor=3, is_mobile=True, has_touch=True)
        await ctx.add_init_script("""(()=>{const c=%s;const f=()=>{const s=document.createElement('style');s.textContent=c;document.head.appendChild(s)};
          if(document.head)f();else document.addEventListener('DOMContentLoaded',f)})()""" % repr(OV))
        pg=await ctx.new_page()
        JS="""(a)=>{const [sel,INS]=a; const e=document.querySelector(sel); if(!e) return {skip:1};
            const g=e.getBoundingClientRect(); if(g.width<1||g.height<1) return {skip:1};
            const c=getComputedStyle(e);
            const ct=g.top+parseFloat(c.paddingTop||0), cb=innerHeight-(g.bottom-parseFloat(c.paddingBottom||0));
            return {ctop:Math.round(ct),cbot:Math.round(cb),okTop:ct>=INS.top-0.6,okBot:cb>=INS.bottom-0.6};}"""
        async def run(label,page,sel,setup=None):
            nonlocal ok
            await pg.goto(f"{P}/{page}", wait_until="networkidle")
            if setup: await setup()
            r=await pg.evaluate(JS,[sel,INS])
            if r.get("skip"): print(f"  {label:26} ⊘ 不可见"); return
            good=r["okTop"] and r["okBot"]
            if good: ok+=1
            else: bad.append(label)
            print(f"  {label:26} 顶={r['ctop']:4} 底={r['cbot']:4}  {'✓' if good else '✗ 被遮'}")
        await run("落地页 stage","index.html",".stage")
        await run("日报 顶栏","daily.html",".nav")
        async def a(): await pg.evaluate("()=>document.querySelector('.pbtn').click()"); await pg.wait_for_timeout(700)
        await run("日报 播放器","daily.html","#np",a)
        async def b(): await pg.locator(".cover-zoom").first.click(); await pg.wait_for_timeout(450)
        await run("日报 浮层 sheet","daily.html","#lb .sheet",b)
        await run("日报 浮层关闭键","daily.html","#lb .x",b)
        async def c():
            e=await pg.query_selector("#roll")
            if e: await e.click(); await pg.wait_for_timeout(2900)
            x=await pg.query_selector(".pbtn")
            if x: await x.click(); await pg.wait_for_timeout(700)
        await run("随机页 播放器","random.html","#np",c)
        async def d():
            e=await pg.query_selector("#roll")
            if e: await e.click(); await pg.wait_for_timeout(2900)
            h=await pg.query_selector(".heart")
            if h: await h.click(); await pg.wait_for_timeout(800)
        await run("随机页 篮子","random.html","#basket",d)

        # 篮子的真正风险【不是】被安全区遮，而是被吸底播放器盖住 ——
        # 它靠 bottom 叠在播放器上方，一旦 bottom 不跟着播放器的实际占位高度走
        # （= --np-h + 底部安全区），下沿就会插进播放器里。
        # 只查"避开安全区"会让这条改动的回归假绿：硬编码 76px 照样过安全区那关。
        await pg.goto(f"{P}/random.html", wait_until="networkidle")
        e=await pg.query_selector("#roll")
        if e: await e.click(); await pg.wait_for_timeout(2900)
        h=await pg.query_selector(".heart")
        if h: await h.click(); await pg.wait_for_timeout(800)
        x=await pg.query_selector(".pbtn")
        if x: await x.click(); await pg.wait_for_timeout(700)
        r=await pg.evaluate('''()=>{const b=document.querySelector('#basket'),n=document.querySelector('#np');
            if(!b||!n) return {skip:1};
            const gb=b.getBoundingClientRect(), gn=n.getBoundingClientRect();
            if(gb.height<1||gn.height<1) return {skip:1};
            return {overlap:Math.round(gb.bottom-gn.top)};}''')
        if r.get("skip"):
            print(f"  {'篮子 vs 播放器重叠':26} ⊘ 有一方不可见")
        else:
            good = r["overlap"] <= 0
            if good: ok+=1
            else: bad.append("篮子被播放器盖住")
            print(f"  {'篮子 vs 播放器重叠':24} {r['overlap']:4}px  {'✓ 不重叠' if good else '✗ 被盖住'}")
        await br.close()
    print(f"  → 通过 {ok} / 失败 {len(bad)}" + (f"：{bad}" if bad else ""))
    return 1 if bad else 0
sys.exit(asyncio.run(main()))
