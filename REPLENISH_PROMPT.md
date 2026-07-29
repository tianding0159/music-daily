# 用ChatGPT（或任意联网LLM）补池 · 操作说明 + 提示词

这套让ChatGPT Plus与内置补池**同一套方法、同一条验真管线**，能力对齐（GPT联网找歌可能更强）。
你负责"创作"（让GPT产出候选JSON），仓库负责"落地"（自动验真+去重+进池+部署）。

## 怎么用（三步，零本地环境）

1. **喂料给GPT**：新开一个开了「联网/搜索」的ChatGPT对话，**上传这3个文件** + 粘贴下方提示词：
   - `docs/profile.md`（口味依据）
   - `docs/style_bible.md`（文案文风）
   - 当前"已有艺人"清单 —— 跑 `python3 scripts/merge_candidates.py --context` 拿到；或直接在GitHub上打开 `data/pool.json` 看。（避免推重复；即便重复了，管线也会自动丢弃）
2. **拿JSON**：GPT会输出一个JSON数组。**整段复制**。
3. **落地**：在GitHub网页进入你的仓库 → `candidates/` 目录 → **Add file → Create new file** → 文件名如 `candidates/2026-08-01.json` → 粘贴JSON → Commit。
   之后 `merge.yml` 会自动 **iTunes验真 + 去重 + 打标签 → 写进pool.json**，随下一期生效。（假曲/重复/黑名单流派会被自动剔除）

> 也可本地跑：`python3 scripts/merge_candidates.py 你的文件.json`（先 `--dry-run` 预览）。
> 或把JSON直接发我（Claude），我帮你合。

---

## 提示词（复制以下全部，连同上传的3个文件一起发给GPT）

你是顶尖独立音乐策展人 + 中文乐评写手。请根据我上传的 `profile.md`（口味）与 `style_bible.md`（文案文风），为我的"每日音乐日报"候选池**发现50首新曲目**。

**策展总开关**：像Pitchfork编辑 + Bandcamp Daily选曲人 + Resident Advisor的电子乐耳朵 + 一个听了二十年独立音乐的朋友一起推荐——找那些一听就想收藏、一个月后还在循环、十年后依然想起的作品。不追猎奇、不追冷门、不追评分、不追热门。

**硬要求**：
1. 严格按 `profile.md`：按气质+制作+旋律选，不按流派；旋律必须存在；命中黑名单（EDM/dubstep/metal/hyperpop/math rock炫技/jazz fusion炫技/只有氛围没旋律的ambient等）一律排除。
2. **别保守**：以profile里的锚点艺人为圆心，找**相邻、更深、我大概率没听过**的艺人与作品。`familiarity` 多数取 `likely-unheard`，`classic-known` 全批最多2首。新旧release不限。
3. **避开我已有的艺人**（见上传的"已有艺人"清单），尽量换新艺人。
4. **务必联网核实每一首真实存在**（Bandcamp / RateYourMusic / Wikipedia / 厂牌页可查），**绝不编造曲名或艺人**；拿不准的不要放。（落地端会用iTunes再验一次，验不到的会被丢弃——所以请挑真实、且大概率在流媒体/iTunes有的曲目。）
5. 三段中文文案严格按 `style_bible.md`：具体压过抽象、画面压过形容词、术语接人话、避开陈词黑名单；`why` ≤ 2句。每条都要通过"能不能原样搬到另一首歌上"的测试。
6. `genres` 用于流派加权与黑名单过滤、`mood_tags` 用于每期气质多样性、`has_melody` 用于硬过滤——请如实、准确填写。

**只输出一个JSON数组，不要任何解释、不要markdown代码围栏**，每个元素：
```json
{"title":"","artist":"","year":"","album":"","genres":["流派1","流派2"],"mood_tags":["气质1","气质2"],"production_tags":["制作特征"],"instrumentation":["乐器"],"vocal_style":"","bpm_band":"70–120","has_melody":true,"familiarity":"likely-unheard","scene":"一个具体到时辰/光线/身体动作的私人时刻","artist_oneliner":"谱系/坐标+一个只对他成立的具体特征","why":"具体声音/制作/情绪锚点+带力度的动词+一个可触画面+克制判断，≤2句","source":"信息来源如 Bandcamp Daily","source_url":"https://..."}
```
