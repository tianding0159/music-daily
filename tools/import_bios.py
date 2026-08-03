"""导入 GPT 写的艺人简介 → data/artists.json。

分工：GPT 写 bio，这边负责校验与落盘。校验项都是真踩过的坑：
  · artist 对不上池 → 这条 bio 永远不会被任何页面用到，静默浪费
  · bio 只是 oneliner 的扩写 → 放大页等于没提供新信息（这是本任务的头号失败模式）
  · 黑名单词 / 「让人·令人」/ 破折号模板 / 开头句式集中度 → 站内文案统一口径
  · 与已有 bio 重复 → 同一段话套在不同艺人身上

用法：
  python3 tools/import_bios.py <gpt产出.json>            # 只体检，不写盘
  python3 tools/import_bios.py <gpt产出.json> --apply    # 校验通过后合并进 artists.json
  python3 tools/import_bios.py <gpt产出.json> --apply --force   # 有 warn 也写（P0 仍拒）
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

POOL = ROOT / "data" / "pool.json"
ARTISTS = ROOT / "data" / "artists.json"

# 站内文案黑名单（从 style_bible 解析，与 copy_check 同一口径）+ bio 专属的通稿词
EXTRA_BANNED = ("才华横溢", "独树一帜", "不可多得", "灵魂人物", "音乐鬼才",
                "无可替代", "享誉", "广受好评", "备受赞誉", "无需多言")

# UTF-8 被按 cp1252/latin-1 解读后的典型残迹。2026-08-03 第一批 30 位就这么坏的：
# 「加拿大」的 e5 8a a0 e6 8b bf 到我手里成了 e5 20 e6 bf —— 0x80-0x9F 区间的字节
# 被传输通道吞掉，90% 汉字不可复原。这些字符在正常中文文案里几乎不可能出现，
# 一旦出现就是编码坏了，必须让上游重发（而不是我这边硬猜着修）。
MOJIBAKE_MARKS = ("å", "æ", "ã", "ï¼", "â", "ä", "è", "é", "ç", "ð")

ALLOWED_KEYS = {"artist", "bio", "confidence"}      # 恰好这三个，多一个都拒
ALLOWED_CONF = {"high", "low"}                     # 只这两档

MIN_LEN, MAX_LEN = 60, 220
MAX_DASH_PCT = 20
MAX_HEAD_PCT = 30          # 同一批里最高频开头句式（前 6 字）


def _banned_words() -> set[str]:
    try:
        import copy_check
        return set(copy_check.blacklist()) | set(EXTRA_BANNED)
    except Exception:
        return set(EXTRA_BANNED)


def _norm(s: str) -> str:
    return re.sub(r"[\s，。、·,.\-—…]+", "", str(s or ""))


def check_encoding(raw: str) -> list[str]:
    """在解析前先看文本有没有编码损坏——这类问题必须让上游重发，不能硬修。"""
    errs = []
    # 判据不能只看「有没有 å æ ã」——葡语 João / 法语 Cécile / 西语 Almoço 都含变音字母，
    # healthcheck 第一版就这么误报了 3 处。真 mojibake 的特征是这些字符【连续成串】
    # （一个汉字坏掉变成 2-3 个连续拉丁扩展字符），正常人名里它们总被 ASCII 包着。
    def _run3(v: str) -> bool:
        run = 0
        for ch in v:
            o = ord(ch)
            if 0xA0 <= o <= 0xFF or o in (0x2019, 0x201C, 0x201D):
                run += 1
                if run >= 3:
                    return True
            else:
                run = 0
        return False

    hits = [m for m in MOJIBAKE_MARKS if m in raw] if _run3(raw) else []
    if hits:
        # 数一下有多少个「E0-EF 开头但续字节残缺」的序列，估损坏规模
        b = raw.encode("latin-1", errors="replace")
        i = broken = ok = 0
        while i < len(b):
            if 0xE0 <= b[i] <= 0xEF:
                if i + 2 < len(b) and 0x80 <= b[i + 1] <= 0xBF and 0x80 <= b[i + 2] <= 0xBF:
                    ok += 1; i += 3
                else:
                    broken += 1; i += 1
            else:
                i += 1
        pct = round(100 * broken / max(ok + broken, 1))
        errs.append(f"文本编码已损坏（残迹字符 {hits[:5]}，约 {pct}% 的汉字序列残缺）。"
                    f"这是 UTF-8 被当 cp1252 解读、0x80-0x9F 字节被吞造成的，**不可复原**。"
                    f"请让上游改用 json.dumps(..., ensure_ascii=True) 重发（纯 ASCII 不会坏）。")
    return errs


def audit(rows: list[dict]) -> dict:
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    pool_artists = {t.get("artist", "") for t in pool}
    oneliners = {t.get("artist", ""): t.get("artist_oneliner", "") for t in pool}
    existing = {a["artist"]: a.get("bio", "")
                for a in (json.loads(ARTISTS.read_text(encoding="utf-8"))
                          if ARTISTS.exists() else [])}
    banned = _banned_words()

    rep: dict = {"input": len(rows), "p0": [], "warn": [], "ok": [],
                 "metrics": {}, "skipped": []}
    seen: set[str] = set()
    bios: list[str] = []

    for r in rows:
        a = str(r.get("artist", "")).strip()
        bio = str(r.get("bio", "")).strip()
        tag = a or "<空 artist>"

        if not a or not bio:
            rep["p0"].append(f"{tag}：artist 或 bio 为空")
            continue
        # 合同收紧（GPT 建议）：多余字段会被静默吞掉，等于契约有洞
        extra = set(r.keys()) - ALLOWED_KEYS
        if extra:
            rep["p0"].append(f"{tag}：多余字段 {sorted(extra)}（只允许 artist/bio/confidence）")
            continue
        missing = ALLOWED_KEYS - set(r.keys())
        if missing:
            rep["p0"].append(f"{tag}：缺字段 {sorted(missing)}（三个键必须齐）")
            continue
        conf = r.get("confidence")
        if conf not in ALLOWED_CONF:
            rep["p0"].append(f"{tag}：confidence 非法 {conf!r}（只能 high / low）")
            continue
        if a not in pool_artists:
            # 池里没这位 = 这条 bio 永远用不上
            rep["p0"].append(f"{tag}：池里查无此艺人（拼写不一致？）")
            continue
        if a in seen:
            rep["p0"].append(f"{tag}：本批内重复")
            continue
        seen.add(a)

        hit = [w for w in banned if w in bio]
        if hit:
            rep["p0"].append(f"{tag}：黑名单词 {hit}")
            continue
        if "让人" in bio or "令人" in bio:
            rep["p0"].append(f"{tag}：出现「让人/令人」")
            continue

        # 头号失败模式：bio 只是 oneliner 的扩写
        ol = _norm(oneliners.get(a, ""))
        nb = _norm(bio)
        if ol and len(ol) >= 8 and ol in nb:
            rep["warn"].append(f"{tag}：bio 整段包含了 oneliner 原文（应写新信息，不是扩写）")
        if not (MIN_LEN <= len(bio) <= MAX_LEN):
            rep["warn"].append(f"{tag}：长度 {len(bio)} 字（期望 {MIN_LEN}–{MAX_LEN}）")
        if a in existing and _norm(existing[a]) == nb:
            rep["skipped"].append(f"{tag}：与已有 bio 相同，跳过")
            continue

        bios.append(bio)
        rep["ok"].append(r)

    # 批级指标
    n = max(len(bios), 1)
    dash = sum(1 for b in bios if "——" in b or "—" in b)
    heads = collections.Counter(b[:6] for b in bios)
    dup_bio = sum(c - 1 for c in collections.Counter(map(_norm, bios)).values() if c > 1)
    top_head = heads.most_common(1)[0] if heads else ("", 0)
    rep["metrics"] = {
        "accepted": len(bios),
        "dash_pct": round(100 * dash / n, 1),
        "top_head": top_head[0], "top_head_pct": round(100 * top_head[1] / n, 1),
        "len_min": min((len(b) for b in bios), default=0),
        "len_max": max((len(b) for b in bios), default=0),
        "len_avg": round(sum(len(b) for b in bios) / n),
        "dup_bio": dup_bio,
        "low_conf": sum(1 for r in rep["ok"] if r.get("confidence") == "low"),
    }
    if len(bios) >= 10 and rep["metrics"]["dash_pct"] > MAX_DASH_PCT:
        rep["warn"].append(f"破折号同位语占 {rep['metrics']['dash_pct']}%（上限 {MAX_DASH_PCT}%）——模板复读")
    # 占比类指标在小样本上没意义：2 条里 1 条就占 50%，会把每批小样都误拦
    if len(bios) >= 10 and rep["metrics"]["top_head_pct"] > MAX_HEAD_PCT:
        rep["warn"].append(f"开头句式「{top_head[0]}」占 {rep['metrics']['top_head_pct']}%"
                           f"（上限 {MAX_HEAD_PCT}%）——换开头")
    if dup_bio:
        rep["p0"].append(f"批内有 {dup_bio} 条 bio 完全相同")
    return rep


def apply(rows: list[dict]) -> int:
    existing = (json.loads(ARTISTS.read_text(encoding="utf-8"))
                if ARTISTS.exists() else [])
    by = {a["artist"]: a for a in existing}
    n = 0
    for r in rows:
        by[r["artist"]] = {"artist": r["artist"], "bio": r["bio"].strip(),
                           "confidence": r["confidence"]}
        n += 1
    out = sorted(by.values(), key=lambda a: a["artist"])
    ARTISTS.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return n, len(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?", default=None,
                    help="GPT 产出的 JSON（数组）；省略则处理 inbox/bios/ 下所有 .json")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--force", action="store_true", help="有 warn 也写盘（P0 仍拒）")
    ap.add_argument("--sha", help="上游声明的 SHA-256，核对文件是否在传输中被改动")
    args = ap.parse_args()

    # 目录模式（CI）：处理 inbox/bios/*.json，每个文件自动找同名 _manifest.json 取 sha
    if args.src is None:
        inbox = ROOT / "inbox" / "bios"
        files = sorted(f for f in inbox.glob("*.json") if not f.name.endswith("_manifest.json"))
        if not files:
            print("inbox/bios/ 下没有待导入文件，跳过")
            return 0
        print(f"目录模式：{len(files)} 个文件待导入\n")
        rc = 0
        for f in files:
            man = f.with_name(f.stem + "_manifest.json")
            sha = None
            if man.exists():
                try:
                    sha = json.loads(man.read_text(encoding="utf-8")).get("sha256")
                except Exception as e:
                    print(f"⚠️ {man.name} 解析失败：{e}")
            print(f"── {f.name}" + (f"（manifest sha {sha[:12]}…）" if sha else "（无 manifest）"))
            r = _one(f, sha, do_apply=args.apply, force=args.force)
            print()
            rc = rc or r
        return rc

    return _one(Path(args.src), args.sha, do_apply=args.apply, force=args.force)


def _one(path: Path, sha: str | None, do_apply: bool, force: bool) -> int:
    """处理单个文件。返回 0=通过 / 1=有 P0 或 warn 未放行 / 2=编码或 SHA 问题。"""
    raw = path.read_text(encoding="utf-8")

    # ① SHA-256 核对（GPT 会随文件给 manifest；纯 ASCII 文件哈希对上=一个字没变）
    if sha:
        got = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        if got != sha.strip().lower():
            print(f"❌ SHA-256 不符\n   声明 {sha.strip().lower()}\n   实际 {got}")
            print("   文件在传输中被改动过，请让上游重发")
            return 2
        print(f"✓ SHA-256 核对通过 {got[:16]}…")

    # ② 编码损坏检测（在 json.loads 之前——坏文本也可能是合法 JSON）
    enc_errs = check_encoding(raw)
    if enc_errs:
        print("❌ " + enc_errs[0])
        return 2

    try:
        rows = json.loads(raw)
    except Exception as e:
        print(f"❌ 无法解析 {path.name}：{e}")
        return 2
    if not isinstance(rows, list):
        print("❌ 顶层必须是数组")
        return 2

    rep = audit(rows)
    m = rep["metrics"]
    print(f"=== import_bios === 输入 {rep['input']} 条 → 可接受 {m['accepted']} 条")
    print(f"  长度 {m['len_min']}–{m['len_max']} 字（均 {m['len_avg']}）· low confidence {m['low_conf']}")
    print(f"  破折号 {m['dash_pct']}% · 最高频开头「{m['top_head']}」{m['top_head_pct']}%")
    for x in rep["skipped"]:
        print(f"  [skip] {x}")
    for x in rep["warn"]:
        print(f"  [warn] {x}")
    for x in rep["p0"]:
        print(f"  [P0]   {x}")

    if rep["p0"]:
        print(f"\n❌ {len(rep['p0'])} 项 P0，拒绝写盘（这些条目本来也用不上）")
        return 1
    if rep["warn"] and not force and do_apply:
        print(f"\n⚠️ {len(rep['warn'])} 项告警。确认可接受就加 --force 写盘")
        return 1
    if not do_apply:
        print("\n（体检模式，未写盘；加 --apply 导入）")
        return 0

    n, total = apply(rep["ok"])
    pool_artists = len({t.get("artist") for t in json.loads(POOL.read_text(encoding="utf-8"))})
    print(f"\n✅ 导入 {n} 条 → data/artists.json 共 {total} 位 "
          f"（池内艺人 {pool_artists} 位，覆盖 {100*total/pool_artists:.1f}%）")
    print("   接着跑：python3 -c \"import sys;sys.path.insert(0,'scripts');"
          "import build_daily;build_daily._rebuild_site()\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
