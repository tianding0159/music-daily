# 每日音乐日报 · Daily Music Report

每天早8:00（北京时间）自动更新的音乐日报：按口味profile精选 **30首**，
工业 / 工程风格网页（专辑封面 + 艺人/专辑介绍 + 推荐理由 + 场景 + 官方播放页/网易云外链），
并附一份可一键复制的网易云导入文本。发布到GitHub Pages，可选发一条微信推送提醒。

## 怎么运作（发现与投递解耦）

```
[发现·定期·重]  乐评/社区  ──►  data/pool.json 常青候选池（打好美学标签 + 写好卡片）
[投递·每期·轻]  纯脚本：黑名单硬过滤 → 旋律必须 → 打分 → 按气质多样性挑 30 首
                → 补封面/官方播放页链接 → 写 issue 快照 → 从快照重建 archive+index → 部署成功后推微信
                (build_daily.py，GitHub Actions 每天定时跑；跨期绝不重复)
```

选曲依据「气质 + 制作 + 旋律」而非流派：旋律必须存在，好听 > 耐听 > 制作 > 气质 > 易循环 >
审美，不因经典/高分/热门而选；命中黑名单（EDM/metal/math rock炫技等）一律排除。

## 目录

```
data/     pool.json(候选池) · history.json(去重记录) · itunes_cache.json(封面缓存)
          artists.json(艺人简介) · issues/YYYY-MM-DD.json(每期快照)
docs/     profile.md(口味依据) · style_bible.md(文案文风规范)
scripts/  build_daily.py(主编排) · picker.py(选曲) · itunes.py(封面/试听)
          render_landing.py(落地页) · render_grid.py(日报) · render_random.py(随机页)
          lightbox.py(封面浮层) · netease.py · push_wechat.py
tools/    make_icons.py(生成 PWA 图标) · check_site_assets.sh(发布前非空守卫)
          healthcheck 等自查脚本见 scripts/
site/     ← GitHub Pages 发布目录
          index.html   落地页（黑胶上机，点「drop the needle」进日报）
          daily.html   最新一期
          random.html  从全池随机抽一首
          archive/YYYY-MM-DD.html + archive/index.html  往期
          manifest.webmanifest · icon-{192,512,180,maskable-512}.png
                       PWA 资源：加到手机主屏后有图标、全屏无地址栏。
                       【静态签入，不由任何脚本重新生成】——误删后页面照开、
                       只是静默少几个请求，所以 check_site_assets.sh 点名守它们。
.github/workflows/
          daily.yml         每日定时构建 + 部署（含非空守卫）
          publish-site.yml  从 data/ 离线重建 site/ 并部署（修正产物滞后）
```

## 本地运行（先看效果）

```bash
python3 scripts/build_daily.py --theme grid --date 2026-07-28   # 生成 site/ 全套页面
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
4. `daily.yml` 触发：**每天定时 + 手动workflow_dispatch**（与候选合并解耦：普通push / 候选入库不触发日报）。候选合并由 `merge.yml`（push `candidates/**.json` 时）负责。

## 运维与授权

- 运维手册（节奏 / 合并 / 回滚 / canary / 库存指标，事实源）：见 [`docs/operations.md`](docs/operations.md)。
- 用ChatGPT补库：见 [`GPT_WEEKLY.md`](GPT_WEEKLY.md)（曲目 + 艺人简介一次交付，含可直接粘给 GPT 的指令）。
- 授权：**代码MIT**（`LICENSE`）；**口味画像 / 文案 / 曲库等内容保留所有权利**（`CONTENT_LICENSE.md`）。
- 页面不内嵌音频，仅官方播放页外链；封面来自iTunes/Apple公开接口，无官方合作关系。

## 补充候选池（保持新鲜）

候选池随每期轮播消耗；不足一期时，日报会在微信提醒补池。补池 = 按 `docs/profile.md`
的口味与 `docs/style_bible.md` 的文风，核实真实（Bandcamp/RYM/Wikipedia可查）后打好美学
标签、写好卡片，append进 `pool.json`。**绝不编造曲名。**

## 微信推送

支持 [Server酱Turbo](https://sct.ftqq.com/)（默认）或 [PushPlus](https://www.pushplus.plus/)，
均免费、扫码绑微信即得一个key/token。key只存GitHub Secret，绝不写进代码。
