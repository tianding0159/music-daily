# 给GPT的catchup：补库规则更新（2026-08-03）

> 这份只讲**曲目字段的硬规则**。整个每周补库流程、交付格式、给 GPT 的指令见
> [`GPT_WEEKLY.md`](GPT_WEEKLY.md)（它是运行入口，本文是它引用的字段参考）。
> 冲突时：**以 `GPT_WEEKLY.md` 为准**（它是运行入口）；`GPT_WEEKLY.md` 未涉及的
> 字段级规则以本文为准。
>
> 必须是两段式 —— `GPT_WEEKLY.md` §四那张表是本文字段规则的【有损子集】，
> 未提 classic-known 全批 ≤2、单艺人 ≤3、`bpm_band` 必须区间、`has_melody`
> 必须显式 true、`source_url` 必须 https。只写「以 WEEKLY 为准」会让这些规则
> 看起来不存在。

## TL;DR：四条硬变更

| # | 变更 | 违反的后果 |
|---|---|---|
| 1 | `mood_tags` 只能从 **32个受控英文词**里选 | schema校验直接拒收，整首不进库 |
| 2 | `genres` 一律**小写英文** | 不拒收，但会在筛选器里分裂成大小写两类 |
| 3 | 文案黑名单 **47个词**，其中 7 个是条件豁免词 | 40 词命中即拒收；7 个豁免词只告警（bio 通道全部硬拒）|
| 4 | 版本错配判定更严：iTunes只认 `exact_match` / `acceptable_match` | 落到Remaster/Live/别人的同名曲 → 隔离，不进库 |

---

## 1. mood_tags：32个受控英文词，只能照抄

**为什么改**：池里曾累积出 **357个不同mood tag**，其中250+ 只出现过一次（「缺一角」「圆钝」「不悲的告别」这种一次性词）。而mood_tags的用途只有两个——①随机页的筛选下拉 ②每期的气质多样性配额。357个类别对这两件事都等于没分类：下拉拉不完，多样性算法把同义词当成不同气质，一期里挑三首同气质还以为凑够了反差。

现在收敛成32个，**tag一律用英文，不再用中文硬凑**。

每首选 **2–3个**，只能从下表照抄（大小写、空格都要一致）：

```
时间与场所   late night · summer dusk · rainy · wide open · wintry
质感与制作   airy · grainy · woody · hazy · floating · shimmering · organic · lush
情绪         tender · warm · sweet · melancholy · longing · fragile · restrained ·
             introspective · nostalgic · hopeful · restless · sensual · dreamlike ·
             intimate · cinematic
律动         unhurried · upbeat · human · elegant
```

**注意**：写「city night」「nocturnal」「怀旧又现代」这类近义词**会被拒收**——历史别名表只用于兼容老数据，不作为准入白名单（这一点我们自己踩过：一开始用别名表判准入，结果「缺一角」「圆钝」这些正要淘汰的旧写法反而被放行了）。

## 2. genres：小写英文

之前池里有 **44组大小写分身**（`Dream Pop` 40首 / `dream pop` 77首被当成两个流派）。现在统一小写，页面靠CSS转大写显示。

正确：`["dream pop", "neo soul"]` · `["ethio-jazz"]` · `["mpb"]`
错误：`["Dream Pop"]` · `["Neo Soul"]`

## 3. 文案黑名单：47个词（曲目通道硬拒 40 + 豁免 7），注意两个「反直觉」的

命中任一即拒收（扫 `artist_oneliner` / `why` / `scene` 三段）：

```
一听就上头  一整个爱住  令人陶醉  仿佛置身  余音绕梁  值得单曲循环  净化  后劲很大
听觉盛宴  大气  天籁  天籁之音  天花板  如梦如幻  如痴如醉  娓娓道来
宝藏专辑  宝藏歌手  封神  层层递进  带你走进  干净的嗓音  慵懒  教科书级
明亮的音色  殿堂级  氛围感拉满  沉浸式  治愈  洗涤心灵  涤荡  温暖的旋律
直击灵魂  磅礴  神仙旋律  空气感  空灵  绝绝子  缓缓流淌  耳朵怀孕
让人沉浸其中  质感满满  醉人  闭上眼仿佛  震撼人心  颗粒感  高级感
```

**反直觉的两个**：`空气感` 和 `颗粒感` **在文案里禁用**，但 `airy` / `grainy` **是合法的mood tag**。
区别是：tag是给机器做分类用的标签，文案是给人读的句子。文案里要写具体的声音证据（「高频收得很干净，人声浮在上面半寸」），不能用这种已经被用滥的抽象形容词。

**还有一类硬规则**（不在黑名单但会被占比告警拦）：
- `artist_oneliner` 里破折号同位语（`——`）占比 ≤ 30%
- `scene` 末4个字相同的最高频模式 ≤ 30%（**别都用「…的时候。」收尾**）
- `scene` 起句时间词（深夜/凌晨/傍晚/夏天/午后/清晨/周末/雨）≤ 35%
- `让人` / `令人` 出现 **0次**
- `why` **≤ 2句**（按句号计）

**范例句禁止原样入库**：`docs/style_bible.md` 里的示范句只是给你体感的，抄进JSON会被检出（我们真发生过4处）。

## 4. 版本错配：只认exact / acceptable

落地端会用iTunes Search API逐首验真，只有两种状态会进库：

- `exact_match`：曲名与艺人名都对上
- `acceptable_match`：曲名对上，艺人是子串关系（如 `Beach House feat. X`）

以下一律**隔离，不进库**：

| 状态 | 含义 | 你能做什么 |
|---|---|---|
| `version_mismatch` | 只找到Remaster / Live / Remix / Album Mix / Acoustic / Edit版 | 要么在title里如实声明该版本，要么换一首 |
| `artist_mismatch` | 匹到同名的**别人** | 换一首，或确认艺人名拼写 |
| `not_found` | iTunes上查不到 | 换一首（太冷门就别收） |

**为什么这么严**：库里曾长期挂着5首错数据在页面上展示——`Ride On Time — Tatsuro Yamashita` 匹到了别人的同名曲，两首落到Remaster版。根子是采纳时只看「有没有拿到封面」，而错版本/错艺人**也有封面**。**错数据比没封面更糟**，所以宁缺不错。

**两个已修的匹配bug**（你不用管，但影响你的选曲余地——现在这两类能过了）：
- 带重音的名字：`María También` 之前永远查不到（归一化把 `í` 整个吞了），现已修
- 「拉丁名 (原文名)」写法：`Ozora Kimijima (君島大空)` 之前必然判艺人不符，现已修

## 5. 其余仍然有效的硬规则（没变，但常被忽略）

- **绝不编造曲名或艺人**。iTunes验不到就白写。
- `year` 必须与所填 `album` 的**正式发行年**一致（单曲后收入专辑时，album填专辑则year用专辑年）。
- `bpm_band` 格式必须是区间：`70–120`（两位或三位数 + 连字号/波浪号）。写 `fast`、`~90` 会被拒。
- `source_url` 必须是 `https://`。
- `has_melody` 必须**显式为 `true`**（缺字段或false都拒）。
- `familiarity` 只能是 `likely-unheard` / `possibly-known` / `classic-known`，且 **classic-known全批最多2首**。
- **单艺人全批最多3首**。
- `scene` 不能是功能标签：`通勤` `适合放松` `睡前听` `背景音乐` `学习时` 这类会被拒，要写具体到时辰/光线/身体动作的私人时刻。
- 黑名单流派一律排除：hyperpop / EDM / dubstep / big room / hardstyle / metal / progressive house / future bass / phonk / lo-fi hip hop study beats / drone / noise / math rock炫技 / jazz fusion炫技 / trap。

## 6. 候选JSON模板（照这个字段名，一个都不能少）

```json
{
  "title": "",
  "artist": "",
  "year": "1998",
  "album": "",
  "genres": ["dream pop", "chamber pop"],
  "mood_tags": ["late night", "tender"],
  "production_tags": ["tape saturation", "felt piano"],
  "instrumentation": ["guitar", "electric piano"],
  "vocal_style": "气声女声，靠后",
  "bpm_band": "70–100",
  "has_melody": true,
  "familiarity": "likely-unheard",
  "scene": "具体到时辰/光线/身体动作的私人时刻",
  "artist_oneliner": "[哪里人/什么谱系一脉] + [一个只对他成立的具体声音标签]",
  "why": "具体声音锚点 + 带力度的动词 + 一个可触画面，≤2 句",
  "source": "如 Bandcamp Daily",
  "source_url": "https://..."
}
```

输出**一个 JSON 对象**（顶层两个键 `tracks` / `artists`，格式见 `GPT_WEEKLY.md` §二），
不要 markdown 围栏、不要弯引号、能通过严格 `json.loads`。

> 补库通道自 2026-08-03 起是「曲目 + 艺人简介一次交付」。裸数组仍可读，但
> 那种文件里的艺人必须**全部已在库**，否则会因「新艺人缺简介」整批被拒。

## 7. 交付方式

产出的 JSON 传到仓库 `candidates/`（GitHub 网页 Add file 即可），CI 自动跑合并管线
（iTunes 验真 → 去重 → schema/文案/词表校验 → 艺人简介校验 → 进池 → 重建部署），
结果推微信。定时任务无人值守，不要说「直接给我」——没有人在那头接。
也可以自己放进repo的 `candidates/` 目录，CI的 `.github/workflows/merge.yml` 会自动处理——这条链路已验证正常（你上次补的227首就是这么进来的，媒体命中率227/227）。

合并后我会把报告发你，格式是：
```
input 90 · schema_valid 90 · exact 80+accept 6 · dup 0 · version_mismatch 1
· artist_mismatch 1 · not_found 2 · blacklist 0 · added 86 → 池 1083→1169
```
被隔离的会逐条列出原因，你可以据此调整下一批。

## 8. 当前库存（决定你该补多少、补什么）

- 池 **1169首** / 合格1169 / 供给约31天（每期30首）
- 封面覆盖99.0%
- **仍然偏缺的方向**（补库时优先）：
  - 非英语世界：日语（原产city pop / 涩谷系 / 日本独立）、韩语、西语、北欧、中东、非洲
  - 器乐（目前仅约17%）
  - 明快 / 上扬 / groove（`upbeat` `hopeful` 标签的曲子偏少，整期容易一路温柔到底）
  - BPM < 70的极慢，和 > 125的快
  - 1950–1969年代（1950s目前只有2首）
