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
import os
import re
import sys
from pathlib import Path

import itunes
import migrate_catalog as mc
import picker
import validate_candidates as vc

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CAND = ROOT / "candidates"
QUAR = ROOT / "quarantine"
REPORTS = ROOT / "reports" / "merge"

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
    """状态路由：schema→canonical去重→黑名单→iTunes精确匹配。exact/acceptable 入库；
    version/artist/album/not_found 入 quarantine；transient_error 整批 fail-closed。"""
    seen = {t.get("id") for t in pool if t.get("id")}
    cache = itunes.load_cache() if validate else {}
    today = dt.datetime.now(dt.timezone.utc).astimezone(
        dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d")
    c = {"input": len(cands), "schema_valid": 0, "exact_match": 0, "acceptable_match": 0,
         "duplicates": 0, "version_mismatch": 0, "artist_mismatch": 0, "album_mismatch": 0,
         "not_found": 0, "blacklist": 0, "transient_error": 0, "added": 0}
    quarantined: list[dict] = []
    transient = False

    valid, invalids = vc.validate_batch(cands, pool)
    c["schema_valid"] = len(valid)
    for iv in invalids:
        tk = iv["track"]
        quarantined.append({"title": tk.get("title"), "artist": tk.get("artist"),
                            "reason": "schema", "detail": iv["errors"]})

    for t in valid:
        title, artist = t["title"].strip(), t["artist"].strip()
        apple_tid = str(t.get("apple_track_id") or "")
        cid = mc.canonical_id({"artist": artist, "title": title,
                               "album": t.get("album", ""), "apple_track_id": apple_tid})
        if cid in seen:
            c["duplicates"] += 1
            quarantined.append({"title": title, "artist": artist, "reason": "duplicate"})
            continue
        if {g.lower() for g in (t.get("genres") or [])} & picker.BLACKLIST:
            c["blacklist"] += 1
            quarantined.append({"title": title, "artist": artist, "reason": "blacklist"})
            continue
        year, coll_id = t.get("year", ""), str(t.get("apple_collection_id") or "")
        if validate:
            info = itunes.lookup(artist, title, cache, album=t.get("album", ""))
            status = info["status"]
            if status == "transient_error":
                transient = True
                break  # fail-closed：不写盘、不删候选、下次重试
            if status not in itunes.ACCEPT:
                c[status] = c.get(status, 0) + 1
                quarantined.append({"title": title, "artist": artist, "reason": status,
                                    "matched": info.get("matched_title", ""),
                                    "matched_artist": info.get("matched_artist", "")})
                continue
            c[status] += 1
            apple_tid = str(info.get("track_id") or apple_tid)
            if apple_tid:
                cid = f"apple:{apple_tid}"
                if cid in seen:
                    c["duplicates"] += 1
                    quarantined.append({"title": title, "artist": artist, "reason": "duplicate"})
                    continue
            ry = str(info.get("release_year") or "")
            if re.fullmatch(r"\d{4}", ry):
                year = ry  # 用 iTunes 收录专辑发行年（更权威）
            coll_id = str(info.get("collection_id") or coll_id)
        seen.add(cid)
        st = _stars(t.get("genres"))
        fam = t.get("familiarity", "likely-unheard")
        pool.append({
            "id": cid, "title": title, "artist": artist,
            "artist_display": artist, "title_display": title,
            "artist_key": mc.keyify(artist), "title_key": mc.keyify(title),
            "version": mc.detect_version(title), "album_key": mc.keyify(t.get("album", "")),
            "apple_track_id": apple_tid, "apple_collection_id": coll_id, "legacy_ids": [],
            "year": year, "album": t.get("album", ""),
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
        c["added"] += 1
    if validate:
        itunes.save_cache(cache)
    c["quarantined"] = len(quarantined)
    return pool, {"counts": c, "quarantined": quarantined, "transient": transient}


def cmd_context() -> None:
    pool = _load_pool()
    arts = sorted({t["artist"] for t in pool})
    print(f"# 当前池已有 {len(pool)} 首 / {len(arts)} 位艺人——补新曲时请尽量避开这些艺人：\n")
    print(" · ".join(arts))


def _step_summary(md: str) -> None:
    p = os.environ.get("GITHUB_STEP_SUMMARY")
    if p:
        with open(p, "a", encoding="utf-8") as f:
            f.write(md + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="候选 JSON 文件；留空=处理 candidates/*.json")
    ap.add_argument("--context", action="store_true", help="打印当前池已有艺人清单")
    ap.add_argument("--dry-run", action="store_true", help="只验真+分类、不写盘")
    ap.add_argument("--keep", action="store_true", help="不删除处理过的 candidates 文件")
    args = ap.parse_args()

    if args.context:
        cmd_context()
        return 0

    paths = [Path(p) for p in args.files] if args.files else sorted(CAND.glob("*.json"))
    paths = [p for p in paths if p.exists()]
    if not paths:
        print("没有候选文件可处理（candidates/ 为空）。")
        return 0

    cands: list[dict] = []
    for p in paths:
        got = parse_candidates(p.read_text(encoding="utf-8"))
        print(f"读入 {p.name}: {len(got)} 条")
        cands += got

    pool = _load_pool()
    before = len(pool)
    pool, rep = merge(cands, pool, validate=True)
    c = rep["counts"]
    line = (f"input {c['input']} · schema_valid {c['schema_valid']} · exact {c['exact_match']}"
            f"+accept {c['acceptable_match']} · dup {c['duplicates']} · version_mismatch {c['version_mismatch']}"
            f" · artist_mismatch {c['artist_mismatch']} · not_found {c['not_found']} · blacklist {c['blacklist']}"
            f" · added {c['added']} → 池 {before}→{len(pool)}")
    print(line)

    if rep["transient"]:
        print("❌ transient_error（网络/限流）：整批 fail-closed——不写盘、不删候选，下次重试。")
        _step_summary("### ⚠️ merge FAILED (transient_error) — 候选保留待重试\n\n" + line)
        return 2

    if args.dry_run:
        print("(--dry-run，未写盘)")
        for q in rep["quarantined"][:30]:
            print("  quarantine:", q.get("reason"), "|", q.get("artist"), "-", q.get("title"),
                  ("→ " + q.get("matched", "")) if q.get("matched") else "")
        return 0

    today = dt.datetime.now(dt.timezone.utc).astimezone(
        dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d")
    (DATA / "pool.json").write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")
    if rep["quarantined"]:
        QUAR.mkdir(parents=True, exist_ok=True)
        (QUAR / f"{today}.json").write_text(
            json.dumps(rep["quarantined"], ensure_ascii=False, indent=2), encoding="utf-8")
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"{today}.json").write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    _step_summary(f"### merge report {today}\n\n```json\n{json.dumps(c, ensure_ascii=False, indent=2)}\n```")
    if not args.keep:  # 仅成功、非 transient 时删除已处理候选
        for p in paths:
            if CAND in p.resolve().parents:
                p.unlink()
                print(f"已清除已处理的 {p.name}")
    print(f"::added::{c['added']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
