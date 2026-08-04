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

**判据量的是「可见内容的边界」而不是元素盒**：满宽底色条（.nav）本来就该
铺到屏幕最边上（刘海区与 --ink 同色、连成一体才好看），量它的盒子必然报
"左右 = 0 被切" —— 那是误报。反过来，元素盒有 padding 时，量盒子也看不出
内容有没有被切。所以贴边容器要量它【最外侧的子元素】。

**踩过的坑**（都会让结果说谎）：
  · 量之前必须判可见：`display:none` 父容器下的元素是 0×0，
    量出来"内容顶沿 = 0"，会伪装成"被刘海压住"。
  · 撤改动做负向验证时，要撤【当前视口真正生效的那条规则】。
    393px 视口命中 max-width:560px 媒体查询，那里的 #basket 覆盖了基础规则，
    所以撤基础规则毫无效果、测试照样绿 —— 这个假绿骗过我一次。

用法：
    python3 -m http.server 8850 --directory site &
    python3 tools/verify_safe_area.py        # 退出码 0 = 全部避开
"""
import asyncio
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8850
P = f"http://localhost:{PORT}"

# 两种设备形态。竖屏刘海在顶、横屏刘海在侧 —— 后者会让 left/right 变成非零，
# 是完全不同的一组约束（只测竖屏会漏掉侧边被切）。数值取 iPhone 14 Pro 实际值。
FORMS = [
    dict(name="竖屏", w=393, h=852, ins=dict(top=59, right=0,  bottom=34, left=0)),
    dict(name="横屏", w=852, h=393, ins=dict(top=0,  right=47, bottom=21, left=47)),
]

# sel   —— 要检查的元素
# probe —— "content" 量【最外侧子元素】的边界（满宽底色条用这个：它自己该铺到边，
#           被切的风险在内容上）；"self" 量元素自身的盒（浮层、播放器这类整体都不该越界）
# axes  —— 只检查这几个方向。居中/超高元素在别的方向上必然"越界"，那是溢出不是遮挡，
#           查了只会产生噪音（.stage 高 852 在 393 视口下底沿是 -242）。
CASES = [
    dict(label="落地页 stage",     page="index.html",  sel=".stage",     probe="content", axes="lr"),
    dict(label="日报 顶栏",        page="daily.html",  sel=".nav",       probe="content", axes="tlr"),
    dict(label="日报 播放器",      page="daily.html",  sel="#np",        probe="self",    axes="blr", setup="play"),
    dict(label="日报 浮层 sheet",  page="daily.html",  sel="#lb .sheet", probe="self",    axes="tblr", setup="lb"),
    dict(label="日报 浮层关闭键",  page="daily.html",  sel="#lb .x",     probe="self",    axes="tr",   setup="lb"),
    dict(label="随机页 播放器",    page="random.html", sel="#np",        probe="self",    axes="blr", setup="rand_play"),
    dict(label="随机页 篮子",      page="random.html", sel="#basket",    probe="self",    axes="lr",  setup="rand_bk"),
]

JS = """(a) => {
  const [sel, INS, probe, axes] = a;
  const e = document.querySelector(sel);
  if (!e) return {skip: '元素不存在'};
  let g = e.getBoundingClientRect();
  if (g.width < 1 || g.height < 1) return {skip: '不可见（0×0）'};
  let note = '';
  if (probe === 'content') {
    // 满宽底色条：它自己该铺到屏幕边，被切的是里面的内容。
    // 取最外侧的【叶子/直接可见子元素】联合边界。
    // 只取【叶子元素】—— 真正画出像素的那些。布局容器（.wrap、.foot 这类满宽的
    // flex/grid 壳）本身就该铺满，它们靠自己的 padding 把内容推进安全区；
    // 把容器算成"内容"会误报（实测 .nav .wrap 宽 852 距边 0，而里面的 logo 距边 81）。
    const kids = [...e.querySelectorAll('*')].filter(k => {
      const kg = k.getBoundingClientRect();
      if (kg.width < 1 || kg.height < 1) return false;
      if (getComputedStyle(k).visibility === 'hidden') return false;
      // 有可见子元素 = 它是容器，不是叶子
      return ![...k.children].some(ch => {
        const cg = ch.getBoundingClientRect();
        return cg.width >= 1 && cg.height >= 1;
      });
    });
    if (!kids.length) return {skip: '容器内无叶子内容'};
    const L = Math.min(...kids.map(k => k.getBoundingClientRect().left));
    const R = Math.max(...kids.map(k => k.getBoundingClientRect().right));
    const T = Math.min(...kids.map(k => k.getBoundingClientRect().top));
    const B = Math.max(...kids.map(k => k.getBoundingClientRect().bottom));
    g = {left: L, right: R, top: T, bottom: B};
    note = `内容(${kids.length}个子元素)`;
  } else {
    const c = getComputedStyle(e);
    g = {left: g.left + parseFloat(c.paddingLeft || 0),
         right: g.right - parseFloat(c.paddingRight || 0),
         top: g.top + parseFloat(c.paddingTop || 0),
         bottom: g.bottom - parseFloat(c.paddingBottom || 0)};
    note = '内容区(扣padding)';
  }
  const d = {t: g.top, b: innerHeight - g.bottom, l: g.left, r: innerWidth - g.right};
  const need = {t: INS.top, b: INS.bottom, l: INS.left, r: INS.right};
  const out = {note, dist: {}, bad: []};
  for (const k of axes) {
    out.dist[k] = Math.round(d[k]);
    if (d[k] < need[k] - 0.6) out.bad.push(`${k}=${Math.round(d[k])}<${need[k]}`);
  }
  return out;
}"""

SETUPS = {
    "play":      [("eval", "()=>{const b=document.querySelector('.pbtn'); if(b)b.click()}"), ("wait", 700)],
    "lb":        [("click", ".cover-zoom"), ("wait", 450)],
    "rand_play": [("click", "#roll"), ("wait", 2900),
                  ("eval", "()=>{const b=document.querySelector('.pbtn'); if(b)b.click()}"), ("wait", 700)],
    "rand_bk":   [("click", "#roll"), ("wait", 2900), ("click", ".heart"), ("wait", 800),
                  ("eval", "()=>{const b=document.querySelector('.pbtn'); if(b)b.click()}"), ("wait", 700)],
}


async def do_setup(pg, name):
    for kind, arg in SETUPS.get(name, []):
        if kind == "wait":
            await pg.wait_for_timeout(arg)
        elif kind == "eval":
            await pg.evaluate(arg)
        elif kind == "click":
            el = await pg.query_selector(arg)
            if el:
                await el.click()


async def main():
    from playwright.async_api import async_playwright
    total_ok = total_bad = total_skip = 0
    failures = []
    async with async_playwright() as pw:
        br = await pw.chromium.launch()
        for form in FORMS:
            ins = form["ins"]
            ov = (":root{" + ";".join(f"--sa{k[0]}:{v}px !important"
                                      for k, v in (("top", ins["top"]), ("right", ins["right"]),
                                                   ("bottom", ins["bottom"]), ("left", ins["left"]))) + "}")
            ctx = await br.new_context(viewport={"width": form["w"], "height": form["h"]},
                                       device_scale_factor=3, is_mobile=True, has_touch=True)
            await ctx.add_init_script(
                "(()=>{const c=%s;const f=()=>{const s=document.createElement('style');"
                "s.textContent=c;document.head.appendChild(s)};"
                "if(document.head)f();else document.addEventListener('DOMContentLoaded',f)})()" % repr(ov))
            pg = await ctx.new_page()
            print(f"\n  【{form['name']} {form['w']}×{form['h']}】"
                  f" 顶{ins['top']} 右{ins['right']} 底{ins['bottom']} 左{ins['left']}")
            for c in CASES:
                await pg.goto(f"{P}/{c['page']}", wait_until="networkidle")
                if c.get("setup"):
                    await do_setup(pg, c["setup"])
                r = await pg.evaluate(JS, [c["sel"], ins, c["probe"], c["axes"]])
                if r.get("skip"):
                    total_skip += 1
                    print(f"    {c['label']:20} ⊘ {r['skip']}")
                    continue
                dist = " ".join(f"{k}={v}" for k, v in r["dist"].items())
                if r["bad"]:
                    total_bad += 1
                    failures.append(f"{form['name']}/{c['label']}: {','.join(r['bad'])}")
                    print(f"    {c['label']:20} {dist:26} ✗ {','.join(r['bad'])}")
                else:
                    total_ok += 1
                    print(f"    {c['label']:20} {dist:26} ✓  [{r['note']}]")

            # 篮子的真正风险不是被安全区遮，而是被吸底播放器盖住。
            # 只查"避开安全区"会让 #basket 的 bottom 联动改动假绿（硬编码 76px 照样过）。
            await pg.goto(f"{P}/random.html", wait_until="networkidle")
            await do_setup(pg, "rand_bk")
            r = await pg.evaluate("""()=>{const b=document.querySelector('#basket'),n=document.querySelector('#np');
                if(!b||!n) return {skip:1};
                const gb=b.getBoundingClientRect(), gn=n.getBoundingClientRect();
                if(gb.height<1||gn.height<1) return {skip:1};
                return {overlap:Math.round(gb.bottom-gn.top)};}""")
            if r.get("skip"):
                total_skip += 1
                print(f"    {'篮子vs播放器重叠':18} ⊘ 有一方不可见")
            elif r["overlap"] > 0:
                total_bad += 1
                failures.append(f"{form['name']}/篮子被播放器盖住 {r['overlap']}px")
                print(f"    {'篮子vs播放器重叠':18} {r['overlap']}px  ✗ 被盖住")
            else:
                total_ok += 1
                print(f"    {'篮子vs播放器重叠':18} {r['overlap']}px  ✓ 不重叠")
            await ctx.close()
        await br.close()

    print(f"\n  通过 {total_ok} / 失败 {total_bad} / 跳过 {total_skip}")
    # 跳过太多说明用例没真正跑到（选择器写错、状态没触发），那是哑弹不是通过
    if total_skip > 2:
        print(f"  ✗ 跳过 {total_skip} 个用例过多，护栏可能在空转")
        return 1
    if failures:
        print("  ✗ " + "\n  ✗ ".join(failures))
        return 1
    print("  ✓ 全部避开安全区")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
