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
    ok, detail = _http_ok(url)
    if not ok:
        print(f"❌ 部署校验失败：{url} → {detail}（不发送微信）")
        return 1
    print(f"✅ 部署校验通过：{url}")

    import push_wechat  # 延迟导入
    latest = json.loads((DATA / "latest.json").read_text(encoding="utf-8")) if (DATA / "latest.json").exists() else {}
    tracks = latest.get("tracks_brief", [])
    title, desp = push_wechat.build_desp(latest.get("date", ""), url, tracks, warn=latest.get("low_pool_warn"))
    if push_wechat.push(title, desp):
        print("✅ 微信推送成功")
    else:
        print("⚠️ 微信推送失败或未配置 key——页面已部署成功，不回滚，仅告警")
    return 0


if __name__ == "__main__":
    sys.exit(main())
