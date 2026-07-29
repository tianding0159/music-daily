"""生成网易云音乐可导入的纯文本歌单块（含歌单名标题行）。

网易云 App / 多数第三方导入工具吃 `歌名 - 艺人` 逐行列表；很多导入器把**不含 " - " 的
首行当作歌单名**。所以第一行放一个按文笔圣经语气、贴合当天主导气质起的歌单名，
复制导入时即自动创建该名称的歌单。
"""
from __future__ import annotations

import hashlib
from collections import Counter

# 歌单名候选（文笔圣经语气：具体、有画面、不用"治愈/空灵/氛围感"等陈词）。
# 每条挂 1~2 个气质关键词，用于贴合当天曲目的主导 mood_tags。首行不得含 " - "。
TITLE_BANK: list[tuple[str, tuple[str, ...]]] = [
    ("城市夜里，声音都调小了", ("城市夜晚", "深夜", "都市")),
    ("夏天傍晚，风还没凉下来", ("夏天傍晚",)),
    ("雨敲着窗，屋里没开灯", ("雨天",)),
    ("木头、旧磁带和一点灰", ("木质感", "怀旧")),
    ("把肩膀放下来的那半小时", ("松弛", "慵懒")),
    ("颗粒感的午后", ("颗粒感",)),
    ("凌晨两点，只留一盏灯", ("深夜",)),
    ("旧胶片，新调色", ("怀旧", "怀旧又现代")),
    ("留白比声音还多", ("空气感", "静谧")),
    ("电子像呼吸的那种", ("organic", "空气感")),
    ("地铁靠窗的那十分钟", ("都市", "城市夜晚")),
    ("关灯以后才敢想的事", ("内省", "内收", "深夜")),
    ("微凉的清晨，先别说话", ("微凉", "静谧", "清晨")),
    ("潮湿黄昏，木吉他慢慢走", ("木质感", "夏天傍晚")),
    ("一个人也不觉得空的房间", ("松弛", "温柔")),
    ("退潮之后，鞋里还进着沙", ("静谧", "木质感")),
    ("把白天调成夜的亮度", ("城市夜晚", "慵懒")),
    ("冬日下午，斜光只照到半墙", ("冬日", "微凉")),
    ("慢到几乎停下来的好听", ("松弛", "缓慢生长")),
    ("耳朵先安静，人才跟上", ("静谧", "空气感")),
    ("夜色很稠，节拍很轻", ("城市夜晚", "克制")),
    ("有点甜，但克制着", ("明快", "温柔")),
]


def playlist_title(tracks: list[dict], date_str: str) -> str:
    """按当天主导气质挑一个歌单名，附日期保证每日唯一；确定性（同日期同结果）。"""
    md = date_str[5:].replace("-", ".")  # MM.DD
    moods = Counter(m for t in tracks for m in (t.get("mood_tags") or []))
    seed = int(hashlib.sha256(date_str.encode()).hexdigest()[:8], 16)
    best, best_score = TITLE_BANK[0][0], -1.0
    for i, (name, keys) in enumerate(TITLE_BANK):
        overlap = sum(c for m, c in moods.items() if any(k in m or m in k for k in keys))
        tie = ((seed + i * 2654435761) % 997) / 997.0  # 同分时按日期确定性轮换
        score = overlap + tie * 0.01
        if score > best_score:
            best, best_score = name, score
    return f"{best}（{md}）"


def build_text(tracks: list[dict], title: str | None = None) -> str:
    lines = [f"{t['title']} - {t['artist']}" for t in tracks]
    if title:
        return title + "\n" + "\n".join(lines)  # 首行=歌单名（导入时自动命名）
    return "\n".join(lines)


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    data = Path(__file__).resolve().parent.parent / "data"
    pool = json.loads((data / "pool.json").read_text(encoding="utf-8"))
    picks = pool[: int(sys.argv[1]) if len(sys.argv) > 1 else 15]
    print(build_text(picks, playlist_title(picks, "2026-07-28")))
