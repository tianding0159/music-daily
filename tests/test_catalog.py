"""离线确定性测试（无需网络/pytest）。运行：python3 tests/test_catalog.py

覆盖：pool 数据完整性、canonical id 稳定性/去重、版本错配检测、fit 百分制、
黑名单过滤、picker 同一天稳定 + 去重、文案口径护栏（copy_check）。
任一失败 → 退出码 1。
"""
from __future__ import annotations

import json
import re
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


def test_version_mismatch_via_itunes_classify():
    """版本错配判据的测试，从已删的 merge_candidates._version_mismatch 迁到真判据。

    原测试保活的是一份零生产调用的副本，两张词表还与 itunes 双向分叉 ——
    它给的是「版本错配已覆盖」的假保证。四个例子在 classify 上结果逐条一致
    （审计已实测），所以直接迁过来。
    """
    def st(cand_title, matched_title):
        res = [{"artistName": "A", "trackName": matched_title, "collectionName": "C",
                "releaseDate": "2020-01-01T00:00:00Z", "trackId": 1}]
        return itunes.classify("A", cand_title, res)[0]

    assert st("Halo", "Halo (Ulrich Schnauss Remix of Aus)") == "version_mismatch"
    assert st("Halo", "Halo") == "exact_match"
    assert st("Song", "Song (Live)") == "version_mismatch"
    # 主标题本身含 live、两边都有 → 不算错配
    assert st("Live Forever", "Live Forever") == "exact_match"


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


def test_gpt_docs_blacklist_matches_code():
    """GPT_ARTIST_BIOS.md 的禁用词表必须与代码的判据集合逐字相等。

    2026-08-04 审计：文档手抄了 36 词，而 bio 通道真实判据是 57 词
    （copy_check.blacklist() 47 ∪ import_bios.EXTRA_BANNED 10）。GPT 按 36 词
    自查通过，写出「广受好评」「享誉」这类在音乐人介绍里极自然的词 → P0 →
    补库通道下连同曲目整批被拒，白写一批 + 一次人工返工。

    为什么不把词表换成链接：GPT_*.md 是贴进 ChatGPT 的自包含任务书，
    对方未必能取仓库文件，换成链接会从 36 词变成 0 词。所以只能保留副本，
    然后用这条测试盯住它别漂。
    """
    import importlib
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.path.insert(0, str(ROOT / "tools"))
    cc = importlib.import_module("copy_check")
    ib = importlib.import_module("import_bios")
    want = set(cc.blacklist()) | set(ib.EXTRA_BANNED)

    doc = (ROOT / "GPT_ARTIST_BIOS.md").read_text(encoding="utf-8")
    m = re.search(r"\*\*禁用词\*\*.*?```\n(.*?)\n```", doc, re.S)
    assert m, "GPT_ARTIST_BIOS.md 里找不到禁用词代码块（结构被改了？）"
    got = set(m.group(1).split())
    assert got == want, (
        f"文档禁用词表与代码不一致 —— 缺 {sorted(want - got)} · 多 {sorted(got - want)}。"
        "别手抄，用脚本从 copy_check.blacklist() ∪ import_bios.EXTRA_BANNED 生成。")


def test_snapshots_have_no_bad_status_media():
    """期号快照里不能冻着非 ACCEPT 的媒体 —— 归档页是从快照渲染的。

    2026-08-04 审计实测：2026-07-29 那期有 4 首带着 artist_mismatch /
    version_mismatch 的封面和试听，线上归档页正在展示（Ride On Time 挂的是
    DEEN 的专辑图，点播放听到的是另一个人）。而当时 healthcheck 报
    bad_status: 0 —— 因为 media_check 只扫 pool_media.json，看不见快照。
    修 pool_media 洗不掉快照，必须单独有工具（tools/fix_snapshot_media.py）。

    这条断言必须在快照洗干净【之后】才加，否则 canary 立刻红而手上没有
    能让它变绿的工具。
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib
    it = importlib.import_module("itunes")
    cache = it.load_cache()
    issues = ROOT / "data" / "issues"
    if not issues.is_dir():
        return
    bad = []
    for f in sorted(issues.glob("*.json")):
        snap = json.loads(f.read_text(encoding="utf-8"))
        for t in snap.get("tracks", []):
            if not t.get("_cover"):
                continue
            k = it._key(t.get("artist", "")) + "|" + it._key(t.get("title", ""))
            ent = cache.get(k)
            if ent and ent.get("status") not in it.ACCEPT:
                bad.append(f"{f.stem} {t.get('artist')} — {t.get('title')} "
                           f"[{ent.get('status')}]")
    assert not bad, ("快照里冻着非 ACCEPT 媒体（归档页正在展示错封面/错试听），"
                     "跑 python3 tools/fix_snapshot_media.py --apply：\n  "
                     + "\n  ".join(bad))


def test_wechat_desp_uses_real_total_not_brief_len():
    """微信推送的曲目数必须来自当期真实总数，不能是 tracks_brief 的长度。

    2026-08-04 审计抓到：latest.json 的 tracks_brief 只有 6 条（摘要用），
    而 build_desp 拿 len(tracks) 当总数 —— 于是每天推送都写「今日 6 首已更新」，
    实际是 30 首。真值在 latest["n"]，此前没人用。
    """
    import importlib
    sys.path.insert(0, str(ROOT / "scripts"))
    pw = importlib.import_module("push_wechat")
    brief = [{"title": f"T{i}", "artist": f"A{i}"} for i in range(6)]
    title, desp = pw.build_desp("2026-01-01", "https://x/", brief, total=30)
    assert "30首" in title, f"标题没用真实总数：{title}"
    assert "今日 30 首" in desp, f"正文没用真实总数：{desp.splitlines()[0]}"
    assert "6首" not in title and "今日 6 首" not in desp, "仍在用摘要条数当总数"
    # 缺省回退：不传 total 时用 len(tracks)，保持直接调用的兼容
    t2, _ = pw.build_desp("2026-01-01", "https://x/", brief)
    assert "6首" in t2, "不传 total 时应回退到 len(tracks)"


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


def test_publish_guard_covers_static_assets():
    """页面 head 引用的静态资源（manifest / 各尺寸图标），发布守卫必须逐个查。

    这些资源【不由重建步骤生成】，只靠 checkout 带过来——没有任何脚本会重造它们，
    所以误删之后一路静默：页面照开，只是 404 四个请求、加桌面拿不到图标。
    根因同 artists.min.json 那次（守卫清单没跟上新增产物）。这里把「清单」与
    「页面真实引用」对账，而不是再手写一份清单等它漂移。
    """
    # 清单的唯一来源是 tools/check_site_assets.sh（两个 workflow 都调它）。
    guard = (ROOT / "tools/check_site_assets.sh").read_text(encoding="utf-8")
    guarded = set()
    for blk in re.findall(r"^(?:PRODUCTS|STATIC)=\(\n(.*?)^\)", guard, re.M | re.S):
        guarded |= {ln.strip() for ln in blk.splitlines()
                    if ln.strip() and not ln.strip().startswith("#")}
    assert guarded, "check_site_assets.sh 里没解析出清单，测试本身失效了"

    # 守卫必须真的被每条部署链路调用 —— daily.yml 此前一道守卫都没有，
    # 而它才是每天自动跑的那条（自动化路径没人在旁边看着，更需要）。
    for wf_name in ("publish-site.yml", "daily.yml"):
        wf = (ROOT / ".github/workflows" / wf_name).read_text(encoding="utf-8")
        if "upload-pages-artifact" not in wf:
            continue                        # 不部署的 workflow 不要求
        # 判据必须是【真的调用】，不能是"文中出现" —— publish-site.yml 里有一行
        # 注释也提到这个脚本名，`in wf` 会被注释满足，于是拿掉真实调用照样绿
        # （这条假绿是负向验证逮出来的）。所以只认非注释行里的 run: 调用。
        called = any(
            "check_site_assets.sh" in ln and not ln.lstrip().startswith("#")
            for ln in wf.splitlines())
        assert called, (f"{wf_name} 会部署 site/ 却没调 tools/check_site_assets.sh"
                        f"（注释里提到不算）")

    # 页面真实引用的静态资源从【渲染器源码】抓，不从产物 HTML 抓——
    # 产物可能滞后，渲染器才是这件事的来源。
    #
    # 正则【不能把模板占位符写死】。第一版写的是 `href="\{?up\}?([^"]+)"`：
    # `up` 是必需的，于是 render_landing.py 里的字面量 href="manifest.webmanifest"
    # 一条都没匹配上 —— 那个文件根本没被对账，测试却照样绿。
    # 现在改成：先把 {任意占位符} 从 href 里剥掉，再取剩下的路径，
    # 这样 "{up}x.png" 与 "x.png" 都能抓到。
    refs = set()
    for src in ("render_grid.py", "render_random.py", "render_landing.py"):
        t = (ROOT / "scripts" / src).read_text(encoding="utf-8")
        for rel in ("manifest", "apple-touch-icon"):
            got = {re.sub(r"\{[^}]*\}", "", raw)          # 去掉 {up} 一类占位符
                   for raw in re.findall(rf'rel="{rel}" href="([^"]+)"', t)}
            # 断言必须细到 **(文件 × 标签种类)**。只按文件断言不够：抽掉 landing 的
            # manifest 标签后，它还有 apple-touch-icon 顶着，集合依然非空 → 照样绿。
            # （这条正是负向验证逮出来的 —— 第一版按文件断言时，我以为它能挡住。）
            assert got, (f"{src} 里没抓到 rel=\"{rel}\" 的引用。要么该文件真的漏了"
                         f"这个标签，要么正则又跟不上写法了 —— 两种都得有人看一眼。")
            refs |= got
    man = json.loads((ROOT / "site/manifest.webmanifest").read_text(encoding="utf-8"))
    refs.update(ic["src"] for ic in man["icons"])

    # ── 产物级断言：每一个发出去的页面都必须两个标签齐全，且路径真能解析 ──
    # 源码级断言数不清"每个 build 函数各自有没有"：render_grid.py 里有两个
    # manifest 标签（daily 与 archive-index 各一），抽掉一个另一个还顶着，
    # 集合依然非空 → 假绿（这条也是负向验证逮出来的）。
    # 「每页都齐全」才是真正要保的性质，就直接对每一页断言。
    pages = [f for f in sorted((ROOT / "site").rglob("*.html"))
             if not f.name.startswith("_")]          # _*.html 是探针页，不发布
    assert len(pages) >= 4, f"只找到 {len(pages)} 个页面，产物像是没生成"
    for pg in pages:
        h = pg.read_text(encoding="utf-8")
        for rel in ("manifest", "apple-touch-icon"):
            m = re.search(rf'rel="{rel}" href="([^"]+)"', h)
            assert m, f"{pg.relative_to(ROOT)} 缺 rel=\"{rel}\""
            target = (pg.parent / m.group(1)).resolve()
            assert target.is_file(), (f"{pg.relative_to(ROOT)} 的 {rel} 指向 "
                                      f"{m.group(1)}，从该页所在目录解析不到文件")
    missing = sorted(r for r in refs if r not in guarded)
    assert not missing, (f"这些资源被页面/manifest 引用，但发布守卫没查：{missing}\n"
                         f"守卫清单：{sorted(guarded)}")
    gone = sorted(r for r in refs if not (ROOT / "site" / r).is_file())
    assert not gone, f"引用了但文件不存在：{gone}"


def _png_rgb(path):
    """纯标准库读 8 位真彩 PNG 的像素（zlib 在标准库里，Pillow 不在）。

    为什么不用 Pillow：CI 全程零 pip install（requirements.txt 就写着"全部用
    标准库"）。第一版写的是 `except ImportError: return` —— 在 CI 里那条护栏
    **必定空转**，等于没有。可选的护栏≈没护栏，所以改成自己解。
    返回 (宽, 高, getpx)；getpx(x, y) -> (r, g, b)。
    """
    import struct
    import zlib
    d = path.read_bytes()
    assert d[:8] == b"\x89PNG\r\n\x1a\n", f"{path} 不是 PNG"
    w, h, depth, ctype = struct.unpack(">IIBB", d[16:26])
    assert (depth, ctype) == (8, 2), f"{path} 是 depth={depth} ctype={ctype}，本读取器只支持 8 位真彩"
    idat, i = b"", 8
    while i < len(d):
        ln = struct.unpack(">I", d[i:i + 4])[0]
        typ = d[i + 4:i + 8]
        if typ == b"IDAT":
            idat += d[i + 8:i + 8 + ln]
        elif typ == b"IEND":
            break
        i += 12 + ln
    raw = zlib.decompress(idat)
    stride, bpp = w * 3, 3
    rows, prev = [], bytearray(stride)
    for y in range(h):
        f = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for x in range(stride):                       # 反 filter（PNG 五种）
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(bytes(line))
        prev = line
    return w, h, lambda x, y: tuple(rows[y][x * 3:x * 3 + 3])


def test_maskable_icon_respects_safe_zone():
    """声明 purpose=maskable 的图标，安全区（直径 80% 圆）外不能有内容。

    这个声明是给系统的承诺：「随便你裁，中心 80% 圆内是完整的」。
    普通版唱片直径 88%，最外两圈沟槽与盘缘亮边都落在裁切带里（实测 14174 px），
    拿它去声明 maskable，Android 会照裁 —— 比不声明更糟。
    顺带校验 sizes 声明与真实像素一致（同类的"声明必须成立"问题）。
    """
    man = json.loads((ROOT / "site/manifest.webmanifest").read_text(encoding="utf-8"))
    checked = 0
    for ic in man["icons"]:
        w, h, px = _png_rgb(ROOT / "site" / ic["src"])
        # sizes 也是给系统的声明，标错会让它按错的尺寸挑图
        assert ic["sizes"] == f"{w}x{h}", (f"{ic['src']} 声明 sizes={ic['sizes']}，"
                                          f"实际 {w}x{h}")
        if "maskable" not in (ic.get("purpose") or ""):
            continue
        assert w == h, f"{ic['src']} 不是正方形"
        c, safe = w / 2, w * 0.40
        bg = px(2, 2)                                 # 角落即底色
        bad = sum(1 for y in range(0, h, 2) for x in range(0, w, 2)
                  if ((x - c) ** 2 + (y - c) ** 2) ** .5 > safe
                  and max(abs(px(x, y)[i] - bg[i]) for i in range(3)) > 12)
        assert bad == 0, (f"{ic['src']} 安全区外有 {bad} 个非底色采样点，"
                          f"声明 maskable 会被系统裁掉内容")
        checked += 1
    assert checked >= 1, ("manifest 里没有任何 maskable 图标被检查到 —— "
                          "要么声明丢了，要么这个测试空转了")

def test_safe_area_not_dropped_by_overrides():
    """贴屏边元素的 padding/bottom，在媒体查询里被覆盖时必须带上 inset。

    简写 `padding:` 会【整条替换】前面写好的四行 calc()，于是窄屏
    （也就是手机 —— 最需要安全区的那批设备）反而丢掉保护。这类漂移
    静态可查，而浏览器验证只覆盖我恰好测到的那个视口宽度。

    实测踩过：393px 视口命中 max-width:560px 媒体查询，那里的 #basket
    覆盖了基础规则 —— 撤掉基础规则的联动，浏览器测试照样全绿（假绿）。
    """
    import re
    # 贴屏边、需要安全区的选择器
    EDGE = (".nav", "#np", "#basket", "#lb", ".stage", ".wrap")
    problems = []
    for src in ("render_grid.py", "render_random.py", "render_landing.py", "lightbox.py"):
        text = (ROOT / "scripts" / src).read_text(encoding="utf-8")
        for m in re.finditer(r"^\s*([#.][\w-]+)\s*\{([^}]*)\}", text, re.M):
            sel, body = m.group(1), m.group(2)
            if sel not in EDGE:
                continue
            line_no = text[:m.start()].count("\n") + 1
            # 声明了会影响贴边距离的属性，就得同时出现 safe-area 变量
            touches_edge = re.search(r"\b(padding|padding-top|padding-bottom|"
                                     r"padding-left|padding-right|bottom|top)\s*:", body)
            if not touches_edge:
                continue
            if "--sa" in body or "safe-area" in body:
                continue
            # top:0 / bottom:0 这类纯定位锚点不算（由 padding 让位），
            # 只在它声明了【非零的】间距时才要求带 inset
            vals = re.findall(r"\b(?:padding[\w-]*|bottom|top)\s*:\s*([^;]+)", body)
            if all(v.strip() in ("0", "0px", "auto") for v in vals):
                continue
            problems.append(f"{src}:{line_no} {sel} 声明了间距却没带 safe-area 变量：{vals}")
    assert not problems, ("这些贴屏边规则会丢掉安全区保护：\n  " + "\n  ".join(problems))


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
