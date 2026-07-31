"""候选 schema 严格校验（P1-5）。纯逻辑、可离线单测。

validate_track(t) -> list[str]  逐首返回错误原因（空=通过）。
validate_batch(cands, pool) -> (valid, invalids)  批级规则：批内去重、classic-known≤2、单艺人≤3。
不合格候选不进曲库（由 merge 写入 quarantine），绝不静默补默认值。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import copy_check  # noqa: E402

FAMILIARITY = {"likely-unheard", "possibly-known", "classic-known"}
REQUIRED = ["title", "artist", "year", "album", "genres", "mood_tags", "production_tags",
            "instrumentation", "vocal_style", "bpm_band", "has_melody", "familiarity",
            "scene", "artist_oneliner", "why", "source", "source_url"]
ARRAY_FIELDS = ["genres", "mood_tags", "production_tags", "instrumentation"]
_SCENE_BANNED = ("通勤", "适合放松", "放松时", "睡前听", "背景音乐", "学习时", "工作时听", "随便听")
_BPM = re.compile(r"^\s*\d{2,3}\s*[–\-~]\s*\d{2,3}\s*$")
_HTTPS = re.compile(r"^https://\S+$")
_PARENS = re.compile(r"[\(\（\[【].*?[\)\）\]】]")


def _key(s: str) -> str:
    return re.sub(r"[^0-9a-z一-鿿぀-ヿ]+", "", _PARENS.sub(" ", (s or "").lower()))


def validate_track(t: dict) -> list[str]:
    errs: list[str] = []
    for f in REQUIRED:
        if f not in t:
            errs.append(f"缺字段 {f}")
    if errs:
        return errs  # 字段不全，先不深查

    for f in ("title", "artist", "album", "scene", "artist_oneliner", "why"):
        if not str(t.get(f, "")).strip():
            errs.append(f"{f} 为空")
    if not re.fullmatch(r"\d{4}", str(t.get("year", ""))):
        errs.append(f"year 非四位年份: {t.get('year')}")
    for f in ARRAY_FIELDS:
        v = t.get(f)
        if not isinstance(v, list) or (f in ("genres", "mood_tags") and len(v) < 1):
            errs.append(f"{f} 需为非空数组")
    if t.get("has_melody") is not True:
        errs.append("has_melody 必须显式为 true")
    if t.get("familiarity") not in FAMILIARITY:
        errs.append(f"familiarity 非法: {t.get('familiarity')}")
    if not _HTTPS.match(str(t.get("source_url", ""))):
        errs.append("source_url 必须是 https://")
    if not _BPM.match(str(t.get("bpm_band", ""))):
        errs.append(f"bpm_band 需为区间如 70–120: {t.get('bpm_band')}")
    why = str(t.get("why", ""))
    if len([s for s in re.split(r"[。！？!?]", why) if s.strip()]) > 2:
        errs.append("why 超过两句")
    scene = str(t.get("scene", ""))
    if any(b in scene for b in _SCENE_BANNED):
        errs.append("scene 是功能标签(如通勤/放松)，需具体场景")
    if len(scene) < 6:
        errs.append("scene 过短")
    # 文案口径（与 healthcheck 同一个 copy_check，口径只有一份）：
    # 单条能查的两项 —— 黑名单词、圣经范例句被原样抄。
    # 占比类指标要整批才有意义，放在 validate_batch。
    p0, _w, _m = copy_check.check_copy([t])
    for e in p0:
        if e.startswith("黑名单词") or e.startswith("圣经范例句"):
            errs.append(e.split("：")[0] + "（见 style_bible 第五节）")
    return errs


def validate_batch(cands: list[dict], pool: list[dict] | None = None,
                   per_artist_cap: int = 3, classic_cap: int = 2) -> tuple[list[dict], list[dict]]:
    valid, invalids = [], []
    seen_batch: set[str] = set()
    artist_count: dict[str, int] = {}
    classic = 0
    for t in cands:
        errs = validate_track(t)
        ck = _key(t.get("artist", "")) + "|" + _key(t.get("title", ""))
        if not errs and ck in seen_batch:
            errs.append("批内重复")
        ak = _key(t.get("artist", ""))
        if not errs and artist_count.get(ak, 0) >= per_artist_cap:
            errs.append(f"单艺人超过 {per_artist_cap} 首/批")
        if not errs and t.get("familiarity") == "classic-known" and classic >= classic_cap:
            errs.append(f"classic-known 超过 {classic_cap} 首/批")
        if errs:
            invalids.append({"track": t, "errors": errs})
            continue
        seen_batch.add(ck)
        artist_count[ak] = artist_count.get(ak, 0) + 1
        if t.get("familiarity") == "classic-known":
            classic += 1
        valid.append(t)
    return valid, invalids


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path
    data = [json.loads(Path(a).read_text(encoding="utf-8")) for a in sys.argv[1:]]
    cands = [x for d in data for x in (d if isinstance(d, list) else d.get("tracks", []))]
    valid, invalids = validate_batch(cands)
    print(f"valid {len(valid)} / invalid {len(invalids)}")
    for iv in invalids:
        print(" -", iv["track"].get("title"), iv["errors"])
