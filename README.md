# 每日音乐日报 · Daily Music Report

每天早8:00（北京时间）自动更新的音乐日报：按口味profile精选 **30首**，
工业 / 工程风格网页（专辑封面 + 30s试听 + 艺人/专辑介绍 + 推荐理由 + 场景），
并附一份可一键复制的网易云导入文本。发布到GitHub Pages，可选发一条微信推送提醒。

## 怎么运作（发现与投递解耦）

```
[发现·定期·重]  乐评/社区  ──►  data/pool.json 常青候选池（打好美学标签 + 写好卡片）
[投递·每期·轻]  纯脚本：黑名单硬过滤 → 旋律必须 → 打分 → 按气质多样性挑 30 首
                → 补封面/试听/官方播放页链接 → 渲染网页 → 更新 history 去重 → 微信推送
                (build_daily.py，GitHub Actions 每天定时跑；跨期绝不重复)
```

选曲依据「气质 + 制作 + 旋律」而非流派：旋律必须存在，好听 > 耐听 > 制作 > 气质 > 易循环 >
审美，不因经典/高分/热门而选；命中黑名单（EDM/metal/math rock炫技等）一律排除。

## 目录

```
data/     pool.json(候选池) · history.json(去重记录) · itunes_cache.json(封面缓存)
docs/     profile.md(口味依据) · style_bible.md(文案文风规范)
scripts/  build_daily.py(主编排) · picker.py(选曲) · itunes.py(封面/试听)
          render_grid.py(默认皮肤·工业风) · render.py(可选皮肤·浅色卡片) · netease.py · push_wechat.py
site/     index.html(最新一期) · archive/YYYY-MM-DD.html(存档)  ← GitHub Pages 发布目录
.github/workflows/daily.yml   定时/推送触发的构建与部署
```

## 本地运行（先看效果）

```bash
python3 scripts/build_daily.py --theme grid --date 2026-07-28   # 生成 site/index.html
python3 -m http.server -d site 8899                           # 浏览器开 localhost:8899
# 可选：--push 发微信；--no-itunes 离线跳过封面查询
```

## 部署（每天自动）

1. 建repo，把本目录推上去。
2. Settings → **Pages** → Source选 **GitHub Actions**。
3. Settings → Secrets and variables → Actions：
   - **Secret** `WECHAT_PUSH_KEY` —— Server酱SendKey或PushPlus token
   - **Variable** `PAGES_URL` —— Pages地址（如 `https://<用户名>.github.io/music-daily/`）
   - **Variable** `WECHAT_PUSH_PROVIDER` —— `serverchan`（默认）或 `pushplus`
4. `daily.yml` 触发：每天定时 + push到 `main` 即部署 + 可手动Run workflow。

## 补充候选池（保持新鲜）

候选池随每期轮播消耗；不足一期时，日报会在微信提醒补池。补池 = 按 `docs/profile.md`
的口味与 `docs/style_bible.md` 的文风，核实真实（Bandcamp/RYM/Wikipedia可查）后打好美学
标签、写好卡片，append进 `pool.json`。**绝不编造曲名。**（`discover.py` 可辅助搜候选线索。）

## 微信推送

支持 [Server酱Turbo](https://sct.ftqq.com/)（默认）或 [PushPlus](https://www.pushplus.plus/)，
均免费、扫码绑微信即得一个key/token。key只存GitHub Secret，绝不写进代码。
