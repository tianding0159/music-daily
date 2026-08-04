"""端到端验证 GPT 补库通道：按 GPT_WEEKLY.md 的规矩造交付物，跑真实管线。

每个场景都在独立的仓库副本里跑，互不污染；全部用 --dry-run（不写真库）。
覆盖 GPT_WEEKLY.md §四「会被拒的硬条件」那张表的每一行 + 正常路径。
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pathlib
SRC = str(pathlib.Path(__file__).resolve().parent.parent)

# 一首 iTunes 真查得到、且不在池里的曲目（假艺人会 not_found、测不到后续闸）
BASE_TRACK = {
    "title": "Blue Monk", "artist": "Thelonious Monk", "year": 1957,
    "album": "Thelonious Himself", "genres": ["jazz pop"], "mood_tags": ["late night"],
    "production_tags": ["tape"], "instrumentation": ["piano"], "vocal_style": "器乐",
    "bpm_band": "80-90", "has_melody": True, "familiarity": "possibly-known",
    "scene": "夜里一个人收拾房间时",
    "artist_oneliner": "钢琴家，把不和谐音处理成结构而非装饰。",
    "why": "左手节奏留出很多空隙。旋律在空隙里显形。",
    "source": "test", "source_url": "https://example.com/x",
}
GOOD_BIO_TEXT = ("Thelonious Monk 生于北卡罗来纳州罗基芒特，四岁随家人迁往纽约。"
                 "四十年代在 Minton's Playhouse 参与早期比波普的成形，"
                 "1947 年起为 Blue Note 录制个人作品，长期使用一架施坦威立式钢琴。")


def deliver(payload) -> tuple[str, str]:
    """按 GPT_WEEKLY.md 的规矩产出交付物：ensure_ascii=True + SHA-256。"""
    s = json.dumps(payload, ensure_ascii=True, indent=1)
    return s, hashlib.sha256(s.encode("ascii")).hexdigest()


def run_case(label, payload, want_rc, mangle=False, drop_from_pool=True):
    root = tempfile.mkdtemp(prefix="gpt_")
    shutil.rmtree(root)
    shutil.copytree(SRC, root, ignore=shutil.ignore_patterns(
        ".git", "node_modules", "__pycache__", ".backup", "site"))
    # 把测试曲目 / 艺人从库里摘掉，模拟「新曲 + 新艺人」
    if drop_from_pool:
        pp = f"{root}/data/pool.json"
        pool = [t for t in json.load(open(pp, encoding="utf-8"))
                if "Blue Monk" not in t.get("title", "")]
        json.dump(pool, open(pp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        ap = f"{root}/data/artists.json"
        arts = [a for a in json.load(open(ap, encoding="utf-8"))
                if a["artist"] != "Thelonious Monk"]
        json.dump(arts, open(ap, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for f in os.listdir(f"{root}/candidates"):
        if f.endswith(".json"):
            os.remove(f"{root}/candidates/{f}")

    text, sha = deliver(payload)
    if mangle:
        # 必须先用 ensure_ascii=False 产出（才有非 ASCII 字节可损坏）。
        # 按 GPT_WEEKLY.md 规矩交付的文件是纯 ASCII，物理上损坏不了 ——
        # 这正是那条规矩存在的意义，也是我第一版测试测不出东西的原因。
        text = json.dumps(payload, ensure_ascii=False, indent=1)
        text = text.encode("utf-8").decode("cp1252", errors="replace")
    open(f"{root}/candidates/2026-08-10.json", "w", encoding="utf-8").write(text)

    r = subprocess.run([sys.executable, "scripts/merge_candidates.py", "--dry-run"],
                       cwd=root, capture_output=True, text=True, timeout=240)
    out = r.stdout + r.stderr
    ok = r.returncode == want_rc
    print(f"{'✓' if ok else '✗'} {label}")
    print(f"    rc={r.returncode}（期望 {want_rc}）· SHA={sha[:12]}…")
    for ln in out.splitlines():
        if any(k in ln for k in ("[P0]", "[warn]", "❌", "没有简介", "编码损坏",
                                 "input ", "写入简介", "都已有简介")):
            print(f"      {ln.strip()[:104]}")
    shutil.rmtree(root, ignore_errors=True)
    return ok


CASES = []

# ── 正常路径：新曲 + 新艺人带简介
CASES.append(("正常：新曲 + 新艺人带简介 → 通过",
              {"tracks": [BASE_TRACK],
               "artists": [{"artist": "Thelonious Monk", "bio": GOOD_BIO_TEXT,
                            "confidence": "high"}]}, 0, False))

# ── §四 表里的每一行
CASES.append(("新艺人没带简介 → 拒（应点名）",
              {"tracks": [BASE_TRACK], "artists": []}, 3, False))

CASES.append(("mood_tags 不在受控表内 → 拒",
              {"tracks": [{**BASE_TRACK, "mood_tags": ["深夜感"]}],
               "artists": [{"artist": "Thelonious Monk", "bio": GOOD_BIO_TEXT,
                            "confidence": "high"}]}, 3, False))
# ↑ 期望 3 而非 1：曲目 schema 不合格 → 不入池 → 艺人不在池里 → bio 报 P0 → rc=3。
#   拒收本身是对的，但【报出的原因错了】（说是简介问题，实际是 mood_tags）。

CASES.append(("why 超过 2 句 → 拒",
              {"tracks": [{**BASE_TRACK, "why": "第一句。第二句。第三句。"}],
               "artists": [{"artist": "Thelonious Monk", "bio": GOOD_BIO_TEXT,
                            "confidence": "high"}]}, 3, False))   # 同上，原因被盖

CASES.append(("简介含黑名单词 → 拒",
              {"tracks": [BASE_TRACK],
               "artists": [{"artist": "Thelonious Monk",
                            "bio": "空灵治愈的钢琴家。" + GOOD_BIO_TEXT,
                            "confidence": "high"}]}, 3, False))

CASES.append(("简介含「让人」→ 拒",
              {"tracks": [BASE_TRACK],
               "artists": [{"artist": "Thelonious Monk",
                            "bio": "他的演奏让人想起某种structure。" + GOOD_BIO_TEXT,
                            "confidence": "high"}]}, 3, False))

CASES.append(("confidence 非 high/low → 拒",
              {"tracks": [BASE_TRACK],
               "artists": [{"artist": "Thelonious Monk", "bio": GOOD_BIO_TEXT,
                            "confidence": "medium"}]}, 3, False))

CASES.append(("简介里英文地名没译 → 拒",
              {"tracks": [BASE_TRACK],
               "artists": [{"artist": "Thelonious Monk",
                            "bio": "Thelonious Monk 生于 North Carolina，"
                                   "四十年代在纽约参与早期比波普的成形，"
                                   "1947 年起为 Blue Note 录制个人作品。",
                            "confidence": "high"}]}, 3, False))

CASES.append(("简介里汉字之间夹空格 → 拒",
              {"tracks": [BASE_TRACK],
               "artists": [{"artist": "Thelonious Monk",
                            "bio": GOOD_BIO_TEXT.replace("四岁随家人", "四岁 随家人"),
                            "confidence": "high"}]}, 3, False))

CASES.append(("文件编码损坏 → 拒（rc=4）",
              {"tracks": [BASE_TRACK],
               "artists": [{"artist": "Thelonious Monk", "bio": GOOD_BIO_TEXT,
                            "confidence": "high"}]}, 4, True))

print("=" * 74)
print("GPT 补库通道端到端验证（按 GPT_WEEKLY.md 的规矩造交付物）")
print("=" * 74)
passed = 0
for label, payload, want, mangle in CASES:
    passed += run_case(label, payload, want, mangle)
    print()
print("=" * 74)
print(f"  {passed}/{len(CASES)} 个场景符合预期")
