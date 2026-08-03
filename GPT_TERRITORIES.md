# 补库搜索规则 · 20 个领地

> 这是 2026-07 那轮「补 800 首」用的领地划分与检索策略，**按缺口设计的**，不是随便分类。
> 配合 [`GPT_CATCHUP.md`](GPT_CATCHUP.md)（导入硬规则）与 [`GPT_VOICE.md`](GPT_VOICE.md)（文案口径）一起用。

## 怎么用

**一次做一个领地、一批 30–50 首。** 别横跨多个领地混着找——领地的意义就是让你在一个明确的
音乐地图区域里深挖，混着找会退化成「随便想几个好听的」，命中率和多样性都会掉。

每个领地给了三样东西：
- **brief** —— 挖哪一脉、锚点艺人是谁、要避开什么
- **mood_hint** —— 该领地典型的 mood_tags（仍须从 32 个受控词里选，见 CATCHUP）
- 锚点艺人**只用来校准方向，不是让你收它们**。以它们为圆心找**相邻的、更深的、大概率没被收过的**。

## 检索的四个层次（按这个顺序展开）

1. **锚点的相邻艺人** —— 同厂牌同期艺人、合作者、被同一批乐评人一起提的名字
2. **锚点的深处** —— 那位艺人不那么有名的专辑、B 面、早期自主发行
3. **场景的其他人** —— 同一个城市/年代/圈子里被锚点带出来的名字
4. **被同一份榜单收录的** —— Bandcamp Daily / Pitchfork Best New / RA 的专题里与锚点并列的

## 命中率经验（实测数据，2026-07 那轮）

- 挑**规范专辑曲**（正式录音室专辑里的曲目）命中率 **89–95%**
- 只有 remaster / instrumental / live / remix 版的曲子会被隔离 —— Hosono、Jon Hopkins、
  Yusef Lateef、Big Thief、Bon Iver 都栽过这个
- **仅在中国区上架的曲子**在 US/JP 商店查不到（Deca Joins「浪流連」就是）
- iTunes 匹配**只比艺人 + 曲名**，album 和 year 不参与匹配 —— 所以只需保证
  「艺人名真实 + 干净的录音室曲名」，标题里别带版本词

## 仍然偏缺的方向（当前 1169 首的口径）

非英语世界（日语 / 韩语 / 西语 / 北欧 / 中东 / 非洲）· 器乐（约 17%）·
明快上扬（`upbeat` `hopeful` 标签偏少，整期容易一路温柔到底）·
BPM < 70 与 > 125 · 1950–1969 年代

---

## 20 个领地

### 1. 日系独立·Shibuya-kei 深挖

日本独立/涩谷系/日系 city pop 真品/日系 jazz pop。锚点是 Lamp、cero、Cornelius、Cymbals、Fishmans、大貫妙子、Sunny Day Service、ミツメ、never young beach、青葉市子、Ichiko Aoba、Haruomi Hosono、Taeko Onuki——但这些锚点本身少收，去找它们相邻的、更深的日本艺人。池里日语声乐只有 3 首标注，这块几乎空白，是最大缺口。

**典型 mood**：`nostalgic / airy / tender / summer dusk / restrained`

### 2. 日系 70-80s 原产 city pop 与 AOR

1975-1988 日本原产 city pop / AOR / 和制 boogie / light mellow。真品，不是后来的廉价复刻。山下達郎、吉田美奈子、大橋純子、松原みき、角松敏生、EPO、間宮貴子那一脉的相邻艺人与不那么有名的专辑曲。year 必须与 album 正式发行年一致。

**典型 mood**：`nostalgic / late night / sensual / upbeat / elegant`

### 3. 韩国·台湾·香港·中国大陆独立

东亚非日本的独立音乐：韩国 indie（Jang Kiha、Silica Gel、Se So Neon、Parannoul 的柔面、Kim Oki）、台湾（雷光夏、盧廣仲的静面、老王樂隊、傷心欲絕、Sunset Rollercoaster、落日飛車、9m88）、香港、大陆（deca joins、Faye 詹雨安、马赛克、柏林护士、房东的猫的好作品、小河、五条人）。池里这块基本空白。

**典型 mood**：`late night / melancholy / woody / hopeful / hazy`

### 4. 器乐·post-classical 与现代室内乐

纯器乐但旋律明确：post-classical、neo-classical、室内乐、felt piano、弦乐四重奏改编、极简钢琴。Ólafur Arnalds、Nils Frahm、Hania Rani、Joep Beving、Dustin O'Halloran、Peter Broderick、Goldmund、Lubomyr Melnyk 那一脉的相邻人。池里器乐只占 17%，偏低。旋律必须存在，禁纯氛围 drone。

**典型 mood**：`introspective / fragile / wide open / wintry / restrained`

### 5. 器乐·爵士与 spiritual jazz

器乐爵士：spiritual jazz、modal jazz、cool jazz、非炫技的 contemporary jazz。Alice Coltrane 的柔面、Pharoah Sanders 的旋律面、Yusef Lateef、Bill Evans、Ahmad Jamal、Matthew Halsall、Nubya Garcia、Sons of Kemet 的柔面、Alfa Mist、Kamaal Williams。禁 jazz fusion 炫技。

**典型 mood**：`late night / introspective / wide open / lush / restrained`

### 6. 巴西·葡语世界深挖

Bossa nova / MPB / Tropicália / 巴西 samba-jazz / 葡萄牙 fado 的柔面 / 佛得角 morna。Milton Nascimento、Marcos Valle、Joyce、Arthur Verocai、Azymuth、Tim Maia、Gal Costa、Elis Regina、Cesária Évora、Sessa、Tim Bernardes、Bala Desejo。池里葡语 32 首是非英语最多的，但仍可深挖冷门专辑曲。

**典型 mood**：`summer dusk / warm / sensual / unhurried / nostalgic`

### 7. 法语·意大利语·西语世界

法语 chanson 新旧（Françoise Hardy、Serge Gainsbourg 的柔面、Air、Sébastien Tellier、Melody's Echo Chamber、La Femme、L'Impératrice）、意大利 library music 与 Lucio Battisti 一脉、西语（Natalia Lafourcade、Silvana Estrada、Juana Molina、Ay Wing、Hermanos Gutiérrez 器乐）。池里法语 12、西语 3，严重不足。

**典型 mood**：`elegant / sensual / nostalgic / summer dusk / hazy`

### 8. 北欧·冰岛·波罗的海

斯堪的纳维亚与冰岛：瑞典（Sarah Klang、Jose Gonzalez、Little Dragon、Tarwater 相邻）、挪威（Jaga Jazzist 相邻、Susanne Sundfør、Bendik Giske 的旋律面）、丹麦、芬兰、冰岛（Sigur Rós 的柔面、múm、Ólöf Arnalds、JFDR、Sin Fang）、爱沙尼亚/拉脱维亚。清冷质感是池里最缺的一档。

**典型 mood**：`wintry / airy / fragile / wide open / floating`

### 9. 中东·北非·土耳其·波斯

土耳其 Anadolu rock/psych（Selda Bağcan、Erkin Koray、Altın Gün、Gaye Su Akyol 相邻）、埃及/黎巴嫩（Fairuz 的柔面、Mohammed Abdel Wahab、Tamino）、波斯（Googoosh 一脉）、马格里布 Gnawa 与 raï 的旋律面、以色列（Yemen Blues）。池里土耳其只有 4 首。旋律优先，禁纯打击乐。

**典型 mood**：`grainy / sensual / nostalgic / restless / wide open`

### 10. 西非·南非·埃塞俄比亚

Ethio-jazz（Mulatu Astatke 相邻、Hailu Mergia、Girma Bèyèné）、马里（Ali Farka Touré、Tinariwen 的柔面、Rokia Traoré、Fatoumata Diawara）、尼日利亚 highlife 与 afrobeat 的旋律面、南非（Abdullah Ibrahim、Letta Mbulu、Bokani Dyer）、贝宁/加纳。池里完全空白。禁纯 percussion 无旋律。

**典型 mood**：`warm / wide open / upbeat / grainy / hopeful`

### 11. 明快·上扬·groove（对比色专项）

专门补池里最缺的那一档：明快、白天、身体想动。Nu-disco 的柔面、boogie、jazz-funk 非炫技、sophisti-pop 上扬面、city pop groove、soul 快歌、Khruangbin 相邻的 funk、Hiatus Kaiyote 的明快面、Jungle、Parcels、Franc Moody、Tom Misch。mood 至少含 upbeat 或 hopeful。BPM 多数 ≥110。禁 festival EDM。

**典型 mood**：`upbeat / hopeful / warm / sweet / shimmering`

### 12. 极慢·极简·长呼吸（BPM<70）

专补 BPM 低于 70 的一档，池里几乎没有。Slowcore（Duster、Codeine、Red House Painters、Grouper 的旋律面）、drone-folk 有旋律者、ambient pop 极慢面、Talk Talk 后期一脉、Bark Psychosis、Dirty Three。bpm_band 多数应落在 50–70。旋律必须能哼，禁无旋律 drone。

**典型 mood**：`introspective / fragile / wide open / melancholy / floating`

### 13. 1950-1969 原产（老年代专项）

专补 1950-1969，池里 1950s 只有 2 首、1960s 只有 31 首。早期 bossa、cool jazz、法国 yé-yé、意大利 canzone、早期 soul 与 doo-wop 的柔面、Brill Building pop、早期 Brazilian、Vashti Bunyan 一脉的英式 folk、exotica 有旋律者。year 与 album 必须对得上。

**典型 mood**：`nostalgic / elegant / warm / sweet / grainy`

### 14. 1970s 非英美

专补 1970s 非英美：德国 krautrock 的旋律面（Harmonia、Cluster、Popol Vuh、Can 的柔面）、法国 library、意大利 prog 的旋律面与 Piero Umiliani、日本 new music 早期、苏联/东欧 estrada、南斯拉夫、土耳其 psych、韩国 folk-rock 1970s。禁炫技 prog。

**典型 mood**：`nostalgic / organic / hazy / woody / wide open`

### 15. Dream pop / shoegaze 的柔面深挖

Dream pop 与 shoegaze 里旋律清晰、不靠噪音堆的那一支。Cocteau Twins 相邻、Slowdive 的柔面、Mazzy Star 一脉、Beach House 相邻的小厂牌新人、Hatchie、Cindy Lee 的旋律面、Nothing But Thieves 除外。池里 dream pop 已有 117 首，所以务必找没收过的艺人（见已有艺人清单），别重复。

**典型 mood**：`hazy / floating / dreamlike / fragile / tender`

### 16. Folktronica / 有机电子深挖

Folktronica、organic electronic、indietronica、旋律型 IDM。Bibio 相邻、Four Tet 的旋律面、Boards of Canada 一脉、Mount Kimbie 的柔面、Loscil 有旋律者、Christian Löffler、Rival Consoles 的旋律面、Nathan Fake 的柔面、Jon Hopkins 的静面。池里 organic electronic 88 首，务必换新艺人。

**典型 mood**：`organic / floating / shimmering / hazy / introspective`

### 17. Quiet alt-R&B / neo soul 深挖

安静的 alt-R&B 与 neo soul。Sampha 相邻、Blood Orange 一脉、Yaya Bey、Cleo Sol、Little Simz 的柔面、Nick Hakim、Serpentwithfeet 的旋律面、Moses Sumney 的柔面、Liv.e、Pink Siifu 的柔面。池里 neo soul 已 100 首，必须全是新艺人。

**典型 mood**：`intimate / sensual / late night / tender / restrained`

### 18. Midwest emo clean / soft post-rock / 木吉他

Midwest emo 的清音 jangle 面（American Football 相邻、Mineral、The Promise Ring 的柔面、Hotel Lights）、soft post-rock（toe 的柔面、Mono 的旋律面、Explosions in the Sky 相邻、Hammock）、指弹与 American Primitive（John Fahey 一脉、William Tyler、Daniel Bachman、Sarah Louise）。禁 math rock 炫技。

**典型 mood**：`woody / hopeful / wide open / organic / longing`

### 19. Chamber pop / art pop / sophisti-pop 深挖

编曲精致的 chamber pop / art pop / sophisti-pop。Van Dyke Parks 一脉、Scott Walker 的旋律面、Prefab Sprout 相邻、Blue Nile、Talk Talk、Aztec Camera、Destroyer 的柔面、Weyes Blood 相邻、Aldous Harding、Julia Holter 的旋律面、Cate Le Bon。池里 chamber pop 57 + art pop 60，务必换新艺人。

**典型 mood**：`elegant / restrained / nostalgic / cinematic / lush`

### 20. 2020s 新锐（近三年）

专补 2022-2026 的新作，池里 2020s 只有 86 首。小厂牌新人为主：Bandcamp Daily / Pitchfork Best New / RA 近年推荐里符合口味的。跨流派都可以，但必须旋律清晰、制作有温度。familiarity 全部 likely-unheard。year 用正式发行年。

**典型 mood**：`任意，但整片至少 8 首带 upbeat 或 hopeful（补对比色）`

---

## 交付

产出一个 JSON 数组，字段见 [`GPT_CATCHUP.md`](GPT_CATCHUP.md) 第 6 节。
**中文务必 `ensure_ascii=True`**（写成 `\uXXXX`），并随附 SHA-256 —— 上一批 bio 就是因为
没这么做，传输中被吞掉 `0x80–0x9F` 字节，90% 汉字不可复原、整批作废。

放进仓库 `candidates/` 目录即可，CI 会自动验真去重入库；或直接发给 Claude 手动跑。
