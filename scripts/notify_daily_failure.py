"""日报链路失败时推微信告警。由 daily.yml 末尾以 if: failure() 调用。

为什么需要：daily.yml 是四个 cron 槽的无人值守任务，整个 job 此前没有任何
告警步骤。确定性失败（pool.json 为空、渲染器抛异常、Pages 配额耗尽）会让
四槽以同样方式全挂，仓内唯一信号是「当天一条微信都没收到」—— 正常日收 1 条、
全挂日收 0 条，这个负向信号太弱。姊妹 workflow merge.yml 为完全相同的理由
早就加了一层。

**必须槽感知，不能无条件告警**（这是本脚本存在的关键约束）：
四槽本身是冗余设计，单槽挂掉由后续槽自愈是【预期行为】；而 push 竞态重试、
deploy-pages 抖动都会让单槽变红。无条件推「日报构建失败」会在一次无害的
竞态后立刻报警、30 分钟后下一槽正常出报 —— 狼来了几次就会被静音，
于是真出事那天也没人看。

所以判据是「**当期快照到底建成了没有**」：
  · data/issues/<今天>.json 存在 → 当期已建成，本槽失败不算停更，静默退出
  · 不存在 → 才是真的停更，推告警
这个判据与「第几槽」无关，比数槽位更稳（cron 可能被 GitHub 跳过）。

用法：python3 scripts/notify_daily_failure.py <run_url>
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import push_wechat  # noqa: E402

ISSUES = ROOT / "data" / "issues"
DATA = ROOT / "data"


def _today_cn() -> str:
    """北京时间的今天。日报按北京时间出刊，UTC 会在跨日槽位上错一天。"""
    return (dt.datetime.now(dt.timezone.utc)
            .astimezone(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d"))


def main() -> int:
    run_url = sys.argv[1] if len(sys.argv) > 1 else ""
    today = _today_cn()
    snap = ISSUES / f"{today}.json"

    if snap.exists():
        # 当期已经建成了 —— 本槽失败多半是 push 竞态或 deploy 抖动，后续槽会自愈。
        # 这种情况【不告警】，否则狼来了几次就会被静音。
        print(f"↻ 当期快照 {snap.name} 已存在，本槽失败不算停更，不推告警")
        return 0

    lines = [f"**{today} 的日报没有生成。**", ""]
    # 附一点上下文，便于判断是数据问题还是流程问题
    try:
        pool = json.loads((DATA / "pool.json").read_text(encoding="utf-8"))
        lines.append(f"- 曲池 {len(pool)} 首（池空会让 build_daily 直接 SystemExit）")
    except Exception as e:
        lines.append(f"- 读 pool.json 失败：{e}  ← 很可能就是原因")
    try:
        n_snap = len(list(ISSUES.glob("*.json")))
        last = sorted(p.stem for p in ISSUES.glob("*.json"))
        lines.append(f"- 已有 {n_snap} 期，最后一期 {last[-1] if last else '（无）'}")
    except Exception:
        pass
    lines += [
        "",
        "当天还有后续 cron 槽会重试；**若到 09:31 那槽仍未收到日报推送，就是真停更**。",
        "",
        f"👉 [看这次的运行日志]({run_url})" if run_url else "看 Actions 日志。",
    ]

    ok = push_wechat.push(f"⚠️ 日报未生成 · {today}", "\n".join(lines))
    print(f"[notify_daily_failure] {today} 无快照 → 已告警，pushed={ok}")
    # 告警本身失败不改变 job 结论（job 已经是 failure 了）
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
