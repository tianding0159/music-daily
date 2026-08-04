"""补库结果推微信 —— 成功报数、失败报原因和怎么修。

为什么需要（2026-08-03）：定时补库跑在 GPT 那边，是**无人值守**的周任务；
仓库这侧 merge.yml 原本失败时【完全没有通知】，只在 Actions 页面变红。
于是「候选被拒 → 池子停止增长」可以静默持续好几周没人发现 ——
而且刚加的「新艺人缺简介整批拒收」让拒收概率变高了。

只报「这次发生了什么 + 下一步做什么」，不报无关细节。
没配 WECHAT_PUSH_KEY 时静默跳过（本地跑不该因此失败）。

用法（merge.yml 里 if: always() 调用）：
    python3 scripts/notify_merge.py <merge退出码>
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import push_wechat  # noqa: E402

REPORTS = ROOT / "reports" / "merge"
DATA = ROOT / "data"

# merge_candidates 的退出码语义（与那边保持一致，改一处要同步）
RC_MEANING = {
    0: ("补库完成", "本次候选已入库。"),
    1: ("补库未通过校验", "候选有 schema / 文案问题，文件已保留在 `candidates/`，修好重传即可。"),
    2: ("补库遇到网络问题", "iTunes 限流或网络异常（transient），**候选已保留**，下次会自动重试，不用管。"),
    3: ("补库被拒：新艺人缺简介", "本批带进来的新艺人没有简介。规则是曲目和简介要在**同一份文件**里一起给。"),
}


# 报告比这个岁数还老 = 本次没产生新报告（候选为空 / 提前退出），
# 不能拿它的数字当本次结果报出去 —— 那会在「什么都没发生」时误报上次的 +N 首。
_FRESH_SEC = 15 * 60


def _latest_report() -> dict | None:
    """本次运行刚产生的合并报告；拿不到就返回 None（宁可不报数，不报错数）。"""
    if not REPORTS.exists():
        return None
    fs = sorted(REPORTS.glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not fs:
        return None
    import time
    if time.time() - fs[-1].stat().st_mtime > _FRESH_SEC:
        return None
    try:
        return json.loads(fs[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> int:
    # 解析必须永不抛错：本脚本在 CI 里由 if: always() 调用，职责就是
    # 「连失败也要发出通知」。如果 steps.merge.outputs.rc 因为上游步骤没跑完
    # 而是空串（或有人手动传了 --help），旧代码会 ValueError 崩掉 ——
    # 那就变成「失败时通知器自己也失败」，最该发声的时候彻底哑掉。
    arg = sys.argv[1] if len(sys.argv) > 1 else "0"
    try:
        rc = int(str(arg).strip() or "0")
    except ValueError:
        print(f"[notify_merge] 退出码参数无法解析：{arg!r}，按「异常」处理")
        rc = -1
    title_base, advice = RC_MEANING.get(
        rc, (f"补库异常退出（rc={rc}）",
             "退出码不在已知列表里，看一下 Actions 日志。"
             if rc >= 0 else "连退出码都没拿到，说明上游步骤异常中断，看 Actions 日志。"))

    lines = []
    try:
        pool = json.loads((DATA / "pool.json").read_text(encoding="utf-8"))
        arts = json.loads((DATA / "artists.json").read_text(encoding="utf-8"))
        n_pa = len({t.get("artist") for t in pool})
        lines.append(f"- 曲池 **{len(pool)}** 首 · 艺人 {n_pa} 位")
        lines.append(f"- 艺人简介 **{len(arts)}** 位（覆盖 {100*len(arts)/max(n_pa,1):.1f}%）")
    except Exception:
        pass

    rep = _latest_report()
    if rc == 0 and not rep:
        title = "补库：本次无新增"
        lines.append("- 本次没有候选文件，或候选全部被去重 / 隔离")
    elif rc == 0 and rep:
        added = rep.get("added", 0)
        title = f"{title_base}：+{added} 首"
        lines.append(f"- 本次新增 **{added}** 首"
                     f"（输入 {rep.get('input', '?')} · 重复 {rep.get('duplicates', 0)}"
                     f" · 版本不符 {rep.get('version_mismatch', 0)}"
                     f" · 查无此曲 {rep.get('not_found', 0)}）")
    else:
        title = title_base

    lines.append("")
    lines.append(advice)
    if rc:
        lines.append("")
        lines.append("拒收的具体条目见 Actions 运行日志；流程与格式见 `GPT_WEEKLY.md`。")

    ok = push_wechat.push(title, "\n".join(lines))
    print(f"[notify_merge] rc={rc} title={title!r} pushed={ok}")
    # 通知本身失败不该改变整条流水线的结论
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
