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

# 正文里该用中文的常见英文地名。2026-08-03 batch05 有 44% 的条目写「来自 Virginia」
# 「Brooklyn 词曲作者」「进入 Nashville」——中英混搭正是站内明确否掉的写法，
# 而同一批人在 batch02 里写的是「弗吉尼亚州夏洛茨维尔」「常驻布鲁克林」。
# 人名/厂牌/专辑名保留英文是对的，地名不是。
# 常见英文地名。**这是低召回的检查——地名是开放集合，固定词表必然漏。**
# 2026-08-03 实测：这份表只抓到 20 条，而 GPT 重写时实际翻掉了 14 个不同地名，
# 其中 Dundee / San Jose / Vienna / Brisbane / Freetown 都不在当时的表里。
# 所以别拿它的命中数当「问题总数」——它是拦截线（高精度），不是普查工具。
# 普查用下面的 place_candidates()（高召回、需人判断）。
EN_PLACES = (
    "Aarhus", "Accra", "Adelaide", "Alabama", "Alaska", "Algiers", "Amsterdam", "Antwerp",
    "Argentina", "Arizona", "Arkansas", "Asuncion", "Atlanta", "Auckland", "Austin",
    "Australia", "Austria", "Bahia", "Baltimore", "Bangalore", "Barcelona", "Beijing",
    "Beirut", "Belfast", "Belgium", "Bergen", "Berlin", "Bilbao", "Birmingham", "Bogota",
    "Bologna", "Boston", "Brighton", "Brisbane", "Bristol", "Brooklyn", "Brussels",
    "Budapest", "Buenos Aires", "Busan", "Cairo", "Calgary", "California", "Canada",
    "Cape Breton", "Cardiff", "Casablanca", "Chengdu", "Chennai", "Chicago", "Chile",
    "Christchurch", "Cologne", "Colombia", "Colombo", "Colorado", "Connecticut",
    "Copenhagen", "Curitiba", "Delaware", "Delhi", "Denmark", "Denver", "Detroit", "Dhaka",
    "Dresden", "Dublin", "Dundee", "Dunedin", "Edinburgh", "England", "Ethiopia",
    "Finland", "Florence", "Florida", "Frankfurt", "Freetown", "Fukuoka", "Geneva",
    "Georgia", "Ghana", "Ghent", "Glasgow", "Gothenburg", "Greece", "Guangzhou", "Halifax",
    "Hamburg", "Havana", "Hawaii", "Helsinki", "Hobart", "Hong Kong", "Houston", "Iceland",
    "Idaho", "Illinois", "Indiana", "Indianapolis", "Indonesia", "Iowa", "Ireland",
    "Israel", "Istanbul", "Johannesburg", "Kampala", "Kansas", "Kansas City", "Karachi",
    "Kathmandu", "Kentucky", "Kiev", "Kingston", "Kinshasa", "Krakow", "Kyoto", "Lagos",
    "Lahore", "Leeds", "Leipzig", "Lima", "Lisbon", "Liverpool", "London", "Los Angeles",
    "Louisiana", "Louisville", "Madrid", "Maine", "Malaysia", "Malmo", "Manchester",
    "Manhattan", "Marrakech", "Maryland", "Massachusetts", "Melbourne", "Memphis",
    "Mexico", "Miami", "Michigan", "Milan", "Minneapolis", "Minnesota", "Mississippi",
    "Missouri", "Montana", "Montevideo", "Montreal", "Mumbai", "Munich", "Nagoya",
    "Nairobi", "Naples", "Nashville", "Nebraska", "Netherlands", "Nevada", "New Hampshire",
    "New Jersey", "New Mexico", "New Orleans", "New York", "New Zealand", "Nigeria",
    "North Carolina", "North Dakota", "Norway", "Oakland", "Odessa", "Ohio", "Oklahoma",
    "Oregon", "Osaka", "Oslo", "Ottawa", "Paris", "Pennsylvania", "Perth", "Peru",
    "Philadelphia", "Philippines", "Pittsburgh", "Poland", "Portland", "Porto", "Portugal",
    "Prague", "Quebec", "Queens", "Quito", "Recife", "Reykjavik", "Rhode Island",
    "Richmond", "Riga", "Rio", "Rome", "Rotterdam", "Salvador", "San Francisco",
    "San Jose", "Santiago", "Sao Paulo", "Sapporo", "Scotland", "Seattle", "Senegal",
    "Seoul", "Seville", "Shanghai", "Sheffield", "Shenzhen", "Sierra Leone",
    "South Carolina", "South Dakota", "Stockholm", "Sweden", "Switzerland", "Sydney",
    "Taipei", "Tallinn", "Tbilisi", "Tel Aviv", "Tennessee", "Texas", "Thailand", "Tokyo",
    "Toronto", "Tulsa", "Tunis", "Turin", "Utah", "Valencia", "Vancouver", "Vermont",
    "Victoria", "Vienna", "Vietnam", "Vilnius", "Virginia", "Wales", "Warsaw",
    "Washington", "Wellington", "West Virginia", "Winnipeg", "Wisconsin", "Wyoming",
    "Yerevan", "Zurich"
)

# 位置词——地名几乎总跟在这些词后面。用于「候选」普查（高召回）。
_PLACE_CTX = r"(?:来自|生于|出生于|常驻|定居|移居|旅居|成长于|活跃于|在|于)"
_PLACE_PAT = re.compile(_PLACE_CTX + r"\s*([A-Z][A-Za-z]*(?:[ \-\'][A-Z][A-Za-z]*)*)")
# 跟在这些词后面的拉丁词是厂牌 / 乐队 / 专辑，不是地名，排除
_NOT_PLACE_HEAD = re.compile(
    r"(?:签入|签给|签约|由|经|厂牌|发行|加入|组建|成立|名义|专辑|单曲|EP|合作|参与|师从)\s*$")
# 明显不是地名的实体后缀（学校 / 厂牌 / 节日 / 场地）
_NOT_PLACE_TAIL = re.compile(
    r"(?:Records?|Recordings?|Tapes|Sound|Music|University|College|School|Institute|"
    r"Conservatory|Festival|Theory|Club|Studios?|Group|Band|Orchestra|Ensemble|SNL)$")


# 地名后面跟这些词，说明它是机构 / 厂牌 / 专辑名的一部分，不是在指地点。
# 2026-08-03 「Manhattan School of Music」被判成地名没翻译，就是缺这道排除。
_INSTITUTION_TAIL = re.compile(
    r"^\s+(?:School|University|College|Conservatory|Institute|Academy|Symphony|"
    r"Philharmonic|Records?|Recordings?|Sound|Sounds|Music|Festival|Museum|"
    r"Public|City\b|Times|Post|Review|Magazine)")


# 地名后紧跟一个大写拉丁词 = 它其实是人名的名（Georgia Hubley、Paris Hilton、
# Austin Peralta）。2026-08-03 Yo La Tengo 的鼓手 Georgia Hubley 被判成「地名
# Georgia 没翻译」，而那条 bio 里真正没翻的 Hoboken 反倒不在词表里 —— 词表法在
# 人名 / 地名同形上必然出错，这也是它只能当拦截线、不能当普查工具的原因之一。
_PERSON_TAIL = re.compile(r"^\s+[A-Z][a-z]+")
# 地名【前面】紧挨一个大写拉丁词 = 它是姓（Alex Leeds、Jack London、Kevin Berlin）。
# _PERSON_TAIL 只能看后面，看不见这种。Slow Pulp 的贝斯手 Alex Leeds 就这么被误报成 Leeds。
_PERSON_HEAD = re.compile(r"[A-Z][a-z]+\s+$")
# 「乐团 Oregon」「乐队 Chicago」—— 地名当团名用，前面有身份词点明。
# 2026-08-03 batch14b 的 Ralph Towner 就这么被拦：他是乐团 Oregon 的创始成员，
# 那条 bio 里真正的地名（华盛顿州、维也纳）早就译成中文了。
# 机构名把地名放在【后面】的形态：「Royal Conservatoire of Scotland」
# 「University of Michigan」—— _INSTITUTION_TAIL 只看后缀，看不见这种。
# 2026-08-04 实测：扩地名词表时 C Duncan 的校名被误判成「Scotland 没翻译」。
_INSTITUTION_HEAD = re.compile(
    r"(?:School|University|College|Conservatoire|Conservatory|Institute|Academy|"
    r"Symphony|Philharmonic|Orchestra|Museum|Library|Bank|Government|Council)"
    r"\s+of\s+$")
# 地名后面紧跟音乐术语 = 它是流派 / 场景名，不是在指地点：
# 「Dunedin sound」「Manchester scene」。与 _INSTITUTION_TAIL 的 Sound 有重叠，
# 但那条要求首字母大写、这条管小写。
_SCENE_TAIL = re.compile(
    r"^\s+(?:sound|scene|school|movement|wave|revival|underground|circuit|"
    r"techno|house|trip-hop|hip-hop|jazz|folk|punk|pop|soul)\b")

_BAND_HEAD = re.compile(r"(乐团|乐队|组合|团体|小组|厂牌|唱片公司|品牌)\s*$")


def _in_title(bio: str, i: int, j: int) -> bool:
    """[i,j) 是否落在书名号 / 引号里 —— 作品名不翻译是对的。

    《Paris I》《Michigan》《Illinois》都是专辑名，翻成中文反而错。
    2026-08-03 batch14a / 14d 各被这种情况挡掉整批 50 条。
    做法：往前找最近的开引号，若它后面没有闭引号就说明我们在引号内。
    """
    for op, cl in (("\u300a", "\u300b"), ("\u300c", "\u300d"),
                   ("\u2018", "\u2019"), ("\u201c", "\u201d"), ("\u3008", "\u3009")):
        a = bio.rfind(op, 0, i)
        if a >= 0 and bio.find(cl, a) >= j:
            return True
    return False


def _place_hit(bio: str, x: str) -> bool:
    """地名是否真的在「指地点」。

    排掉四种同形：机构名首词、人名的名、人名的姓、以及
    **作品名（书名号内）与乐队名（前面有「乐团 / 乐队」等身份词）**。
    后两种是 2026-08-03 batch14a/14b/14d 三批各被一条误报挡掉的原因 ——
    每批 50 条只因 1 条误报全被拦下，而那 3 条其实都写对了。
    """
    for m in re.finditer(r"(?<![A-Za-z])" + re.escape(x) + r"(?![A-Za-z])", bio):
        tail, head = bio[m.end():], bio[:m.start()]
        if (_INSTITUTION_TAIL.match(tail) or _PERSON_TAIL.match(tail)
                or _SCENE_TAIL.match(tail)
                or _PERSON_HEAD.search(head[-20:])
                or _BAND_HEAD.search(head[-12:])
                or _INSTITUTION_HEAD.search(head[-40:])
                or _in_title(bio, m.start(), m.end())):
            continue
        return True
    return False


def place_candidates(bio: str) -> list[str]:
    """疑似未翻译地名（**高召回、需人判断**）。

    厂牌 / 乐队 / 学校也会跟在「来自」「在」后面，这里只能靠语境词和后缀排掉一部分,
    剩下的必须人看。**不要把它接成拦截条件**——2026-08-03 实测误报率约 6 成
    （Sub Pop / Flying Nun / Massive Attack / UCLA / Bandcamp 全被它捞出来）。
    与 mojibake 检测误报葡语人名是同一类错：开放集合上做判定，宁可交人判断。
    """
    out = []
    for m in _PLACE_PAT.finditer(bio):
        tok = m.group(1)
        if _NOT_PLACE_HEAD.search(bio[:m.start()][-14:]):
            continue
        if _NOT_PLACE_TAIL.search(tok):
            continue
        if len(tok) < 3:                      # St / Le 之类的碎片
            continue
        out.append(tok)
    return out

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


def audit(rows: list[dict], extra_artists: set[str] | None = None) -> dict:
    """校验一批 bio。

    extra_artists：**本批同时入库、但此刻还没写进 pool.json 的艺人**。
    专用通道（inbox/bios）是「先有曲目、后补 bio」，池里一定已有这位艺人；
    而补库通道（candidates）是曲目和 bio 同一批到达，校验发生在写盘之前，
    池里还没有 —— 不传这个集合的话，新艺人会被「池里查无此艺人」全部误杀。
    """
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    pool_artists = {t.get("artist", "") for t in pool} | (extra_artists or set())
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
            # 池里没这位、本批也没带这位的曲目 = 这条 bio 永远用不上
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

        # 汉字之间夹空格 —— placefix 那批的残留：把英文地名换成中文时，
        # 原英文两侧的空格没一起删（「出生于 Tulsa，」→「出生于 塔尔萨，」）。
        # 判据严格限定汉字—空格—汉字：中英之间的空格是全库一致的风格，不管。
        cjk_sp = re.findall(r"[一-鿿] +[一-鿿]", bio)
        if cjk_sp:
            rep["p0"].append(
                f"{tag}：汉字之间有多余空格 {cjk_sp[:4]}"
                "（换词时原英文两侧的空格要一起删；中英之间的空格是对的，别动）")
            continue

        # 头号失败模式：bio 只是 oneliner 的扩写
        ol = _norm(oneliners.get(a, ""))
        nb = _norm(bio)
        if ol and len(ol) >= 8 and ol in nb:
            rep["warn"].append(f"{tag}：bio 整段包含了 oneliner 原文（应写新信息，不是扩写）")
        # 艺人名本身包含的词不算地名 —— 乐队 Beirut、A Sunny Day in Glasgow、
        # Casino Versus Japan 都以地名为名，把它们的名字翻成中文才是错的。
        # 2026-08-03 把 Beirut 加进词表后立刻误报了这支乐队，故加这道排除。
        aw = {w.lower() for w in re.findall(r"[A-Za-z]+", a)}
        pl = [x for x in EN_PLACES
              if _place_hit(bio, x) and not set(x.lower().split()) <= aw]
        if pl:
            rep["warn"].append(f"{tag}：地名没翻译 {pl}（人名/厂牌保留英文没问题，地名要用中文）")
        # 词表之外的疑似地名——只提示不拦截（误报约 6 成，见 place_candidates docstring）
        cand = [x for x in place_candidates(bio)
                if x not in pl and not set(x.lower().split()) <= aw]
        if cand:
            rep.setdefault("info", []).append(
                f"{tag}：疑似地名 {cand}（若真是地名请翻译；厂牌/乐队/学校/节日保留英文是对的）")
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

    # 覆盖检测：同名艺人已有 bio 且内容不同 —— 必须显式确认，不能静默发生。
    # 2026-08-03 batch05 覆盖了 batch02 里 16 位的更好版本（地名没翻译），
    # CI 8 步全绿、零拒收，是靠事后手算「输入 160 − 净增 112 = 覆盖 48」才发现的。
    # 护栏只管「有没有违规」，管不了「新版是不是比旧版差」，所以这里只能拦下来让人判断。
    prev = dict(_SEEN)
    if ARTISTS.exists():
        for a in json.loads(ARTISTS.read_text(encoding="utf-8")):
            prev.setdefault(a["artist"], a["bio"])
    ov = [r["artist"] for r in rep["ok"]
          if r["artist"] in prev and prev[r["artist"]].strip() != r["bio"].strip()]
    if ov:
        rep["warn"].append(
            f"覆盖 {len(ov)} 位已有简介且内容不同：{ov[:8]}"
            + (f" …共 {len(ov)}" if len(ov) > 8 else "")
            + "。**先比对两版质量再决定**——旧版可能更好（batch05 就是这样）。"
            "确认新版更好再加 --force")
        rep["overwrites"] = ov
    # 【不在这里登记 _SEEN】—— audit() 只做判定，登记由 _one() 在【放行之后】调
    # record()。无条件登记会让一个被拒的文件污染 _SEEN，把同一次运行里后面那个
    # 干净文件连坐拦下，直接违反本文件「按文件隔离、不连坐」的设计。
    # 触发路径不是 P0（P0 条目走 continue、不进 rep["ok"]），而是
    # **warn 未给 --force 而 rc=1** —— 那些条目就在 rep["ok"] 里。
    # 2026-08-04 审计抓到；我第一次核验时只测了 P0 路径，误判成「不成立」。
    return rep


def record(rep: dict) -> None:
    """把本文件已放行的条目登记进 _SEEN，供同一次运行的后续文件做跨文件去重。

    只在 _one() 判定放行（return 0）之后调用 —— 被拒的文件不该留下痕迹。
    两个 return-0 点【都要调】：体检模式那处漏了的话，_SEEN 在 --dry-run 下
    永远为空、跨文件检测静默缺席，而「护栏没跑」和「护栏通过」输出一模一样。

    单次调用 audit() 的调用方（如 merge_candidates）无需调 record()：
    它每进程只 audit 一次且从不读 _SEEN。将来若改成循环调用，记得补上。
    """
    for r in rep.get("ok", []):
        _SEEN[r["artist"]] = r["bio"]


# 一次运行内已写过的 artist → bio。用于检测「同一批次里多个文件互相覆盖」，
# 这种情况在体检模式（未写盘）下无法从 artists.json 看出来。
_SEEN: dict[str, str] = {}


def load_artists() -> list[dict]:
    """读 data/artists.json —— 唯一读取口，供本模块与 merge_candidates 共用。"""
    return (json.loads(ARTISTS.read_text(encoding="utf-8"))
            if ARTISTS.exists() else [])


def apply(rows: list[dict]) -> int:
    by = {a["artist"]: a for a in load_artists()}
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
    ap.add_argument("--archive", action="store_true",
                    help="目录模式：把通过的输入文件搬到 inbox/bios/done/（CI 用）")
    args = ap.parse_args()

    # 目录模式（CI）：处理 inbox/bios/*.json，每个文件自动找同名 _manifest.json 取 sha
    if args.src is None:
        inbox = ROOT / "inbox" / "bios"
        files = sorted(f for f in inbox.glob("*.json") if not f.name.endswith("_manifest.json"))
        if not files:
            print("inbox/bios/ 下没有待导入文件，跳过")
            return 0
        print(f"目录模式：{len(files)} 个文件待导入\n")

        # 孤儿 manifest 检测：目录里有 *_manifest.json，但按命名规则配不上任何主文件
        # —— 这是命名手滑的确定信号，后果是 SHA 校验被【静默跳过】而其余全绿。
        # 「护栏缺席」和「护栏通过」长得一模一样，所以这里必须硬失败而不是继续。
        stems = {f.stem for f in files}
        orphans = [m for m in sorted(inbox.glob("*_manifest.json"))
                   if m.name[:-len("_manifest.json")] not in stems]
        if orphans:
            print("❌ 有 manifest 配不上主文件（SHA 校验会被静默跳过）：")
            for m in orphans:
                want = m.name[:-len("_manifest.json")] + ".json"
                print(f"   {m.name}")
                print(f"     → 它在找 {want}，但目录里没有这个文件")
            print(f"   目录里的主文件：{sorted(f.name for f in files)}")
            print("   manifest 必须命名为「主文件名去掉 .json」+ _manifest.json")
            print("   例：artist_bios_batch06.json → artist_bios_batch06_manifest.json")
            return 2

        # 【按文件隔离，不连坐】——每个文件是一次独立投递，一批要人工确认
        # 不该堵住其它干净批次。2026-08-03 踩过：batch05_rewrite 需 --force，
        # 旧代码 `rc = rc or r` 让整个 run 非零退出、干净的 batch06/07 已写入的
        # 结果被一并丢弃；此后每传新批次都被它重新连坐一次。
        # 数据完整性由「单文件内整批拒绝」保证，跨文件原子性没有必要。
        applied, held = [], []
        for f in files:
            man = f.with_name(f.stem + "_manifest.json")
            sha = None
            if man.exists():
                try:
                    sha = json.loads(man.read_text(encoding="utf-8")).get("sha256")
                except Exception as e:
                    print(f"⚠️ {man.name} 解析失败：{e}")
            print(f"── {f.name}" + (f"（manifest sha {sha[:12]}…）" if sha
                                      else "  ⚠️ 无 manifest —— 跳过 SHA 校验，"
                                           "传输损坏只能靠编码检测兜底"))
            r = _one(f, sha, do_apply=args.apply, force=args.force)
            print()
            (applied if r == 0 else held).append((f, man, r))

        print("=" * 60)
        if applied:
            print(f"✅ 通过 {len(applied)} 个文件：" + "、".join(f.name for f, _, _ in applied))
        if held:
            print(f"⏸️  留在 inbox 等修正 {len(held)} 个：")
            for f, _, r in held:
                why = {1: "有 P0 或需 --force 确认", 2: "SHA / 编码 / 解析问题"}.get(r, f"rc={r}")
                print(f"     {f.name} —— {why}（原因见上方该文件的报告）")
            print("   它们不影响上面已通过的文件。修好重传，或确认无误后用 --force。")

        # 归档：只搬已通过的，留下的下次还能重跑。CI 用 --archive。
        if args.apply and args.archive and applied:
            done = inbox / "done"
            done.mkdir(parents=True, exist_ok=True)
            for f, man, _ in applied:
                f.rename(done / f.name)
                if man.exists():
                    man.rename(done / man.name)
            print(f"   已归档 {len(applied)} 个文件到 inbox/bios/done/")

        # 有文件通过就 0（让 CI 继续走重建 / 测试 / 提交）；一个都没通过才非零
        if applied:
            return 0
        return max((r for _, _, r in held), default=1)

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
    for x in rep.get("info", []):
        print(f"  [info] {x}")
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
        record(rep)          # 放行了才登记；体检模式也要记，否则跨文件检测在 dry-run 下失效
        print("\n（体检模式，未写盘；加 --apply 导入）")
        return 0

    before = (len(json.loads(ARTISTS.read_text(encoding="utf-8")))
              if ARTISTS.exists() else 0)
    n, total = apply(rep["ok"])
    pool_artists = len({t.get("artist") for t in json.loads(POOL.read_text(encoding="utf-8"))})
    print(f"\n✅ 导入 {n} 条 → data/artists.json 共 {total} 位 "
          f"（池内艺人 {pool_artists} 位，覆盖 {100*total/pool_artists:.1f}%）")
    # 数字对账：输入 − 净增 = 覆盖数。不闭合说明有意料外的覆盖，必须查。
    net, dup = total - before, n - (total - before)
    print(f"   对账：输入 {n} − 净增 {net} = 覆盖 {dup} 位"
          + ("（无覆盖 ✓）" if dup == 0 else "  ← 已在上方 warn 列出"))
    print("   接着跑：python3 -c \"import sys;sys.path.insert(0,'scripts');"
          "import build_daily;build_daily._rebuild_site()\"")
    record(rep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
