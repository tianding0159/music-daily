"""B · 全自动补池：池里"没发过的存量"低于阈值时，用 Anthropic API 按同口味标准
发现新曲，iTunes 验真 + 去重后写进 pool.json。只在真低时才花 API（省钱）。

需要环境变量 ANTHROPIC_API_KEY（个人 console.anthropic.com 的 key）。
模型可用 MD_MODEL 覆盖（默认 claude-sonnet-5，质量/成本均衡）。

用法：
  python3 scripts/replenish.py                 # 存量<阈值才补，默认加 40
  python3 scripts/replenish.py --force --add 60
安全网：iTunes 查不到的候选一律丢弃（防 LLM 幻觉出假曲）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path

import itunes
import picker

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"

STAR5 = {"shibuya-kei", "folktronica", "indietronica", "ambient pop", "organic electronic",
         "dream pop", "japanese indie", "jazz pop", "sophisti-pop", "downtempo", "bedroom pop",
         "city pop", "midwest emo", "sampledelia", "ambient folk", "quiet alternative",
         "leftfield pop", "hypnagogic", "chamber pop", "soft post-rock", "chamber folk"}
STAR4 = {"trip-hop", "slowcore", "idm", "neo soul", "neo-soul", "modern bossa", "bossa",
         "electro-acoustic", "electroacoustic", "minimal electronica", "post-classical", "neo-acoustic"}
STAR3 = {"shoegaze", "post punk", "post-punk", "art pop", "indie rock", "psychedelic",
         "indie pop", "guitar pop", "jangle", "folk", "americana", "soul", "aor", "exotica", "boogie"}


def _norm(s: str) -> str:
    return re.sub(r"[^0-9a-z一-鿿぀-ヿ]+", "", (s or "").lower())


def _stars(genres) -> int:
    best = 3
    for g in genres or []:
        gl = g.lower()
        if any(k in gl for k in STAR5):
            best = max(best, 5)
        elif any(k in gl for k in STAR4):
            best = max(best, 4)
        elif any(k in gl for k in STAR3):
            best = max(best, 3)
    return best


def unsent_count(pool: list[dict], history: dict) -> int:
    eligible = [t for t in pool if picker.is_eligible(t)[0]]
    sent_dates = sorted(history)
    cutoff = set(sent_dates[-45:]) if sent_dates else set()
    recent = picker._recent_sent_ids(history, cutoff)
    return sum(1 for t in eligible if t.get("id") not in recent)


def call_llm(profile: str, bible: str, avoid_artists: list[str], add_n: int, model: str) -> list[dict]:
    import anthropic  # 仅补池时需要，deliver 路径零依赖

    client = anthropic.Anthropic()
    system = ("你是顶尖独立音乐策展人 + 中文乐评写手。只推荐真实存在的曲目，绝不编造曲名/艺人。"
              "输出严格的 JSON 数组，除 JSON 外不要任何文字。")
    prompt = f"""按下列口味 profile 与文笔圣经，发现 {add_n} 首**新**曲目加入每日音乐日报候选池。

# 口味 profile
{profile}

# 文笔圣经（artist_oneliner / why / scene 必须照此文风写）
{bible}

# 硬要求
- 真实存在、契合口味、**主体是用户很可能没听过**的（familiarity 多数取 likely-unheard）；新旧 release 不限。
- 尽量**换新艺人**，别老推这些池中已有的艺人：{", ".join(sorted(set(avoid_artists))[:150])}
- 每首过滤：有旋律、不踩黑名单（EDM/dubstep/metal/hyperpop/math rock 炫技/jazz fusion 炫技/只有氛围没旋律的 ambient 等）、制作美学吻合。
- 绝不编造。拿不准是否真实存在就不要放。
- 三段中文文案严格按文笔圣经：具体压过抽象、画面压过形容词、术语接人话、避开陈词黑名单，why≤2 句。

# 只输出 JSON 数组（无解释、无 markdown 代码围栏）
[{{"title":"","artist":"","year":"","album":"","genres":[],"mood_tags":[],"production_tags":[],"vocal_style":"","has_melody":true,"familiarity":"likely-unheard","scene":"","artist_oneliner":"","why":"","source":"","source_url":""}}]
"""
    msg = client.messages.create(
        model=model, max_tokens=16000, system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    i, j = text.find("["), text.rfind("]")
    if i < 0 or j < 0:
        raise SystemExit(f"LLM 未返回 JSON 数组：{text[:200]}")
    return json.loads(text[i:j + 1])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-fresh", type=int, default=40, help="未发存量低于此值才补池")
    ap.add_argument("--add", type=int, default=40, help="每次向 LLM 要多少首候选")
    ap.add_argument("--force", action="store_true", help="无视阈值强制补")
    args = ap.parse_args()

    pool = json.loads((DATA / "pool.json").read_text(encoding="utf-8"))
    hist_path = DATA / "history.json"
    history = json.loads(hist_path.read_text(encoding="utf-8")) if hist_path.exists() else {}

    fresh = unsent_count(pool, history)
    print(f"当前未发存量 {fresh}（阈值 {args.min_fresh}）")
    if fresh >= args.min_fresh and not args.force:
        print("存量充足，跳过补池（不花 API）")
        return

    profile = (DOCS / "profile.md").read_text(encoding="utf-8")
    bible = (DOCS / "style_bible.md").read_text(encoding="utf-8")
    model = os.environ.get("MD_MODEL", "claude-sonnet-5")
    avoid = [t.get("artist", "") for t in pool]
    print(f"调用 {model} 发现 {args.add} 首候选…")
    cand = call_llm(profile, bible, avoid, args.add, model)
    print(f"LLM 返回候选 {len(cand)}，开始 iTunes 验真 + 去重…")

    seen = {_norm(t["title"]) + "|" + _norm(t["artist"]) for t in pool}
    cache = itunes.load_cache()
    today = dt.datetime.now(dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d")
    added = dropped_dup = dropped_fake = 0
    for t in cand:
        k = _norm(t.get("title")) + "|" + _norm(t.get("artist"))
        if not k.strip("|"):
            continue
        if k in seen:
            dropped_dup += 1
            continue
        info = itunes.lookup(t.get("artist", ""), t.get("title", ""), cache)
        if not info.get("found"):  # 验不到 = 可能幻觉，弃
            dropped_fake += 1
            continue
        seen.add(k)
        st = _stars(t.get("genres"))
        fam = t.get("familiarity", "likely-unheard")
        fit = 0.70 + 0.05 * (st - 3) + (0.06 if fam == "likely-unheard" else 0.0 if fam == "possibly-known" else -0.05)
        pool.append({
            "id": f"d-{_norm(t['artist'])[:12]}-{_norm(t['title'])[:16]}",
            "title": t.get("title", ""), "artist": t.get("artist", ""),
            "year": t.get("year", ""), "album": t.get("album", ""),
            "genres": t.get("genres", []), "genre_stars": st,
            "mood_tags": t.get("mood_tags", []), "production_tags": t.get("production_tags", []),
            "instrumentation": [], "vocal_style": t.get("vocal_style", ""),
            "bpm_band": "70–120", "has_melody": t.get("has_melody", True),
            "familiarity": fam, "scene": t.get("scene", ""),
            "artist_oneliner": t.get("artist_oneliner", ""), "why": t.get("why", ""),
            "fit_score": round(min(fit, 0.95), 3),
            "source": t.get("source", ""), "source_url": t.get("source_url", ""),
            "added_date": today,
        })
        added += 1

    itunes.save_cache(cache)
    (DATA / "pool.json").write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"补池 +{added}（重复弃 {dropped_dup} · iTunes 验不到弃 {dropped_fake}）→ 池现共 {len(pool)} 首")


if __name__ == "__main__":
    main()
