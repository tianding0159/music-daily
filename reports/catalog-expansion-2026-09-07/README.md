# 1000 首补库：验真后的审听队列

这批资料属于**待审听曲目**，尚未加入 `data/pool.json`。曲目数量、艺人数和校验结果以同目录 `summary.json` 为准。

每首均来自 Apple 官方 iTunes Lookup API，带艺人、真实曲名、专辑、该发行版本日期、歌曲与专辑 ID、试听和 Apple Music 链接。入口使用正式曲库已经收录的专辑，结果必须与原有曲目的艺人及专辑名一致；艺人匹配只收 `exact_match`，不收子串形式的 `acceptable_match`。整批每位艺人最多 3 首，并排除曲库和本批里的同名作品、不同 Apple ID 的重制或现场版本及重复 Apple ID。

文件说明：

- `listening-queue.json`：供审听界面读取的曲目资料；不是可自动导入的候选文件。
- `apple-source-records.json`：每首对应的 Apple 原始歌曲对象和专辑对象，可逐字段复查。
- `summary.json`：统计、检索端点、获取时间、源响应哈希及过滤原因。
- `audit.json`：从交付文件重新核对身份、去重、来源字段及审听状态的结果。
- `media-probes.json`：逐首试听链接的 HTTP 状态、音频类型及前 64 字节文件头；可获取不等于已经听审。
- `SHA256SUMS.txt`：交付文件的 SHA-256 校验清单。

运行 `python tools/build_catalog_review.py` 可恢复或重新生成同一批队列；运行 `python tools/audit_catalog_review.py --probe-media` 可重新核对全部来源及试听链接。已获取的完整响应临时保存在 `.backup/catalog-source-2026-09-07/`，中断重跑不会重复请求已完成的批次。官方元数据请求遵守 Apple 文档约每分钟 20 次的限制。

**验真范围**：这里确认的是公开曲目身份、版本标题和专辑归属。相同专辑是继续发现音乐的线索，不能证明其中每首都符合口味。Apple 的专辑发行日期也可能属于数字再发行，不应直接当成原版发行年。

**仍需完成**：逐曲核对旋律、制作偏好及黑名单、BPM、器乐和人声；查证原版发行年；填写各自独立的中文听感与场景、受控心情标签。队列保留 `pending_checks` 并故意不填这些未验证字段，也未把现有曲目的文案或声音标签复制给新曲。所有艺人已有简介，因此本批没有新简介和覆盖写入。

只有完成以上项目后，才应转成 `GPT_WEEKLY.md` 定义的 `tracks` / `artists` 候选对象，通过现有 schema、iTunes、去重、文案和简介校验入库。

官方接口规则：[iTunes Search API 文档](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/Searching.html)。
