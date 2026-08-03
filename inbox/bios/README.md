# inbox/bios/ — 艺人简介投递口

把 GPT 写好的 bio JSON 放这里（GitHub 网页 **Add file → Upload files** 即可），
push 到 main 后 `.github/workflows/import-bios.yml` 自动处理。

## 放什么

两个文件一起传：

- `<批次名>.json` —— bio 数组，**必须 `ensure_ascii=True`**（中文写成 `\uXXXX`）
- `<批次名>_manifest.json` —— 含 `sha256`，workflow 自动核对

**manifest 的名字 = 主文件名去掉 `.json` + `_manifest.json`，一个字都不能差。**
导入器靠这条规则自动配对；配不上就等于没有 manifest、SHA 校验被跳过。
现在配不上会**硬失败并告诉你它在找哪个文件名**，不会静默放行。

```
✅ artist_bios_batch06_ascii.json
   artist_bios_batch06_ascii_manifest.json

❌ artist_bios_batch06_ascii.json
   artist_bios_batch06_manifest.json      ← 少了 _ascii，配不上
```

manifest 内容：
```json
{"file": "artist_bios_batch06_ascii.json", "count": 50, "sha256": "6e4c86..."}
```

## 会发生什么

1. SHA-256 核对（有 manifest 时）
2. 编码损坏检测
3. 合同校验：恰好 `artist`/`bio`/`confidence` 三键、confidence ∈ {high, low}
4. 内容校验：artist 必须在池里、黑名单词、「让人/令人」、批内重复、长度、模板集中度
5. 写入 `data/artists.json` → 重建页面 → 跑测试与 healthcheck
6. **任一环节失败 → 全批拒绝、回滚、文件留在这里等修正**，`data/artists.json` 一个字都不会变
7. 成功则提交，输入文件移到 `done/` 归档

## 本地也能跑

```bash
python3 tools/import_bios.py inbox/bios/batch02.json --sha <hash>   # 体检
python3 tools/import_bios.py                                        # 处理整个目录
python3 tools/import_bios.py --apply                                # 写盘
```
