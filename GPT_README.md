# 给GPT的资料总入口

分工：**GPT写内容，Claude负责导入与校验。**

## 三份文件，按任务挑

| 你要做的事 | 先读 | 再读 |
|---|---|---|
| **补库**（找新曲目） | [`GPT_CATCHUP.md`](GPT_CATCHUP.md) — 规则变更 | [`GPT_VOICE.md`](GPT_VOICE.md) — 怎么写文案 |
| **写艺人简介** | [`GPT_ARTIST_BIOS.md`](GPT_ARTIST_BIOS.md) — 任务书 | [`GPT_VOICE.md`](GPT_VOICE.md) — 用语口径 |

补充材料（需要时再看）：
- [`docs/profile.md`](docs/profile.md) — 用户口味画像（选曲唯一依据）
- [`docs/style_bible.md`](docs/style_bible.md) — 文风完整规范（`GPT_VOICE.md` 是它的操作版）
- [`REPLENISH_PROMPT.md`](REPLENISH_PROMPT.md) — 补库原始提示词（与 `GPT_CATCHUP.md` 冲突时**以catchup为准**）
- [`data/artists_todo.json`](data/artists_todo.json) — 待写简介的艺人清单（1054位，按本站收录曲目数降序）

## 最容易踩的四条

1. **`mood_tags` 只能从32个受控英文词照抄**，写近义词会被拒（见CATCHUP第1节）
2. **「空气感」「颗粒感」在文案里禁用，但 `airy`/`grainy` 是合法tag** —— tag给机器分类，文案给人读，两套标准
3. **`why` 严格 ≤ 2句**，超了直接拒收
4. **艺人简介不是oneliner的扩写**，要给可核实的事实（见BIOS开头的正反例）

## 交付

产出JSON直接发给Claude，他跑校验管线后把体检报告发回来，被拒的会逐条说原因。
也可以自己放进repo的 `candidates/` 目录（仅补库），CI会自动处理。

## 当前状态（2026-08-03）

- 曲池 **1169首**，封面覆盖99.0%，约31天供给
- 艺人简介 **32 / 1084位**
- 仍偏缺的补库方向：非英语世界（日语/韩语/西语/北欧/中东/非洲）、器乐（约17%）、明快上扬（`upbeat` `hopeful`）、BPM <70与 >125、1950–1969年代
