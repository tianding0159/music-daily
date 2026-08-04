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



# 版本错配的判据【只在 itunes.classify()】——这里曾有一份 _version_mismatch +
# VERSION_WORDS 副本，零生产调用、只被一条测试保活，且两张词表已双向分叉
# （itunes 多 cover/edit/karaoke/mix/version，这边多 re recording）。
# 那条测试给的是「版本错配已覆盖」的假保证，实际覆盖的是死代码。2026-08-04 审计删。


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


def _load_json_lenient(text: str):
    """容忍代码围栏 / 弯引号，返回解析后的对象或数组。"""
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    # 容错：LLM/聊天常把直引号变成弯引号，会让 JSON 解析失败——归一化回直引号
    t = t.translate(str.maketrans({"\u201c": '"', "\u201d": '"',
                                   "\u2018": "'", "\u2019": "'"}))
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    for op, cl in (("{", "}"), ("[", "]")):
        i, j = t.find(op), t.rfind(cl)
        if i >= 0 and j > i:
            try:
                return json.loads(t[i:j + 1])
            except json.JSONDecodeError:
                continue
    return None


def parse_candidates(text: str) -> list[dict]:
    """抽出曲目数组。兼容三种外形：裸数组 / {"tracks":[...]} / {"items":[...]}。"""
    v = _load_json_lenient(text)
    if isinstance(v, dict):
        v = v.get("tracks") or v.get("items") or []
    return v if isinstance(v, list) else []


def parse_artists(text: str) -> list[dict]:
    """抽出同一份文件里的艺人简介数组（新格式）。

    2026-08-03 起补库与写 bio 合成一次交付：候选文件顶层是对象，
    `tracks` 放曲目、`artists` 放这批新艺人的简介，用户只上传一次。
    裸数组（旧格式）读到的 artists 为空 —— 那种文件里的艺人必须早已在库。
    """
    v = _load_json_lenient(text)
    if isinstance(v, dict):
        a = v.get("artists") or v.get("bios") or []
        return a if isinstance(a, list) else []
    return []


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
         "duplicates": 0, "version_mismatch": 0, "artist_mismatch": 0,
         # 不再预置 album_mismatch —— 它恒为 0，而「0」在报告里读起来像
         # 「专辑维度查过了没问题」，实际是「从来没检查过」。这两件事看起来一样，
         # 所以宁可让字段缺席。计数用 c.get(status,0)+1，不依赖预置键。
         # 改为记录 year_differs：候选 year 与 iTunes 匹中年份不一致的条数，
         # 这个数字是真的有人在算。
         "not_found": 0, "blacklist": 0, "transient_error": 0, "added": 0}
    quarantined: list[dict] = []
    transient = False

    valid, invalids = vc.validate_batch(cands)
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
            info = itunes.lookup(artist, title, cache)
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
            # 【不再用 iTunes 年份覆盖候选 year】。
            # 原注释写「更权威」，但这条匹配是在**没有任何专辑约束**下选出的
            # （lookup 的 album 参数从不参与匹配、缓存键只有 artist|title），
            # 于是卡片上的「年份 / 专辑」可以来自两张不同的唱片：
            # 实测 The Style Council《You're the Best Thing》存成
            # year=2020 / album='Café Bleu' —— Café Bleu 是 1984 年的专辑，
            # 2020 来自匹到的合辑 Long Hot Summers。池里 167 首受影响、26 首已发布。
            #
            # 现在保留候选 year（与 album 同源，至少自洽），iTunes 的另存
            # matched_release_year 供人工核，差异进 warn。
            # 不改成「collection 与候选 album 一致才采信」—— 那个判据假阳性率很高
            # （& vs and、Deluxe/Remaster、原专辑没上架只有合辑），会把年份来源从
            # 「iTunes 匹中发行版」换成「LLM 自报」，即从「错得可查」变「错得不可查」。
            ry = str(info.get("release_year") or "")
            matched_year = ry if re.fullmatch(r"\d{4}", ry) else ""
            if matched_year and year and matched_year != str(year):
                c.setdefault("year_differs", 0)
                c["year_differs"] += 1
                quarantined.append({
                    "title": title, "artist": artist, "reason": "year_differs_kept_candidate",
                    "candidate_year": str(year), "matched_release_year": matched_year,
                    "candidate_album": t.get("album", ""),
                    "matched_collection": info.get("collection_name", ""),
                })
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
            # iTunes 匹中发行版的年份，仅供核对：它与 album 可能不是同一张唱片
            # （见上方 year 那段注释）。渲染层只印 year，不印这个。
            "matched_release_year": matched_year if info else "",
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


def _apply_bios(bios: list[dict], added_artists: set[str],
                write: bool = True) -> tuple[int, str]:
    """校验并写入本批附带的艺人简介。返回 (退出码, 报告文本)，0 = 通过。

    两件事，缺一不可：
    ① **覆盖**：入库曲目的艺人若不在 artists.json，本批必须给它 bio。
       不强制的话覆盖率会从 100% 悄悄下滑，而且是静默的（页面只是少一段字）。
    ② **质量**：bio 本身的校验【整个委托给 import_bios.audit()】——
       SHA 不在这层；编码已由 main() 在读文件后、解析前用 import_bios.check_encoding 校验过（2026-08-04 补上，此前这句是假断言），但合同、黑名单、
       让人令人、地名、汉字间空格、覆盖已有内容等判据必须与专用通道完全一致。
       在这里重写一份必然与那边漂移（见 memory parallel-paths-drift-silently）。
    """
    sys.path.insert(0, str(ROOT / "tools"))
    import import_bios                                   # noqa: PLC0415

    have = {a["artist"] for a in import_bios.load_artists()}
    given = {b.get("artist", "") for b in bios if isinstance(b, dict)}
    missing = sorted(a for a in added_artists if a and a not in have and a not in given)

    out = []
    if bios:
        rep = import_bios.audit(bios, extra_artists=added_artists)
        m = rep["metrics"]
        out.append(f"艺人简介 {rep['input']} 条 → 可接受 {m['accepted']} 条"
                   f"（长度 {m['len_min']}–{m['len_max']}，low conf {m['low_conf']}）")
        out += [f"  [skip] {x}" for x in rep["skipped"]]
        out += [f"  [warn] {x}" for x in rep["warn"]]
        out += [f"  [P0]   {x}" for x in rep["p0"]]
        if rep["p0"]:
            return 1, "\n".join(out)
        if rep["warn"]:
            out.append("  ↑ 有告警，本批不写盘。修好重传（补库通道不提供 --force，"
                       "因为它同时会动 pool，风险面比纯 bio 通道大）。")
            return 1, "\n".join(out)

    if missing:
        out.append(f"❌ {len(missing)} 位新艺人没有简介 —— 本批必须一起给："
                   f"\n     " + "\n     ".join(missing))
        out.append("   （规则：入库曲目的艺人不在库里，就要在同一份文件的 "
                   "\"artists\" 里带上简介）")
        return 1, "\n".join(out)

    if bios and not write:
        out.append(f"（--dry-run，未写盘；将写入 {len(rep['ok'])} 条简介）")
        return 0, "\n".join(out)
    if bios:
        n, total = import_bios.apply(rep["ok"])
        pa = len({t.get("artist") for t in _load_pool()})
        out.append(f"✅ 写入简介 {n} 条 → 共 {total} 位（池内艺人 {pa} 位，"
                   f"覆盖 {100*total/max(pa,1):.1f}%）")
    elif added_artists:
        out.append(f"本批 {len(added_artists)} 位艺人都已有简介，无需新增 ✓")
    return 0, "\n".join(out)


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

    # 编码检测必须在【解析之前】—— 损坏的中文仍是合法 JSON，等解析完就晚了。
    # 补库通道此前完全没有这道闸（全仓 check_encoding 只在 inbox/bios 专用通道用），
    # 而 cp1252 化的候选能零错误通过全部校验：`。` 变 `ã€‚` 使「why 超过两句」
    # 失效、len(scene) 只管下限、mood_tags 是 ASCII、黑名单是中文匹不上，
    # iTunes 也因 title/artist 是 ASCII 照样 exact_match（2026-08-04 审计实测）。
    # 真正裸奔的是 0-新艺人批次（salvage 重传 / 已知艺人补曲）：不走 bio 校验，
    # 损坏静默入库并 commit。这类批次真实发生过（reports/merge/2026-08-03-salvage）。
    sys.path.insert(0, str(ROOT / "tools"))
    import import_bios as _ib                       # noqa: PLC0415

    cands: list[dict] = []
    bios: list[dict] = []
    for p in paths:
        txt = p.read_text(encoding="utf-8")
        enc_errs = _ib.check_encoding(txt)
        if enc_errs:
            print(f"❌ {p.name} 编码损坏：{enc_errs[0]}")
            print("   请让上游用 json.dumps(..., ensure_ascii=True) 重发。")
            print("   不写盘、不删候选。")
            _step_summary(f"### ⚠️ merge FAILED（编码损坏）\n\n`{p.name}`：{enc_errs[0]}")
            # rc=4 是新码。**绝不能用 2** —— 那是 transient，微信会推
            # 「不用管，下次自动重试」，而编码损坏每次重试都同样失败，
            # 等于把硬失败伪装成可忽略的抖动。
            return 4
        got, gb = parse_candidates(txt), parse_artists(txt)
        print(f"读入 {p.name}: 曲目 {len(got)} 条" + (f" · 艺人简介 {len(gb)} 条" if gb else ""))
        cands += got
        bios += gb

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

    # ── 艺人简介：与曲目同一次交付、同一个文件 ────────────────────────
    # 判据：**真正入库的曲目里，凡艺人不在 artists.json，就必须在本文件里带 bio**。
    # 缺一条就整批不写盘 —— 否则覆盖率会从 100% 悄悄掉下来，而且掉了没人会发现
    # （页面上只是少一段简介，不报错，属于典型的静默退化）。
    # bio 内容校验完全委托 import_bios.audit()，不在这里另造判据（两套必然漂移）。
    #
    # 位置刻意放在 --dry-run 之前：体检模式必须能验出「新艺人缺 bio」，
    # 否则本地 --dry-run 全绿、传上去才被拒，白跑一趟。
    # dry-run 下只报告不写盘（_apply_bios 收到 write=False）。
    added_artists = {t.get("artist", "") for t in pool[before:]}
    if added_artists or bios:
        rc, msg = _apply_bios(bios, added_artists, write=not args.dry_run)
        print(msg)
        if rc:
            print("❌ 艺人简介不合格：不写盘、不删候选，修好重传。")
            _step_summary("### ⚠️ merge FAILED（艺人简介）— 候选保留待修正\n\n"
                          + line + "\n\n```\n" + msg + "\n```")
            return 3

    if args.dry_run:
        print("(--dry-run，未写盘)")
        for q in rep["quarantined"][:30]:
            print("  quarantine:", q.get("reason"), "|", q.get("artist"), "-", q.get("title"),
                  ("→ " + q.get("matched", "")) if q.get("matched") else "")
        return 0

    now = dt.datetime.now(dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(hours=8)))
    today = now.strftime("%Y-%m-%d")
    # 报告/隔离用「候选文件名」做唯一运行标识（单文件上传时），多文件混合才退回时间戳——
    # 保证同一天先跑 canary 再跑补库不会互相覆盖，canary 证据永久留存、可回溯到具体输入。
    run_id = paths[0].stem if len(paths) == 1 else f"{today}-{now.strftime('%H%M%S')}"
    report_obj = {**c, "run_id": run_id, "candidates": [p.name for p in paths],
                  "generated_at": now.isoformat(timespec="seconds")}
    (DATA / "pool.json").write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")
    if rep["quarantined"]:
        QUAR.mkdir(parents=True, exist_ok=True)
        (QUAR / f"{run_id}.json").write_text(
            json.dumps(rep["quarantined"], ensure_ascii=False, indent=2), encoding="utf-8")
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"{run_id}.json").write_text(json.dumps(report_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    _step_summary(f"### merge report {run_id}\n\n```json\n{json.dumps(report_obj, ensure_ascii=False, indent=2)}\n```")
    if not args.keep:  # 仅成功、非 transient 时删除已处理候选
        for p in paths:
            if CAND in p.resolve().parents:
                p.unlink()
                print(f"已清除已处理的 {p.name}")
    print(f"::added::{c['added']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
