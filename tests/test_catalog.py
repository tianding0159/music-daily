"""离线确定性测试（无需网络/pytest）。运行：python3 tests/test_catalog.py

覆盖：pool 数据完整性、canonical id 稳定性/去重、版本错配检测、fit 百分制、
黑名单过滤、picker 同一天稳定 + 去重、文案口径护栏（copy_check）。
任一失败 → 退出码 1。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import copy_check  # noqa: E402
import itunes  # noqa: E402
import merge_candidates as mcand  # noqa: E402
import migrate_catalog as mc  # noqa: E402
import picker  # noqa: E402
import validate_candidates as vc  # noqa: E402


def _good_cand(**over):
    t = {"title": "So Many Details", "artist": "Toro y Moi", "year": "2013",
         "album": "Anything in Return", "genres": ["indietronica", "dream pop"],
         "mood_tags": ["late night", "grainy"], "production_tags": ["soft compression"],
         "instrumentation": ["synth"], "vocal_style": "气声", "bpm_band": "90–100",
         "has_melody": True, "familiarity": "likely-unheard",
         "scene": "深夜末班地铁靠窗，玻璃把你映成陌生人的那十分钟",
         "artist_oneliner": "南加州 chillwave 代表人物之一", "why": "合成器铺出雾面，人声浮在上面。",
         "source": "Bandcamp", "source_url": "https://example.com/x"}
    t.update(over)
    return t


def test_itunes_classify_statuses():
    assert itunes.classify("Bibio", "Lovers' Carvings",
                           [{"artistName": "Bibio", "trackName": "Lovers' Carvings"}])[0] == "exact_match"
    assert itunes.classify("aus", "Halo",
                           [{"artistName": "Aus", "trackName": "Halo (Ulrich Schnauss Remix of Aus)"}])[0] == "version_mismatch"
    assert itunes.classify("aus", "Halo",
                           [{"artistName": "Beyoncé", "trackName": "Halo"}])[0] == "artist_mismatch"
    assert itunes.classify("X", "Y", [{"artistName": "Z", "trackName": "W"}])[0] == "not_found"
    assert itunes.classify("Beach House", "Space Song",
                           [{"artistName": "Beach House feat. Q", "trackName": "Space Song"}])[0] == "acceptable_match"


def test_validate_track_good_and_bad():
    assert vc.validate_track(_good_cand()) == []
    assert vc.validate_track(_good_cand(year="2010s"))
    assert vc.validate_track(_good_cand(has_melody=False))
    assert vc.validate_track(_good_cand(familiarity="unknown"))
    assert vc.validate_track(_good_cand(source_url="http://x"))
    assert vc.validate_track(_good_cand(scene="通勤时听"))
    assert vc.validate_track(_good_cand(bpm_band="fast"))


def test_validate_batch_caps():
    classic = [_good_cand(artist=f"A{i}", title=f"T{i}", familiarity="classic-known") for i in range(4)]
    valid, invalid = vc.validate_batch(classic)
    assert len(valid) == 2 and len(invalid) == 2  # classic-known 全批最多 2
    same = [_good_cand(artist="Solo", title=f"S{i}") for i in range(5)]
    valid2, invalid2 = vc.validate_batch(same)
    assert len(valid2) == 3  # 单艺人最多 3/批

POOL = json.loads((ROOT / "data" / "pool.json").read_text(encoding="utf-8"))
HISTORY = json.loads((ROOT / "data" / "history.json").read_text(encoding="utf-8"))


def test_pool_parses_and_nonempty():
    assert isinstance(POOL, list) and len(POOL) > 0


def test_ids_unique():
    ids = [t["id"] for t in POOL]
    assert len(ids) == len(set(ids)), "pool 存在重复 id"


def test_fit_all_0_100():
    for t in POOL:
        f = t.get("fit_score")
        assert isinstance(f, (int, float)) and 0 <= f <= 100, f"fit 越界: {t['id']}={f}"


def test_years_four_digit():
    for t in POOL:
        y = t.get("year")
        if y:
            assert len(str(y)) == 4 and str(y).isdigit(), f"year 非法: {t['id']}={y}"


def test_canonical_fields_present():
    for t in POOL:
        for c in ("artist_key", "title_key", "version", "album_key", "legacy_ids"):
            assert c in t, f"{t['id']} 缺 canonical 字段 {c}"


def test_history_ids_exist():
    pool_ids = {t["id"] for t in POOL}
    for date, ids in HISTORY.items():
        for i in ids:
            assert i in pool_ids, f"history[{date}] 指向不存在 id {i}"


def test_canonical_id_stable_and_variant_merges():
    a = mc.canonical_id({"artist": "Takako Minekawa", "title": "Milk Rock", "album": "Cloudy Cloud Calculator"})
    b = mc.canonical_id({"artist": "Takako Minekawa (嶺川貴子)", "title": "Milk Rock", "album": "Cloudy Cloud Calculator"})
    assert a == b, "括号变体艺人名应归并为同一 canonical id"
    c = mc.canonical_id({"artist": "Takako Minekawa", "title": "Different Song", "album": "X"})
    assert a != c
    d = mc.canonical_id({"artist": "X", "title": "Y", "album": "Z", "apple_track_id": "123"})
    assert d == "apple:123", "有 apple id 时应优先用 apple:<id>"


def test_version_mismatch_detected():
    assert mcand._version_mismatch("Halo", "Halo (Ulrich Schnauss Remix of Aus)")
    assert not mcand._version_mismatch("Halo", "Halo")
    assert mcand._version_mismatch("Song", "Song (Live)")
    assert not mcand._version_mismatch("Live Forever", "Live Forever")  # 主标题含 live 但两边都有→不算错配


def test_fit_score_scale_and_direction():
    hi = mcand._fit_score(5, "likely-unheard")
    lo = mcand._fit_score(3, "classic-known")
    assert 0 <= lo <= hi <= 95
    assert hi > lo


def test_blacklist_filtered_in_merge():
    cands = [_good_cand(artist="ZZBlack", title="EDM Thing", genres=["festival edm"])]
    _, rep = mcand.merge(cands, [dict(t) for t in POOL], validate=False)
    assert rep["counts"]["blacklist"] == 1 and rep["counts"]["added"] == 0


def test_picker_deterministic_and_dedup():
    a = [t["id"] for t in picker.select_daily([dict(x) for x in POOL], HISTORY, "2026-08-10", 20)]
    b = [t["id"] for t in picker.select_daily([dict(x) for x in POOL], HISTORY, "2026-08-10", 20)]
    assert a == b, "同一天选曲应确定性一致"
    assert len(a) == len(set(a)), "同一期不应重复"


def test_picker_no_dup_artist_or_album_in_issue():
    picks = picker.select_daily([dict(x) for x in POOL], HISTORY, "2026-08-11", 30)
    aks = [t.get("artist_key") for t in picks]
    alks = [t.get("album_key") for t in picks if t.get("album_key")]
    assert len(aks) == len(set(aks)), "同一期出现重复艺人"
    assert len(alks) == len(set(alks)), "同一期出现重复专辑"


def test_blacklist_never_relaxed_and_melody_required():
    assert not picker.is_eligible({"has_melody": False, "genres": ["dream pop"]})[0]
    assert not picker.is_eligible({"has_melody": True, "genres": ["metal"]})[0]


# ── 文案口径护栏（copy_check）──
# 为什么要测：文案标准以前只活在 style_bible.md 与 commit message 里，
# 结果「声称全量重写」实际只改了一个字段、圣经范例句被原样入库都没人挡住。

def _ok_track(**over):
    t = {"id": "t1", "title": "T", "artist": "A", "year": "2020", "album": "Al",
         "genres": ["dream pop"], "mood_tags": ["tender"], "has_melody": True,
         "familiarity": "likely-unheard", "fit_score": 80, "bpm_band": "70–120",
         "source_url": "https://example.com/a", "source": "bandcamp",
         "production_tags": ["tape"], "instrumentation": ["guitar"], "vocal_style": "soft",
         "artist_oneliner": "布鲁克林的吉他手，指甲刮弦的声音全留在录音里。",
         "why": "吉他磨得起毛，副歌一到全松开。",
         "scene": "等水烧开的两分钟，站在灶台边不想动。"}
    t.update(over)
    return t


def test_copy_blacklist_parsed_from_bible_not_hardcoded():
    bl = copy_check.blacklist()
    assert len(bl) > 30, f"黑名单应从圣经 parse 出几十个词，实际 {len(bl)}"
    assert "慵懒" in bl and "空灵" in bl
    # 「宝藏歌手/专辑」的缩写不能被拆成裸词「专辑」这种中性词
    assert "专辑" not in bl, "『专辑』是中性词，不该进黑名单（曾因拆 / 误报）"
    assert "宝藏专辑" in bl, "缩写应还原成完整词"


def test_copy_catches_blacklist_word():
    p0, _w, _m = copy_check.check_copy([_ok_track(artist_oneliner="一个慵懒的歌手。")])
    assert any("黑名单" in e for e in p0), p0


def test_copy_catches_bible_example_verbatim():
    ex = copy_check.examples()
    assert ex, "应能从圣经 parse 出范例句"
    p0, _w, _m = copy_check.check_copy([_ok_track(scene=ex[0])])
    assert any("范例句" in e for e in p0), p0


def test_copy_catches_cross_track_duplicate():
    a = _ok_track(id="a")
    b = _ok_track(id="b")            # scene 与 a 完全相同
    p0, _w, _m = copy_check.check_copy([a, b])
    assert any("完全重复" in e for e in p0), p0


def test_copy_warns_on_template_concentration():
    # 10 条 oneliner 全用破折号同位语 → 占比 100%，应告警而非 P0
    pool = [_ok_track(id=f"t{i}", artist_oneliner=f"某地某人——做某种声音的第{i}个。",
                      scene=f"第{i}个动作做完，手还停在那里。") for i in range(10)]
    p0, warn, m = copy_check.check_copy(pool)
    assert m["oneliner_dash_pct"] == 100.0, m
    assert any("破折号" in w for w in warn), warn
    assert not any("破折号" in e for e in p0), "模板集中度是告警不是 P0"


def test_copy_clean_track_passes():
    p0, _w, _m = copy_check.check_copy([_ok_track()])
    assert not p0, p0


def test_validate_candidates_rejects_bad_copy():
    errs = vc.validate_track(_ok_track(artist_oneliner="一个慵懒的歌手，声音很治愈。"))
    assert any("黑名单" in e for e in errs), errs
    assert not vc.validate_track(_ok_track()), vc.validate_track(_ok_track())


def test_mood_vocab_is_controlled_and_pool_conforms():
    """mood_tags 必须全部落在受控英文词表内，且候选校验用 CANON 而非别名表做准入。

    别名表(ALIASES)是给历史数据兼容用的，若拿它当白名单，「缺一角」「圆钝」这些
    正要淘汰的旧写法反而会被放行——踩过一次，故固化。
    """
    import mood_vocab

    assert all(m.isascii() for m in mood_vocab.CANON), "受控词须全英文"
    pool = json.loads((ROOT / "data" / "pool.json").read_text(encoding="utf-8"))
    bad = {m for t in pool for m in (t.get("mood_tags") or []) if m not in mood_vocab.CANON}
    assert not bad, f"池里有 {len(bad)} 个表外 mood: {sorted(bad)[:8]}"
    # 别名表里的旧写法必须被候选校验拦下（不能因在 ALIASES 里就放行）
    legacy = next(a for c, alts in mood_vocab.CANON.items() for a in alts if a not in mood_vocab.CANON)
    t = _ok_track()
    t["mood_tags"] = [legacy]
    assert any("受控英文词" in e for e in vc.validate_track(t)), \
        f"旧写法 {legacy!r} 应被拦下，却放行了"


def test_key_strips_accents():
    """_key 必须先剥重音再过滤，否则带重音的字符会被整个删掉。

    「María」旧实现 → 'mara'（í 消失），而 iTunes 返回的「Maria」→ 'maria'，
    两边永远比不上 —— Khruangbin - María También 等曲子因此长期 not_found、
    页面只显示艺人首字母。
    """
    import itunes
    assert itunes._key("María También") == itunes._key("Maria También")
    assert itunes._key("Björk") == itunes._key("Bjork")
    assert itunes._key("Sigur Rós") == itunes._key("Sigur Ros")
    assert itunes._key("日本語") == "日本語"          # 中日文不受影响


def test_artist_keys_accepts_both_scripts():
    """「拉丁名 (原文名)」写法的艺人，括号内外任一都该算命中。"""
    import itunes
    ks = itunes._artist_keys("Ozora Kimijima (君島大空)")
    assert itunes._key("Ozora Kimijima") in ks
    assert itunes._key("君島大空") in ks
    assert itunes._artist_keys("Khruangbin") == {"khruangbin"}


def test_media_only_accepts_verified_matches():
    """页面展示的媒体，来源 status 必须在 itunes.ACCEPT 内。

    只看「有没有 artwork」就采纳会把错版本/错艺人放上页面 —— 库里真出现过 5 首
    （Ride On Time 匹到别人的同名曲、两首落到 Remaster/Live 版）。
    """
    import itunes
    import media_check
    assert "exact_match" in itunes.ACCEPT and "acceptable_match" in itunes.ACCEPT
    assert "version_mismatch" not in itunes.ACCEPT
    assert "artist_mismatch" not in itunes.ACCEPT
    rep = media_check.audit()
    assert not rep["bad_status"], f"页面挂着非 ACCEPT 的媒体：{rep['bad_status'][:3]}"
    assert not rep["missing_entry"], f"media 表缺记录：{len(rep['missing_entry'])} 首"


def test_snapshots_copy_in_sync_with_pool():
    """已生成的 issue 快照，三段文案必须与 pool.json 一致。

    快照不可变、只在生成当天写一次，所以池里改了文案，往期页会永远停在旧版。
    手动回填过一次就漏过一次（rebase 从远端带下来两期新快照，全 30 首停在旧文案，
    线上日报页还挂着 13 处已被判为 AI 味的「…的时候。」）。
    这条测试让滞后自己报警，不靠人记得跑 tools/refresh_snapshot_copy.py。
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "refresh_snapshot_copy", ROOT / "tools" / "refresh_snapshot_copy.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    lag, total = mod.scan()
    assert not lag, (
        f"{len(lag)} 期快照文案滞后于 pool.json（共 {total} 处）："
        f"{[d for d, _, _ in lag]}；跑 python3 tools/refresh_snapshot_copy.py --apply")


def test_media_adoption_uses_accept_not_found():
    """采纳封面/试听的判据必须是 status ∈ itunes.ACCEPT，不能是 found。

    这个 bug 在本项目出现过【四次】（media_check 一次、build_daily 三处），
    所以固化成测试。根子：itunes.lookup 拿不到 exact/acceptable 时会退回
    best_nonexact（version_mismatch / artist_mismatch）而 found 仍为真 ——
    用 found 采纳等于把别人的歌挂上封面和试听。实测缓存 1297 条里 44 条命中，
    含 bigthief|paul 这类 artist_mismatch。

    检法：扫源码里所有「用 info/ent 的 found 做条件、随后取 artwork/preview」
    的地方，要求同一个条件里必须一起出现 ACCEPT。
    """
    import re
    for rel in ["scripts/build_daily.py", "scripts/media_check.py"]:
        src = (ROOT / rel).read_text(encoding="utf-8")
        for m in re.finditer(r"^[^\n#]*\bif\b[^\n]*\bfound\b[^\n]*$", src, re.M):
            line = m.group(0)
            ln = src[:m.start()].count("\n") + 1
            # 取该 if 之后一小段，看是否真的在采纳媒体字段
            after = src[m.end():m.end() + 260]
            adopts = any(k in line + after for k in ('"artwork"', '"preview"', '"apple_url"'))
            if adopts:
                assert "ACCEPT" in line, (
                    f"{rel}:{ln} 用 found 采纳媒体但没查 ACCEPT —— "
                    f"会把 version_mismatch / artist_mismatch 的结果当成命中：\n    {line.strip()}")


def test_workflows_commit_what_scripts_write():
    """每个 workflow 跑的脚本（含它调用的模块）会写的 data/*.json，都必须在 git add 里。

    2026-08-04 一次审计抓到两个同根因的静默 bug：
      · merge.yml 漏 data/artists.json —— 补库带来的简介只写到 runner 磁盘、
        随容器蒸发；合并成功、微信报「+N 首」、Actions 全绿，库里却永远补不上。
      · daily.yml 漏 data/pool_media.json —— 每天增量补的封面/试听全部丢失，
        第二天重查同一批（每首限流 3s），而日报照常出、页面有封面。
    根因是「脚本写了什么」与「workflow 提交了什么」之间没有任何东西在对账。

    实现上踩过的两个坑（都靠负向验证才发现）：
      ① shell 续行：git add 跨行时跨行正则会漏，必须先把 "\\\n" 折平。
      ② **跨模块写入**：merge_candidates 调 import_bios.apply() 才写 artists.json，
         而 ARTISTS 常量定义在 import_bios 里。只扫单文件 = 测试通过但没在检查
         （第一版就是这样：抽掉 merge.yml 的 artists.json 竟然仍全绿）。
         所以这里要顺着 `import xxx` 把被调用的本地模块一起扫。
    """
    import re

    SEARCH_DIRS = ["scripts", "tools"]

    def _resolve(mod):
        for d in SEARCH_DIRS:
            f = ROOT / d / f"{mod}.py"
            if f.exists():
                return f"{d}/{mod}.py"
        return None

    def _written(src_path, entry=None, seen=None):
        """该脚本（含它 import 的本地模块）会写的 data/*.json 集合。"""
        seen = seen if seen is not None else set()
        if src_path in seen:
            return set()
        seen.add(src_path)
        src = (ROOT / src_path).read_text(encoding="utf-8")

        # 认两种常量写法：DATA / "x.json" 和 ROOT / "data" / "x.json"
        consts = {}
        for m in re.finditer(r'^([A-Z_][A-Z_0-9]*)\s*=\s*DATA\s*/\s*"([^"]+)"',
                             src, re.M):
            consts[m.group(1)] = m.group(2)
        for m in re.finditer(
                r'^([A-Z_][A-Z_0-9]*)\s*=\s*ROOT\s*/\s*"data"\s*/\s*"([^"]+)"',
                src, re.M):
            consts[m.group(1)] = m.group(2)

        scope = src
        if entry:
            m = re.search(rf"^def {re.escape(entry)}\(.*?(?=\n(?:def |@|\Z))",
                          src, re.S | re.M)
            assert m, f"{src_path} 里找不到入口函数 {entry}（改名了？）"
            scope = m.group(0)

        out = set()
        for name, fn in consts.items():
            if re.search(rf"\b{name}\.write_text\b", scope):
                out.add(f"data/{fn}")

        # 顺着本地 import 递归：只有 scope 里真的用到 mod.something 才算
        for m in re.finditer(r"^\s*import\s+([a-z_][a-z_0-9]*)\s*(?:#.*)?$",
                             src, re.M):
            mod = m.group(1)
            path = _resolve(mod)
            if not path or path == src_path:
                continue
            if not re.search(rf"\b{mod}\.\w+", scope):
                continue
            out |= _written(path, None, seen)
        return out

    RUNS = {
        "merge.yml": [("scripts/merge_candidates.py", None)],
        "daily.yml": [("scripts/build_daily.py", None)],
        # 只调 _rebuild_site()，那个函数不写 pool_media.json 也不查 iTunes
        "import-bios.yml": [("tools/import_bios.py", None),
                            ("tools/gen_gpt_memory.py", None),
                            ("scripts/build_daily.py", "_rebuild_site")],
    }

    problems = []
    for wf, scripts in RUNS.items():
        f = ROOT / ".github" / "workflows" / wf
        if not f.exists():
            continue
        y = f.read_text(encoding="utf-8")
        flat = re.sub(r"\\\s*\n\s*", " ", y)          # 折平 shell 续行
        adds = " ".join(re.findall(r"git add ([^\n]*)", flat))
        for sp, entry in scripts:
            if not (ROOT / sp).exists():
                continue
            for target in sorted(_written(sp, entry)):
                if target not in adds:
                    problems.append(f"{wf} 跑 {sp} 会写 {target}，但 git add 里没有它")
    assert not problems, ("workflow 漏提交脚本写出的数据文件：\n  "
                          + "\n  ".join(problems))


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed, failed = 0, []
    for fn in fns:
        try:
            fn()
            passed += 1
            print(f"  PASS {fn.__name__}")
        except Exception as e:
            failed.append((fn.__name__, e))
            print(f"  FAIL {fn.__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
