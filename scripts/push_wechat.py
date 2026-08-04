"""微信推送：Server酱 Turbo（默认）或 PushPlus，发一条「今日日报已更新 + 链接」。

密钥从环境变量读，绝不写进代码/git：
  WECHAT_PUSH_KEY       —— Server酱 的 SendKey，或 PushPlus 的 token
  WECHAT_PUSH_PROVIDER  —— serverchan（默认）| pushplus
纯标准库。无 key 时跳过（本地开发不阻塞），返回 False。
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request


def _post(url: str, data: dict, form: bool = True) -> tuple[int, str]:
    if form:
        body = urllib.parse.urlencode(data).encode()
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
    else:
        body = json.dumps(data).encode()
        headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, r.read().decode("utf-8", "replace")


def push(title: str, desp_md: str, key: str | None = None,
         provider: str | None = None) -> bool:
    key = key or os.environ.get("WECHAT_PUSH_KEY", "")
    provider = (provider or os.environ.get("WECHAT_PUSH_PROVIDER", "serverchan")).lower()
    if not key:
        print("[push_wechat] 未配置 WECHAT_PUSH_KEY，跳过推送")
        return False
    try:
        if provider == "pushplus":
            status, resp = _post(
                "https://www.pushplus.plus/send",
                {"token": key, "title": title, "content": desp_md, "template": "markdown"},
                form=False,
            )
        else:  # serverchan turbo
            status, resp = _post(
                f"https://sctapi.ftqq.com/{key}.send",
                {"title": title, "desp": desp_md},
            )
        ok = status == 200 and '"code":0' in resp.replace(" ", "")
        print(f"[push_wechat] {provider} status={status} ok={ok}")
        return ok
    except Exception as e:
        print(f"[push_wechat] 推送失败：{type(e).__name__}: {e}")
        return False


def build_desp(date_str: str, url: str, tracks: list[dict],
               warn: str | None = None, total: int | None = None) -> tuple[str, str]:
    """返回 (title, markdown desp)。列前几首勾一下胃口；warn 非空时附低池预警（A 方案）。

    total：当期【真实】曲目数。必须与 tracks 分开传 —— tracks 是
    latest.json 的 tracks_brief，只有 6 条摘要，不是整期。
    2026-08-04 审计抓到：旧代码拿 len(tracks) 当总数，于是每天推送都写
    「今日 6 首已更新」，而实际是 30 首。真值在 latest.json 的 n 字段里，
    此前没人用。缺省回退到 len(tracks) 只为兼容直接调用的场景。
    """
    n = total if total is not None else len(tracks)
    title = f"🎵 今日音乐日报 · {date_str} · {n}首"
    lines = [f"**{date_str} 今日 {n} 首已更新**", "", f"👉 [点开今日日报]({url})", ""]
    for t in tracks[:5]:
        lines.append(f"- {t['title']} — {t['artist']}")
    if n > 5:
        lines.append(f"- …等共 {n} 首")
    if warn:
        lines += ["", "---", warn]
    return title, "\n".join(lines)


if __name__ == "__main__":
    import sys

    u = sys.argv[1] if len(sys.argv) > 1 else "https://example.github.io/music-daily/"
    t, d = build_desp("2026-07-28", u, [{"title": "Lovers' Carvings", "artist": "Bibio"}])
    push(t, d)
