"""文案体检：把 docs/style_bible.md 的口径变成可执行检查。

为什么单独一个模块：文案标准以前只活在 style_bible.md 和 commit message 里，
靠人肉发现问题 —— 实测结果是「声称 856/856 全量重写」其实只改了 why 一个字段，
另两个字段 856×2 条一字未动，而且圣经里的范例句被原样当歌曲文案入库、还跨歌撞车。
标准不进代码，就只能靠自觉；进了代码，补库和 CI 都能挡。

三类检查（越靠前越硬）：
  P0  黑名单词命中 / 范例句被原样入库 / 跨歌完全重复
  警告 单一模板占比超阈值（破折号同位语、scene 收尾句式、起句时间词）

黑名单与范例句都从 docs/style_bible.md 动态 parse，不在本文件硬编码 ——
否则改了圣经忘了改代码，两处口径就会静默漂移。

用法：
  python3 scripts/copy_check.py                 # 体检 data/pool.json
  python3 scripts/copy_check.py <某.json>        # 体检候选文件（同样的 schema）
被 healthcheck.py 与 validate_candidates.py 复用（import check_copy）。
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIBLE = ROOT / "docs" / "style_bible.md"

FIELDS = ("artist_oneliner", "why", "scene")

# 单一模板占比上限（超过即警告——单条看不出问题，连着读就露馅）
MAX_DASH_PCT = 30          # artist_oneliner 破折号同位语
MAX_TAIL_PCT = 30          # scene 收尾句式（末 4 字）
MAX_TIMEWORD_PCT = 35      # scene 起句时间词
TIME_WORDS = ("深夜", "凌晨", "傍晚", "夏天", "午后", "清晨", "周末", "雨天", "半夜", "早上")


def _bible_text() -> str:
    return BIBLE.read_text(encoding="utf-8") if BIBLE.exists() else ""


def blacklist(text: str = "") -> list[str]:
    """从圣经第五节的中文陈词段落 parse 黑名单词，不硬编码。"""
    text = text or _bible_text()
    m = re.search(r"\*\*中文陈词/鸡汤/营销体\*\*：\s*\n(.+?)\n\s*\n", text, re.S)
    if not m:
        return []
    body = m.group(1)
    words = re.split(r"[、；;，,\s]+", body)
    out = []
    for w in words:
        w = re.sub(r"[（(].*?[)）]", "", w).strip(" 。.·…")
        # 只留纯中文短词；带「/」的取两侧；含省略号或引号的是句式示例不当词用
        if not w or "…" in w or '"' in w or "“" in w:
            continue
        # 「宝藏歌手/专辑」是「宝藏歌手 / 宝藏专辑」的缩写，「视听/听觉盛宴」同理。
        # 直接按 / 拆会得到裸词「专辑」这种中性词，误报一片 —— 用左词的共享前缀还原。
        parts = [x.strip() for x in w.split("/") if x.strip()]
        if len(parts) == 2 and len(parts[0]) > len(parts[1]):
            pre = parts[0][: len(parts[0]) - len(parts[1])]
            parts[1] = pre + parts[1] if len(pre) >= 1 else parts[1]
        for part in parts:
            if 2 <= len(part) <= 8 and re.fullmatch(r"[一-鿿]+", part):
                out.append(part)
    # 这几个是圣经里的说明性词条，不是可直接匹配的禁词
    return sorted(set(out) - {"鸡汤排比", "视听", "专辑"})


def examples(text: str = "") -> list[str]:
    """parse 圣经里的范例句，用来挡「范例被原样当文案入库」。"""
    text = text or _bible_text()
    out = []
    for m in re.finditer(r'^-\s*[""](.+?)[""]\s*$', text, re.M):
        out.append(m.group(1).strip())
    for m in re.finditer(r"^-\s*(?:before|after)：(.+?)$", text, re.M):
        out.append(m.group(1).strip())
    return sorted({e for e in out if len(e) > 6})


def _pct(n: int, total: int) -> float:
    return round(100.0 * n / total, 1) if total else 0.0


def check_copy(pool: list[dict]) -> tuple[list[str], list[str], dict]:
    """返回 (p0, warn, metrics)。pool 是 track dict 列表。"""
    p0: list[str] = []
    warn: list[str] = []
    bl = blacklist()
    ex = set(examples())
    n = len(pool)
    metrics: dict = {"n": n, "blacklist_words": len(bl), "examples": len(ex)}
    if not n:
        return p0, warn, metrics

    # ── P0-1 黑名单词 ──
    # 圣经里带「除非…」条件豁免的词降级为警告：颗粒感(真指失真质地可用)、
    # 空气感/大气(有具体锚点可用)、天花板/后撑很大(无所指时才是营销体)。
    SOFT = {"颗粒感", "空气感", "大气", "天花板", "后劲很大", "明亮的音色", "干净的嗓音"}
    hits: list[str] = []
    soft_hits: list[str] = []
    for t in pool:
        for f in FIELDS:
            v = t.get(f) or ""
            for w in bl:
                if w in v:
                    (soft_hits if w in SOFT else hits).append(f"{t.get('id')}·{f}·{w}")
    metrics["blacklist_soft_hits"] = len(soft_hits)
    if soft_hits:
        warn.append(f"条件豁免词 {len(soft_hits)} 处（圣经允许带具体锚点时用，人工抽查）：{soft_hits[:3]}")
    metrics["blacklist_hits"] = len(hits)
    if hits:
        p0.append(f"黑名单词命中 {len(hits)} 处（圣经第五节）：{hits[:4]}")

    # ── P0-2 圣经范例句被原样入库 ──
    stolen = [f"{t.get('id')}·{f}" for t in pool for f in FIELDS if (t.get(f) or "").strip() in ex]
    metrics["example_verbatim"] = len(stolen)
    if stolen:
        p0.append(f"圣经范例句被原样当文案入库 {len(stolen)} 处：{stolen[:4]}（范例只供体感，禁止入库）")

    # ── P0-3 跨歌完全重复 ──
    for f in FIELDS:
        c = Counter((t.get(f) or "").strip() for t in pool if (t.get(f) or "").strip())
        dup = {k: v for k, v in c.items() if v > 1}
        metrics[f"{f}_dup_groups"] = len(dup)
        if dup:
            k0 = next(iter(dup))
            p0.append(f"{f} 有 {len(dup)} 组跨歌完全重复，例：「{k0[:24]}…」×{dup[k0]}")

    # ── 警告：单一模板占比 ──
    ol = [(t.get("artist_oneliner") or "") for t in pool]
    dash = sum(1 for v in ol if "——" in v or "—" in v)
    metrics["oneliner_dash_pct"] = _pct(dash, n)
    if metrics["oneliner_dash_pct"] > MAX_DASH_PCT:
        warn.append(f"artist_oneliner 破折号同位语占 {metrics['oneliner_dash_pct']}%（上限 {MAX_DASH_PCT}%）——模板复读")

    sc = [(t.get("scene") or "") for t in pool]
    tails = Counter(v[-4:] for v in sc if len(v) >= 4)
    if tails:
        tk, tv = tails.most_common(1)[0]
        metrics["scene_top_tail"] = tk
        metrics["scene_top_tail_pct"] = _pct(tv, n)
        if metrics["scene_top_tail_pct"] > MAX_TAIL_PCT:
            warn.append(f"scene 收尾「{tk}」占 {metrics['scene_top_tail_pct']}%（上限 {MAX_TAIL_PCT}%）——换角度收尾")

    tw = sum(1 for v in sc if any(v.startswith(w) for w in TIME_WORDS))
    metrics["scene_timeword_pct"] = _pct(tw, n)
    if metrics["scene_timeword_pct"] > MAX_TIMEWORD_PCT:
        warn.append(f"scene 起句时间词占 {metrics['scene_timeword_pct']}%（上限 {MAX_TIMEWORD_PCT}%）")

    # ── 警告：自定义 AI 味句式 ──
    ai = {
        "又A又B": sum(1 for t in pool for f in FIELDS if re.search(r"又[^，。]{1,4}又", t.get(f) or "")),
        "让人/令人": sum(1 for t in pool for f in FIELDS if re.search(r"[让令]人", t.get(f) or "")),
    }
    metrics["ai_tics"] = ai
    for k, v in ai.items():
        if v > max(6, n * 0.02):
            warn.append(f"「{k}」句式 {v} 处（>2%）——翻译腔，换具体动作")

    return p0, warn, metrics


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "pool.json"
    pool = json.loads(src.read_text(encoding="utf-8"))
    if isinstance(pool, dict):
        pool = pool.get("tracks") or []
    p0, warn, metrics = check_copy(pool)
    print("=== copy_check ===", src.name)
    print(json.dumps(metrics, ensure_ascii=False, indent=1))
    for w in warn:
        print("  [warn]", w)
    for e in p0:
        print("  [P0]  ", e)
    if p0:
        print(f"\n❌ {len(p0)} 项文案 P0")
        return 1
    print("\n✅ 文案无 P0" + (f"（{len(warn)} 项告警）" if warn else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
