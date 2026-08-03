"""生成 GPT_MEMORY.md —— 给 GPT 的长期记忆台账。

为什么要自动生成：GPT 每开一个新对话就失忆，不知道自己写过谁、当前进度如何。
手写的状态文档必然过期（这个项目已经在快照文案上栽过一次，见 memory
derived-artifact-staleness），所以**状态部分全部从仓库现算**，只有「累积教训」是手写的。

每次 import-bios workflow 成功后自动重跑，保证 GPT 读到的永远是真实状态。

用法：python3 tools/gen_gpt_memory.py
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# 手写部分：每次踩坑后往这里追加。状态部分不要手写。
LESSONS = """\
### 已经踩过的坑（每条都真实发生过，别再犯）

1. **编码**：第一批 30 位 bio 在传输中损坏，90% 汉字不可复原、整批作废。
   通道吞掉了 `0x80–0x9F` 区间的字节（「加拿大」的 `e5 8a a0 e6 8b bf` 变成 `e5 20 e6 bf`）。
   → **中文一律 `json.dumps(data, ensure_ascii=True)` 写成 `\\uXXXX`**，纯 ASCII 物理上不会坏。

2. **批次重叠**：batch05 与 batch02 有 16 位艺人重叠，且两版内容全不同。
   后写的覆盖了先写的，而后写那版更差。
   → **开工前先查「已写清单」**（本文档下方），别重复写。

3. **地名不翻译**：batch05 有 44% 的条目写「来自 Virginia」「Brooklyn 词曲作者」，
   而同一批人在 batch02 里写的是「弗吉尼亚州夏洛茨维尔」「常驻布鲁克林」。
   中英混搭是站内明确否掉的写法。
   → **地名用中文**；人名 / 厂牌名 / 专辑名保留英文是对的。

4. **bio 写成 oneliner 的扩写**：放大页里 oneliner 单独有一栏，bio 再复述一遍等于没提供新信息。
   → **bio 给可核实的事实**（本名、生年、地点、厂牌、谁签的、哪张专辑、用什么设备、之前在哪个乐队）。

5. **质量批间漂移**：单看每批都合规，连起来看才发现 batch05 明显退步。
   → **每批交付时附自查数字**（见下方交付清单），让漂移可见。
"""


def _pool():
    return json.loads((ROOT / "data" / "pool.json").read_text(encoding="utf-8"))


def _artists():
    p = ROOT / "data" / "artists.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def _batches():
    """已归档的批次：文件名 → 条数。"""
    d = ROOT / "inbox" / "bios" / "done"
    out = []
    if d.exists():
        for f in sorted(d.glob("*.json")):
            if f.name.endswith("_manifest.json"):
                continue
            try:
                out.append((f.name, len(json.loads(f.read_text(encoding="utf-8")))))
            except Exception:
                out.append((f.name, -1))
    return out


EN_PLACES = ("Virginia", "Brooklyn", "Nashville", "Texas", "California", "London",
             "Tokyo", "Chicago", "Berlin", "Paris", "Melbourne", "Toronto", "Glasgow",
             "Seattle", "Portland", "Detroit", "New York", "Los Angeles", "Manchester",
             "Bristol", "Copenhagen", "Stockholm", "Oslo")


def build() -> str:
    pool = _pool()
    arts = _artists()
    pool_artists = {t.get("artist", "") for t in pool}
    have = {a["artist"] for a in arts}
    todo = sorted(pool_artists - have)

    # 待写艺人按「本站收录曲目数」排序——收得多的更常出现在页面上，优先写
    cnt = collections.Counter(t.get("artist", "") for t in pool)
    todo_ranked = sorted(todo, key=lambda a: (-cnt[a], a))

    # 缺口分析：哪些方向仍偏少
    genres = collections.Counter(g for t in pool for g in (t.get("genres") or []))
    moods = collections.Counter(m for t in pool for m in (t.get("mood_tags") or []))
    decades = collections.Counter(
        f"{str(t.get('year',''))[:3]}0s" for t in pool if str(t.get("year", "")).isdigit())
    n_inst = sum(1 for t in pool
                 if not (t.get("vocal_style") or "").strip()
                 or "器乐" in (t.get("vocal_style") or ""))

    # bio 质量现状
    bad_place = [a["artist"] for a in arts
                 if any(re.search(r"(?<![A-Za-z])" + re.escape(x) + r"(?![A-Za-z])", a["bio"])
                        for x in EN_PLACES)]
    L = [len(a["bio"]) for a in arts] or [0]
    conf = collections.Counter(a.get("confidence") for a in arts)

    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    batches = _batches()

    lines = [
        "# GPT 长期记忆 · 操作台账",
        "",
        f"> **本文件由 `tools/gen_gpt_memory.py` 自动生成，最后更新 {today}。**",
        "> 状态数字全部从仓库现算，不会过期。每次开新对话先读这一份。",
        "",
        "---",
        "",
        "## 一、开工前必做（30 秒）",
        "",
        "1. 读本文件的**「三、已写清单」**，确认你要写的艺人还没被写过",
        "2. 读**「四、待写队列」**，从队首取 30–50 位（已按重要度排好序）",
        "3. 扫一眼**「六、已经踩过的坑」**",
        "",
        "## 二、当前状态",
        "",
        "| 项目 | 数字 |",
        "|---|--:|",
        f"| 曲池 | **{len(pool)}** 首 |",
        f"| 池内艺人 | **{len(pool_artists)}** 位 |",
        f"| 已写简介 | **{len(arts)}** 位（覆盖 {100*len(arts)/max(len(pool_artists),1):.1f}%）|",
        f"| 待写 | **{len(todo)}** 位 |",
        f"| confidence | high {conf.get('high',0)} · low {conf.get('low',0)} |",
        f"| bio 长度 | {min(L)}–{max(L)} 字（均 {sum(L)//len(L)}）|",
        f"| 含未翻译地名 | {len(bad_place)} 条 —— **待修，见坑 #3** |" if bad_place
        else "| 含未翻译地名 | 0 条 ✅ |",
        "",
        "### 已导入批次",
        "",
    ]
    if batches:
        lines += ["| 批次 | 条数 |", "|---|--:|"]
        lines += [f"| `{n}` | {c} |" for n, c in batches]
    else:
        lines.append("（还没有）")

    lines += [
        "",
        "## 三、已写清单（这些别再写）",
        "",
        "<details><summary>展开 " + str(len(have)) + " 位</summary>",
        "",
        "```",
    ]
    hs = sorted(have)
    lines += ["  ".join(hs[i:i+4]) for i in range(0, len(hs), 4)]
    lines += ["```", "", "</details>", "",
              "## 四、待写队列（按本站收录曲目数降序，从队首取）", "",
              f"完整清单见 [`data/artists_todo.json`](data/artists_todo.json)。**接下来这 60 位优先**：", "", "```"]
    lines += ["  ".join(todo_ranked[i:i+4]) for i in range(0, min(60, len(todo_ranked)), 4)]
    lines += ["```", ""]

    # 补库缺口
    lines += [
        "## 五、补库仍偏缺的方向",
        "",
        "（写 bio 用不到这节，做补库时看）",
        "",
        f"- **器乐**：{n_inst}/{len(pool)} 首（{100*n_inst/max(len(pool),1):.0f}%），偏低",
        f"- **明快上扬**：`upbeat` {moods.get('upbeat',0)} 首 · `hopeful` {moods.get('hopeful',0)} 首，"
        "整期容易一路温柔到底",
        "- **年代**：" + " · ".join(f"{k} {v}" for k, v in sorted(decades.items())),
        "- **非英语世界**：日语 / 韩语 / 西语 / 北欧 / 中东 / 非洲",
        "- **BPM**：< 70 的极慢与 > 125 的快都少",
        "",
        f"当前流派 {len(genres)} 类，TOP10："
        + "、".join(f"{k}({v})" for k, v in genres.most_common(10)),
        "",
        "领地划分与检索策略见 [`GPT_TERRITORIES.md`](GPT_TERRITORIES.md)。",
        "",
        "## 六、" + LESSONS.split("### ", 1)[1].split("\n", 1)[0],
        "",
        LESSONS.split("\n", 1)[1].split("\n", 1)[1],
        "## 七、交付清单（每批照做）",
        "",
        "```python",
        "import json, hashlib",
        "",
        "data = [...]                                   # 你写的 bio 数组",
        "s = json.dumps(data, ensure_ascii=True, indent=2)   # ← 关键：ensure_ascii",
        "open('batchNN.json', 'w').write(s)",
        "",
        "sha = hashlib.sha256(s.encode('ascii')).hexdigest()",
        "json.dump({'file': 'batchNN.json', 'count': len(data), 'sha256': sha},",
        "          open('batchNN_manifest.json', 'w'), indent=1)",
        "```",
        "",
        "交付时附上这几个自查数字（让质量漂移可见）：",
        "",
        "- 条数 · high/low 分布 · bio 长度范围",
        "- 黑名单词命中数（应为 0）",
        "- 「让人 / 令人」出现次数（应为 0）",
        "- **未翻译英文地名条数（应为 0）**",
        "- 与「已写清单」的重叠数（应为 0）",
        "",
        "两个文件一起传到仓库 `inbox/bios/`，CI 自动核 SHA → 校验 → 导入 → 重建 → 部署。",
        "**任一条不合格就整批拒绝**，文件留在原地等修正，不会污染数据。",
        "",
        "## 八、其它文档",
        "",
        "| 文档 | 什么时候看 |",
        "|---|---|",
        "| [`GPT_ARTIST_BIOS.md`](GPT_ARTIST_BIOS.md) | 写简介的完整任务书（正反例、四层结构）|",
        "| [`GPT_VOICE.md`](GPT_VOICE.md) | 用语与文风（黑名单 47 词、句式配额、站内固定用语）|",
        "| [`GPT_CATCHUP.md`](GPT_CATCHUP.md) | 补库的导入硬规则（mood 受控词表、版本错配）|",
        "| [`GPT_TERRITORIES.md`](GPT_TERRITORIES.md) | 补库的 20 个领地与检索策略 |",
        "",
    ]
    return "\n".join(lines) + "\n"


def refresh_todo() -> int:
    """顺手刷新 data/artists_todo.json —— 它是 GPT 的输入清单，写完一批就该少一批。"""
    pool = _pool()
    have = {a["artist"] for a in _artists()}
    by = collections.defaultdict(list)
    for t in pool:
        by[t.get("artist", "")].append(t)
    rows = []
    for a, ts in by.items():
        if a in have or not a:
            continue
        yrs = sorted(str(t.get("year", "")) for t in ts if t.get("year"))
        gs = collections.Counter(g for t in ts for g in (t.get("genres") or []))
        rows.append({
            "artist": a, "n": len(ts),
            "years": (yrs[0] if yrs and yrs[0] == yrs[-1] else f"{yrs[0]}–{yrs[-1]}") if yrs else "",
            "genres": [k for k, _ in gs.most_common(3)],
            "albums": sorted({t.get("album", "") for t in ts if t.get("album")})[:3],
            "titles": [t.get("title", "") for t in ts[:3]],
            "oneliner": ts[0].get("artist_oneliner", ""),
        })
    rows.sort(key=lambda r: (-r["n"], r["artist"]))
    (ROOT / "data" / "artists_todo.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(rows)


if __name__ == "__main__":
    out = ROOT / "GPT_MEMORY.md"
    out.write_text(build(), encoding="utf-8")
    n = refresh_todo()
    print(f"写出 {out.name}（{out.stat().st_size} 字节）· artists_todo.json 刷新为 {n} 位")
