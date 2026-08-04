"""部署后校验 + 通知（P2-11）。先 HTTP 校验已部署页面可访问，再发微信。

- 页面校验失败 → 退出非零（daily workflow 明确失败，且不发"日报已更新"）。
- 页面 OK 但微信失败 → 仍退出 0（不回滚日报，仅告警）。
- 无 PAGES_URL → 报配置错误退出非零，绝不用本地 file://。
用法：python3 scripts/notify_after_deploy.py <deployed_url>
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def _daily_url(base: str) -> str:
    """日报本体的 URL。index.html 是开机自检落地页，标记不在那儿。"""
    b = base.rstrip("/")
    if b.endswith(".html"):
        b = b.rsplit("/", 1)[0]
    return b + "/daily.html"


def _http_ok(url: str) -> tuple[bool, str]:
    for attempt in range(6):  # Pages 部署后有传播延迟
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "music-daily-notify/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                body = r.read().decode("utf-8", "replace")
            if r.status == 200 and ("tracklist" in body.lower() or "今日精选" in body):
                return True, "ok"
            last = f"HTTP {r.status}, marker missing"
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(10)
    return False, last


def main() -> int:
    url = (sys.argv[1] if len(sys.argv) > 1 else "").strip() or os.environ.get("PAGES_URL", "").strip()
    if not url or url.startswith("file://"):
        print("❌ 未提供有效的已部署 URL（PAGES_URL 未配置）——绝不使用本地 file://。")
        return 3
    check = _daily_url(url)
    ok, detail = _http_ok(check)
    if not ok:
        print(f"❌ 部署校验失败：{check} → {detail}（不发送微信）")
        return 1
    print(f"✅ 部署校验通过：{check}")

    lp = DATA / "latest.json"
    latest = json.loads(lp.read_text(encoding="utf-8")) if lp.exists() else {}

    # 幂等键必须是「今天推送成功过吗」，不能是 fresh_build（「本次是否新建快照」）。
    # fresh_build 只看快照文件存不存在，与推送成功无关；而 latest.json 在 daily.yml
    # 的回写步骤（第 4 步）就提交了，远早于 deploy(6) 和本步(7)。
    # 于是首槽只要跑过回写，此后【任何】环节失败 —— deploy 挂 / HTTP 校验不过 /
    # Server酱 5xx（push_wechat 把所有异常吞成 False，本脚本只打印告警就 return 0、
    # job 全绿）—— 都会让当天剩下三个备份槽在这里提前 return，微信永久静默丢失。
    # 四个槽恰好被设计成「不重发」，一个都救不回来。
    #
    # 改成认 notified 标记：标记由本脚本在推送成功后写入，再由 daily.yml 新增的
    # post-notify 步骤提交（必须在本步之后，否则随 runner 销毁、跨 run 不存在）。
    # 退化方向也对：标记机制哪天失效 → 多推一条，而不是永久不推。
    today = latest.get("date", "")
    if latest.get("notified") == today and today:
        print(f"↻ 本期（{today}）已推送成功过，跳过重复推送")
        return 0
    import push_wechat  # 延迟导入
    tracks = latest.get("tracks_brief", [])
    # total 传 latest["n"]（当期真实曲目数），不能用 len(tracks)——
    # tracks 是 tracks_brief，只有 6 条摘要。
    title, desp = push_wechat.build_desp(
        latest.get("date", ""), check, tracks,
        warn=latest.get("low_pool_warn"), total=latest.get("n"))
    if push_wechat.push(title, desp):
        print("✅ 微信推送成功")
        # 写 notified 标记；提交由 daily.yml 的 post-notify 步骤负责。
        # 写盘失败不影响本次结论（已经推成功了），只会导致下一槽多推一条。
        try:
            latest["notified"] = today
            lp.write_text(json.dumps(latest, ensure_ascii=False, indent=1),
                          encoding="utf-8")
            print(f"   已写 notified={today}（待 post-notify 步骤提交）")
        except Exception as e:
            print(f"   ⚠️ notified 标记写盘失败：{e}（下一槽可能重复推送）")
    else:
        # 【不写标记】—— 这正是修复的核心：推送失败时必须让后续槽位有机会重试。
        print("⚠️ 微信推送失败或未配置 key——页面已部署成功，不回滚，仅告警")
        print("   未写 notified 标记，当天后续 cron 槽会重试推送")
    return 0


if __name__ == "__main__":
    sys.exit(main())
