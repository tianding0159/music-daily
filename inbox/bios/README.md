# inbox/bios/ — 艺人简介投递口

把 GPT 写好的 bio JSON 放这里（GitHub 网页 **Add file → Upload files** 即可），
push 到 main 后 `.github/workflows/import-bios.yml` 自动处理。

## 放什么

- `<批次名>.json` —— bio 数组，**必须 `ensure_ascii=True`**（中文写成 `\uXXXX`）
- `<批次名>_manifest.json` —— 可选但强烈建议，含 `sha256` 字段，workflow 会自动核对

manifest 示例：
```json
{"file": "batch02.json", "count": 30, "sha256": "6e4c86..."}
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
