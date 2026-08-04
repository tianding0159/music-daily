# 给GPT的资料总入口

分工：**GPT写内容，Claude负责导入与校验。**

## 先读这一份

**[`GPT_MEMORY.md`](GPT_MEMORY.md) — 长期记忆台账。** 每次开新对话第一件事读它：
当前进度、**已写过哪些艺人（别重复写）**、接下来该写谁、踩过的坑、交付清单。
自动生成、不会过期。

## 然后按任务挑

| 你要做的事 | 先读 | 再读 |
|---|---|---|
| **补库**（找新曲目） | [`GPT_CATCHUP.md`](GPT_CATCHUP.md) — 导入硬规则 | [`GPT_TERRITORIES.md`](GPT_TERRITORIES.md) — 20 个领地搜索策略<br>[`GPT_VOICE.md`](GPT_VOICE.md) — 怎么写文案 |
| **写艺人简介** | [`GPT_ARTIST_BIOS.md`](GPT_ARTIST_BIOS.md) — 任务书 | [`GPT_VOICE.md`](GPT_VOICE.md) — 用语口径 |

补充材料（需要时再看）：
- [`docs/profile.md`](docs/profile.md) — 用户口味画像（选曲唯一依据）
- [`docs/style_bible.md`](docs/style_bible.md) — 文风完整规范（`GPT_VOICE.md` 是它的操作版）
- [`GPT_WEEKLY.md`](GPT_WEEKLY.md) — **每周补库的运行入口**（曲目 + 艺人简介一次交付）
- [`data/artists_todo.json`](data/artists_todo.json) — 待写简介的艺人清单（按本站收录曲目数降序，每次导入后自动刷新）

## 最容易踩的四条

1. **`mood_tags` 只能从32个受控英文词照抄**，写近义词会被拒（见CATCHUP第1节）
2. **「空气感」「颗粒感」在文案里禁用，但 `airy`/`grainy` 是合法tag** —— tag给机器分类，文案给人读，两套标准
3. **`why` 严格 ≤ 2句**，超了直接拒收
4. **艺人简介不是oneliner的扩写**，要给可核实的事实（见BIOS开头的正反例）

## 交付

**中文务必 `ensure_ascii=True`（写成 `\uXXXX`）并随附 SHA-256** —— 上一批 bio 就是没这么做，
传输中被吞掉 `0x80-0x9F` 字节、90% 汉字不可复原、整批作废。

- **艺人简介** → 传仓库 `inbox/bios/`（GitHub 网页 Add file 即可）。CI 自动核 SHA、校验、
  导入、重建、部署；任一环节不过就**整批拒绝并保留文件等修正**，不会污染数据。
  详见 [`inbox/bios/README.md`](inbox/bios/README.md)。
- **补库候选** → 传 `candidates/` 目录，CI 自动验真去重入库。
- 也可以直接发给 Claude，他跑校验管线后把体检报告发回来，被拒的会逐条说原因。

## 当前状态

数字全在 **[`GPT_MEMORY.md`](GPT_MEMORY.md)** 里（自动生成，永远是最新的）。
这里不再重复维护——手写的数字一定会过期。
