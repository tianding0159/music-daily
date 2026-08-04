"""生成 PWA 图标：黑胶唱片 + 橙色中心标签，用站点自己的色板。

**为什么不直接放大 favicon**：那是个橙方块 + 黑描边，在 512px 下就是一块纯色，
认不出是什么站。黑胶是这个站的核心意象（落地页整块唱机、随机页的转盘、
「另起一首」那个图标），图标用它才有辨识度。

几何取自落地页那个唱盘的实测参数（见 render_random 的 `.tt`）：
  · 沟槽必须**疏密不均**——等距同心圆会像靶心（调落地页图标时第 8 版才试出来）
  · 外圈沟槽更密（真唱片外圈曲目多）
  · 中心标签约占半径 0.27（0.36 看着胖，真黑胶标签比想象的小）
  · 一道受光高光弧 + 盘缘细亮边，是「这是个实体唱片」的关键线索

用法：python3 tools/make_icons.py
"""
from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

INK = (15, 14, 18)        # --ink
ORANGE = (240, 90, 36)    # --orange
GROOVE = (38, 36, 42)
DISC = (26, 24, 29)
SHEEN = (86, 82, 94)
RIM = (58, 54, 64)

# 疏密不均：外圈密、内圈疏
GROOVE_RS = [.97, .94, .90, .87, .83, .78, .74, .69, .64, .58, .52, .45, .38]


def make(size: int, maskable: bool = False) -> Image.Image:
    """maskable=True 时唱片缩进「安全区」（直径 80% 的圆）内。

    Android 会按 purpose 声明去裁图标——圆形、方角、水滴各家不同，只保证
    中心直径 80% 的圆不被裁。默认画法的唱片直径 88%，最外两圈沟槽与盘缘
    亮边正好落在裁切带里（实测超出 20.5px @512）。声明一个不合规的
    maskable 比不声明更糟：系统信了这个声明，就真的会把边切掉。
    所以 maskable 版单出一张，底色仍出血到边（裁到哪都只切到 INK）。
    """
    S = size * 4                          # 4x 超采样再缩，边缘才干净
    im = Image.new("RGB", (S, S), INK)
    d = ImageDraw.Draw(im)
    # 0.44 = 唱片占满画布（普通图标）；0.355 让盘缘落在 0.40 安全圈内还留一点余量
    c, R = S / 2, S * (0.355 if maskable else 0.44)

    d.ellipse([c - R, c - R, c + R, c + R], fill=DISC)

    for i, f in enumerate(GROOVE_RS):
        r = R * f
        w = max(1, int(S * (0.004 if i % 3 else 0.0065)))
        d.ellipse([c - r, c - r, c + r, c + r], outline=GROOVE, width=w)

    # 受光高光弧（左上）
    a = R * 0.90
    d.arc([c - a, c - a, c + a, c + a], start=190, end=258,
          fill=SHEEN, width=max(2, int(S * 0.022)))

    # 盘缘细亮边
    d.ellipse([c - R, c - R, c + R, c + R], outline=RIM, width=max(1, int(S * 0.006)))

    # 中心纸标签
    lr = R * 0.27
    d.ellipse([c - lr, c - lr, c + lr, c + lr], fill=ORANGE)

    # 主轴孔
    hr = R * 0.05
    d.ellipse([c - hr, c - hr, c + hr, c + hr], fill=INK)

    return im.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    for n in (192, 512, 180):             # 180 = apple-touch-icon
        p = SITE / f"icon-{n}.png"
        make(n).save(p, optimize=True)
        print(f"  {p.relative_to(ROOT)}  {p.stat().st_size} 字节")

    p = SITE / "icon-maskable-512.png"    # Android 自适应裁切专用
    make(512, maskable=True).save(p, optimize=True)
    print(f"  {p.relative_to(ROOT)}  {p.stat().st_size} 字节（唱片缩进安全区）")
