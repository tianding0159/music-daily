# 每日音乐日报 · Daily Music Report

每天早上8:00（北京时间）自动更新的个人音乐日报：按你的口味profile精选15首，
Apple Music风格网页（专辑封面 + 30s试听 + 艺人/专辑介绍 + 推荐理由 + 场景），
并附一份可一键复制的网易云导入文本。发布到GitHub Pages，另发一条微信推送提醒。

> **这是纯个人项目**，请部署在你的**个人（非公司）GitHub账号**下——只有个人账号才能公开
> Pages（手机浏览器免登录直开）、用官方Actions、享免费额度。不含任何公司数据。

## 它怎么运作（发现与投递解耦）

```
[发现·定期·重]  乐评/社区  ──►  data/pool.json 常青候选池（打好美学标签+写好卡片）
                (discover.py + LLM 策展)
[投递·每天·轻]  纯脚本：黑名单硬过滤 → 旋律必须 → 打分 → 按气质多样性挑 15 首
                → iTunes 补封面/试听/Apple链接 → 渲染网页 → 更新 history 去重 → 微信推送
                (build_daily.py，GitHub Actions 每天定时跑)
```

选曲依据「气质 + 制作 + 旋律」而非流派：旋律必须存在，好听 > 耐听 > 制作 > 气质 > 易循环 >
审美，不因经典/高分/热门而选；命中黑名单（EDM/metal/math rock炫技等）一律排除。

## 目录

```
data/     pool.json(候选池) · history.json(去重记录) · itunes_cache.json(封面缓存)
scripts/  build_daily.py(主编排) · picker.py(选曲) · itunes.py(封面/试听)
          render.py(网页) · netease.py(网易云文本) · push_wechat.py(推送) · discover.py(补池)
site/     index.html(最新一期) · archive/YYYY-MM-DD.html(存档)  ← GitHub Pages 发布目录
.github/workflows/daily.yml   定时任务
```

## 本地运行（先看效果，零GitHub）

```bash
python3 scripts/build_daily.py --date 2026-07-28     # 生成 site/index.html
python3 -m http.server -d site 8899                  # 浏览器开 localhost:8899
# 可选：--push 发微信；--no-itunes 离线跳过封面查询
```

## 上线到你的个人GitHub（每日自动）

1. 在**个人GitHub** 建repo（如 `music-daily`），把本目录推上去。
2. Settings → **Pages** → Source选 **GitHub Actions**。
3. Settings → Secrets and variables → Actions：
   - **Secret** `WECHAT_PUSH_KEY` —— Server酱SendKey或PushPlus token
   - **Variable** `PAGES_URL` —— 你的Pages地址（如 `https://<用户名>.github.io/music-daily/`）
   - **Variable** `WECHAT_PUSH_PROVIDER` —— `serverchan`（默认）或 `pushplus`
   - 可选 **Secret** `TAVILY_API_KEY` —— 给discover.py补池搜索用
4. Actions页手动 **Run workflow** 触发一次，确认Pages更新 + 微信收到推送。
   之后每天北京时间8:00自动跑（GitHub cron偶有几分钟延迟，正常）。

## 补充候选池（保持新鲜）

候选池会随每日轮播消耗，定期补新：

```bash
python3 scripts/discover.py     # 按 profile 搜候选线索 → data/discover_leads.json
```

再由LLM按 `discover.py` 里的 `CURATION_PROMPT`（策展总开关）把线索**核实真实 + 打全套美学
标签 + 写卡片**，append进 `pool.json`。**绝不编造曲名**，每条要可在Bandcamp/RYM/Wikipedia查到。

## 微信推送

支持 [Server酱Turbo](https://sct.ftqq.com/)（默认）或 [PushPlus](https://www.pushplus.plus/)，
都免费、扫码绑微信即得一个key/token。key只存GitHub Secret，绝不写进代码。
