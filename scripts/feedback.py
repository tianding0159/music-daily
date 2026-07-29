"""轻量用户反馈存取（Phase 3）。data/feedback.json 为一个数组，每条：
  {"date": "YYYY-MM-DD", "track_id": "apple:123|sha1:..", "rating": "...", "note": ""}
允许 rating：liked / saved / skipped / disliked / more_like_this。

本轮只做数据结构 + 读写 + 文档；不自动改 docs/profile.md。
后续补库/picker 可读取做**建议性**加权（连续正反馈的声音邻域适度加权、连续跳过降权），
口味画像的任何变更都应先生成建议、由人确认后再改 profile。
"""
from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from pathlib import Path

FB = Path(__file__).resolve().parent.parent / "data" / "feedback.json"
ALLOWED = {"liked", "saved", "skipped", "disliked", "more_like_this"}


def load() -> list[dict]:
    return json.loads(FB.read_text(encoding="utf-8")) if FB.exists() else []


def add(track_id: str, rating: str, note: str = "", date: str | None = None) -> list[dict]:
    if rating not in ALLOWED:
        raise ValueError(f"rating 必须是 {sorted(ALLOWED)}")
    fb = load()
    fb.append({"date": date or dt.date.today().isoformat(),
               "track_id": track_id, "rating": rating, "note": note})
    FB.write_text(json.dumps(fb, ensure_ascii=False, indent=2), encoding="utf-8")
    return fb


def summary() -> dict:
    fb = load()
    return {"total": len(fb), "by_rating": dict(Counter(x.get("rating") for x in fb))}


if __name__ == "__main__":
    print(json.dumps(summary(), ensure_ascii=False, indent=2))
