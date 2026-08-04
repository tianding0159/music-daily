"""动效性能回归探针：量「每帧主线程工作量」与「丢帧」，判能否跑满高刷。

**为什么不能只看 CSS 属性名**：静态审计只能说「这个属性理论上触发 layout」，
说不出「它一秒跑几次、实际掉了多少帧」。2026-08-04 实测就打脸过——静态审计
报出 7 处动画在动非合成器属性（box-shadow / width / visibility / …），
看着很吓人，实测它们全是一次性过场、摊到帧上几乎为零；而真正每帧触发 layout
的是两个 SVG `<g>`（cat-eyes / cat-tail）缺合成层提示，那两个静态审计判为「✓ 合成器」。

**判据**（240fps 每帧预算 4.17ms）：
  · 丢帧率 —— requestAnimationFrame 实际间隔，p99 与中位数的差
  · 每帧主线程工作量 = (Layout + RecalcStyle + Script) / 帧数
  · 4x CPU 节流下仍在预算内 → 真机高刷有充足余量

**容器里跑不出 240fps**（headless 锁 60），所以不要指望直接读到 240 ——
用节流放大压力做外推才是可行的判法。

用法：
    python3 -m http.server 8850 --directory site &
    python3 tools/perf_probe.py            # 默认三页全量
    python3 tools/perf_probe.py daily.html # 只测一页
"""
from __future__ import annotations

import asyncio
import statistics
import sys

PORT = 8850
BUDGET_240 = 1000 / 240
PAGES = ["index.html", "daily.html", "random.html"]


async def _frames(pg, ms=2000):
    return await pg.evaluate("""(ms) => new Promise(res => {
        const ts = []; let last = performance.now(); const t0 = last;
        (function tick(now) {
            ts.push(now - last); last = now;
            if (now - t0 < ms) requestAnimationFrame(tick); else res(ts.slice(1));
        })(last);
    })""", ms)


async def probe(ctx, name, rate=1):
    pg = await ctx.new_page()
    cdp = await pg.context.new_cdp_session(pg)
    if rate > 1:
        await cdp.send("Emulation.setCPUThrottlingRate", {"rate": rate})
    await cdp.send("Performance.enable")
    await pg.goto(f"http://localhost:{PORT}/{name}", wait_until="networkidle")
    await pg.wait_for_timeout(800)

    a = {m["name"]: m["value"] for m in (await cdp.send("Performance.getMetrics"))["metrics"]}
    fr = await _frames(pg)
    b = {m["name"]: m["value"] for m in (await cdp.send("Performance.getMetrics"))["metrics"]}
    d = lambda k: (b.get(k, 0) - a.get(k, 0)) * 1000        # noqa: E731

    n = len(fr) or 1
    per = (d("LayoutDuration") + d("RecalcStyleDuration") + d("ScriptDuration")) / n
    s = sorted(fr)
    med = statistics.median(s) if s else 0
    p99 = s[int(len(s) * 0.99)] if s else 0
    drops = sum(1 for x in s if med and x > med * 1.5)

    # 合成层：SVG transform 动画容易漏提层，单独报出来
    layers = await pg.evaluate("""() => {
        const out = [];
        for (const el of document.querySelectorAll('*')) {
            const cs = getComputedStyle(el);
            const anim = el.getAnimations().filter(x => x.playState === 'running');
            if (!anim.length) continue;
            const isSvg = el.namespaceURI && el.namespaceURI.includes('svg');
            const hinted = cs.willChange !== 'auto' || /translateZ|matrix3d/.test(cs.transform);
            if (isSvg && !hinted)
                out.push((el.getAttribute('class') || el.tagName));
        }
        return [...new Set(out)].slice(0, 10);
    }""")
    await pg.close()
    return dict(per=per, med=med, p99=p99, drops=drops, n=n, unhinted=layers)


async def main():
    from playwright.async_api import async_playwright
    pages = sys.argv[1:] or PAGES
    async with async_playwright() as p:
        br = await p.chromium.launch()
        ctx = await br.new_context(viewport={"width": 1280, "height": 900},
                                   reduced_motion="no-preference")
        print(f"  240fps 每帧预算 {BUDGET_240:.2f}ms\n")
        print("  页面            节流  每帧主线程   占预算  中位间隔    p99   丢帧")
        bad = []
        for name in pages:
            for rate in (1, 4):
                m = await probe(ctx, name, rate)
                pct = 100 * m["per"] / BUDGET_240
                flag = "✓" if pct < 100 else "✗ 超预算"
                if pct >= 100:
                    bad.append(f"{name} @{rate}x = {pct:.0f}%")
                print(f"  {name:14} {rate}x  {m['per']:8.3f}ms  {pct:6.1f}%  "
                      f"{m['med']:6.2f}ms {m['p99']:6.2f}ms  {m['drops']:3}  {flag}")
                if rate == 1 and m["unhinted"]:
                    print(f"  {'':17}⚠️ SVG 动画元素缺合成层提示: {m['unhinted']}")
            print()
        await br.close()
        print("  " + ("全部在预算内 ✓" if not bad else f"超预算: {bad}"))
        return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
