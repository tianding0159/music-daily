"""把任意 LLM（ChatGPT / Claude / …）产出的候选曲目 JSON 合并进 pool.json。

与内置补池同一条管线（LLM 无关）：iTunes 验真（查不到=可能幻觉，丢弃）→ 归一化去重
→ 计算 genre_stars/fit_score/familiarity 加权 → append 进 pool.json。

用法：
  python3 scripts/merge_candidates.py                    # 处理 candidates/ 下所有 *.json（CI 默认）
  python3 scripts/merge_candidates.py path/to/new.json   # 处理指定文件
  python3 scripts/merge_candidates.py --context          # 打印当前池"已有艺人"，喂给 LLM 避免重复
  python3 scripts/merge_candidates.py --dry-run f.json   # 只验真+去重、不写盘（预览）

接受的 JSON：裸数组 / {"tracks":[...]} / {"items":[...]}；容忍 ```json 代码围栏。
处理成功后会删除 candidates/ 下的输入文件（--keep 保留）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import itunes
import migrate_catalog as mc
import picker

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CAND = ROOT / "candidates"

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


# 版本词：iTunes 命中的标题若含这些、而候选标题未声明 → 交付的是另一录音版本，剔除
VERSION_WORDS = ("remix", "remixed", "live", "remaster", "remastered", "rework",
                 "re recorded", "re recording", "acoustic", "instrumental", "demo",
                 "reprise", "radio edit", "single edit", "extended", "rerecorded")


def _version_mismatch(cand_title: str, matched_title: str) -> str | None:
    """候选是原版、iTunes 却给了 remix/live/remaster 等 → 返回命中的版本词，否则 None。"""
    c = " " + _norm(cand_title) + " "
    m = " " + _norm(matched_title) + " "
    for w in VERSION_WORDS:
        wn = _norm(w)
        if wn in m and wn not in c:
            return w
    return None


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


def _load_pool() -> list[dict]:
    return json.loads((DATA / "pool.json").read_text(encoding="utf-8"))


def parse_candidates(text: str) -> list[dict]:
    """容忍代码围栏 / 外层对象，抽出曲目数组。"""
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    # 容错：LLM/聊天常把直引号变成弯引号，会让 JSON 解析失败——归一化回直引号
    t = t.translate(str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"}))
    try:
        v = json.loads(t)
    except json.JSONDecodeError:
        i, j = t.find("["), t.rfind("]")
        if i < 0 or j < 0:
            return []
        v = json.loads(t[i:j + 1])
    if isinstance(v, dict):
        v = v.get("tracks") or v.get("items") or []
    return v if isinstance(v, list) else []


_FAM_ADJ = {"likely-unheard": 6, "possibly-known": 0, "classic-known": -5}


def _fit_score(genre_stars: int, familiarity: str) -> float:
    """百分制 0..95：基线 70 + 流派档位 + 熟悉度方向。绝不写 0..1。"""
    fit = 70 + 5 * (genre_stars - 3) + _FAM_ADJ.get(familiarity, 0)
    return round(min(max(fit, 0), 95), 1)


def merge(cands: list[dict], pool: list[dict], validate: bool = True) -> tuple[list[dict], dict]:
    seen = {t.get("id") for t in pool if t.get("id")}  # 现有 canonical id
    cache = itunes.load_cache() if validate else {}
    today = dt.datetime.now(dt.timezone.utc).astimezone(
        dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d")
    added = dup = fake = badgenre = verdrop = 0
    for t in cands:
        title, artist = (t.get("title") or "").strip(), (t.get("artist") or "").strip()
        if not title or not artist:
            continue
        apple_tid = str(t.get("apple_track_id") or "")
        cid = mc.canonical_id({"artist": artist, "title": title,
                               "album": t.get("album", ""), "apple_track_id": apple_tid})
        if cid in seen:
            dup += 1
            continue
        if {g.lower() for g in (t.get("genres") or [])} & picker.BLACKLIST:
            badgenre += 1
            continue
        if validate:
            info = itunes.lookup(artist, title, cache)
            if not info.get("found"):
                fake += 1
                continue
            if _version_mismatch(title, info.get("matched_title", "")):
                verdrop += 1
                continue
            apple_tid = str(info.get("track_id") or apple_tid)  # P1-6 起 iTunes 会带 trackId
            if apple_tid:
                cid = f"apple:{apple_tid}"
                if cid in seen:
                    dup += 1
                    continue
        seen.add(cid)
        st = _stars(t.get("genres"))
        fam = t.get("familiarity", "likely-unheard")
        pool.append({
            "id": cid,
            "title": title, "artist": artist,
            "artist_display": artist, "title_display": title,
            "artist_key": mc.keyify(artist), "title_key": mc.keyify(title),
            "version": mc.detect_version(title), "album_key": mc.keyify(t.get("album", "")),
            "apple_track_id": apple_tid, "apple_collection_id": str(t.get("apple_collection_id") or ""),
            "legacy_ids": [],
            "year": t.get("year", ""), "album": t.get("album", ""),
            "genres": t.get("genres", []), "genre_stars": st,
            "mood_tags": t.get("mood_tags", []), "production_tags": t.get("production_tags", []),
            "instrumentation": t.get("instrumentation", []), "vocal_style": t.get("vocal_style", ""),
            "bpm_band": t.get("bpm_band", "70–120"), "has_melody": t.get("has_melody", True),
            "familiarity": fam, "scene": t.get("scene", ""),
            "artist_oneliner": t.get("artist_oneliner", ""), "why": t.get("why", ""),
            "fit_score": _fit_score(st, fam),
            "source": t.get("source", ""), "source_url": t.get("source_url", ""),
            "added_date": today,
        })
        added += 1
    if validate:
        itunes.save_cache(cache)
    return pool, {"added": added, "dup": dup, "fake": fake, "badgenre": badgenre, "verdrop": verdrop}


def cmd_context() -> None:
    pool = _load_pool()
    arts = sorted({t["artist"] for t in pool})
    print(f"# 当前池已有 {len(pool)} 首 / {len(arts)} 位艺人——补新曲时请尽量避开这些艺人：\n")
    print(" · ".join(arts))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="候选 JSON 文件；留空=处理 candidates/*.json")
    ap.add_argument("--context", action="store_true", help="打印当前池已有艺人清单")
    ap.add_argument("--dry-run", action="store_true", help="只验真+去重、不写盘")
    ap.add_argument("--keep", action="store_true", help="不删除处理过的 candidates 文件")
    args = ap.parse_args()

    if args.context:
        cmd_context()
        return

    paths = [Path(p) for p in args.files] if args.files else sorted(CAND.glob("*.json"))
    paths = [p for p in paths if p.exists()]
    if not paths:
        print("没有候选文件可处理（candidates/ 为空）。")
        return

    cands: list[dict] = []
    for p in paths:
        got = parse_candidates(p.read_text(encoding="utf-8"))
        print(f"读入 {p.name}: {len(got)} 条")
        cands += got

    pool = _load_pool()
    before = len(pool)
    pool, stats = merge(cands, pool, validate=True)
    print(f"结果：+{stats['added']} 首（重复 {stats['dup']} · iTunes 验不到 {stats['fake']} · "
          f"版本错配 {stats['verdrop']} · 黑名单流派 {stats['badgenre']}）→ 池 {before} → {len(pool)}")

    if args.dry_run:
        print("(--dry-run，未写盘)")
        return

    (DATA / "pool.json").write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.keep:
        for p in paths:
            if CAND in p.resolve().parents:
                p.unlink()
                print(f"已清除已处理的 {p.name}")
    # 供 CI 判断是否需要提交
    print(f"::added::{stats['added']}")


if __name__ == "__main__":
    sys.exit(main())
