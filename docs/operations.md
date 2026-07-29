# 运维说明（operations）· 事实源

仓库是运行规则的唯一事实源，不依赖聊天记忆。

## 节奏与分工

- **每天** 北京时间约 **08:11** 发布 **30首**（`.github/workflows/daily.yml`，cron `11 0 * * *`）。
- **每周日22:00** 由 **ChatGPT** 联网发现、写文案、提交候选（约 **225首**/周，覆盖每周约210展示位 + 过滤余量；不得降标凑数）。
- **仓库**负责：schema校验、iTunes精确版本匹配、去重、入库、隔离、日报构建与部署。
- **Claude** 负责：仓库代码维护与复杂迁移。
- 口味唯一依据 `docs/profile.md`；文案唯一标准 `docs/style_bible.md`。
- 架构：纯Python标准库 + 静态GitHub Pages + 发现/投递解耦。不引入DB / React / 后端 / 多余第三方框架。

## 候选合并（merge）与失败处理

- 候选JSON传到 `candidates/*.json` → `merge.yml` 触发（与daily解耦，入库后不立即发日报，新曲随下一次daily生效）。
- 流程：`validate_candidates` schema校验 → canonical去重 → 黑名单 → `itunes` 精确版本匹配。
- 分流：
  - **成功**（exact/acceptable）→ 写入 `data/pool.json`。
  - **不合格**（schema / 重复 / 版本错配 / 艺人错配 / not_found / 黑名单）→ `quarantine/YYYY-MM-DD.json`（附原因），不静默删除。
  - **transient_error**（超时/429/5xx/DNS/JSON异常）→ 整批 **fail-closed**：不写盘、不删候选、脚本非零退出、下次重试（指数退避 + Retry-After + 限流 ~3s/请求）。
- 报告：`reports/merge/YYYY-MM-DD.json` + GitHub Actions Step Summary。

## 常用操作

```bash
# 手动跑一期日报（本地预览）
python3 scripts/build_daily.py                       # 北京当天
python3 scripts/build_daily.py --date 2026-08-03
python3 scripts/build_daily.py --force-rebuild       # 重生成当期快照（默认当天幂等复用）
python3 scripts/build_daily.py --no-itunes           # 离线（占位封面）

# 手动触发线上日报 / 合并
gh workflow run daily.yml -R <owner>/music-daily
gh workflow run merge.yml -R <owner>/music-daily

# 数据健康 / 测试 / 迁移
python3 scripts/healthcheck.py                        # P0 问题非零退出
python3 tests/test_catalog.py                         # 离线测试
python3 scripts/migrate_catalog.py --apply            # 一次性目录迁移（写盘前自动备份 .backup/）

# 补库辅助
python3 scripts/merge_candidates.py --context         # 导出"已有艺人"清单喂 LLM 避重
python3 scripts/merge_candidates.py --dry-run f.json  # 预览某候选文件的分流结果
python3 scripts/validate_candidates.py f.json         # 只跑 schema 校验
```

## 回滚

- 日报页面是可重建产物：`site/` 每次由 `data/issues/*.json` 快照全量重建；改回快照或代码后重跑 `build_daily` 即可。
- 数据迁移前自动备份到 `.backup/`（本地，未入库）；异常时从备份恢复 `data/pool.json` / `data/history.json`。
- pool变更走git，可 `git revert` 对应提交后重跑。

## 发布链路与检查

- daily：构建 → 提交状态(history/issues/latest/缓存/site) → 上传Pages制品 → 部署 → **部署成功且HTTP 200才发微信**（`notify_after_deploy.py`）。部署失败则workflow失败、不发"已更新"；微信失败不回滚日报。
- 检查Pages：`curl -s https://<owner>.github.io/music-daily/ | grep -c 'class="mod"'`（应为30）。

## 库存健康（healthcheck输出）

- 指标：total / eligible / recently_sent / fresh / est_days_supply。
- 目标：活跃合格库存 ≥ 约 **1350** 首（≈45期 × 30）；< 1050预警、< 900高风险。
- 每周225首补库：每日30 × 7 = 210展示位/周，理论安全余量约15；经去重/错版/验真过滤后实际入池可能 < 225，**不得为补足过滤损耗而塞次等歌**。

## 首次正式225补库前的验收（canary）

先用 **25首标准候选** 跑通：schema → 精确验真 → 错版检查 → 去重 → 入库 → merge report → 手动构建一期 → 检查issue快照 / archive / 外链 / 无站内试听 / 微信仅部署成功后发送。全过后才允许每周225首自动补库。
