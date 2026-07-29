"""生成网易云音乐可导入的纯文本歌单块。

网易云 App / 多数第三方导入工具吃 `歌名 - 艺人` 逐行列表。返回可全选复制的纯文本。
"""
from __future__ import annotations


def build_text(tracks: list[dict]) -> str:
    lines = [f"{t['title']} - {t['artist']}" for t in tracks]
    return "\n".join(lines)


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    data = Path(__file__).resolve().parent.parent / "data"
    pool = json.loads((data / "pool.json").read_text(encoding="utf-8"))
    print(build_text(pool[: int(sys.argv[1]) if len(sys.argv) > 1 else 15]))
