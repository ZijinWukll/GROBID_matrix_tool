# 故障排查

## 命令太多记不住

```powershell
python matrix_tool.py help
python matrix_tool.py help rebuild
python matrix_tool.py help import-labels
```

## GROBID 不可达

连接校园 VPN，确认 `.env` 中的 `MATRIX_GROBID_URL` 可达。离线时用 `add ... --from-tei`。

`build` 只有新增 PDF、PDF 内容变化、TEI 丢失或旧记录没有 PDF 哈希时才需要重新解析。全部命中缓存时可直接重建；关系标签和翻译仍可能需要模型服务。

## 未找到 project.json / init 提示缺少旧 TEI

新版本 `build` 和 `add` 会自动创建空项目配置。把 PDF 放入 `data/seed_papers/`，运行 `python matrix_tool.py build` 即可；也可以先用 `init` 创建空项目。

旧版本的 `init` 固定迁移三篇历史论文，缺少私有 TEI 时会失败。更新代码后运行普通 `init` 或 `build` 即可，不必寻找截图中的旧缓存，也不要用 `--migrate-legacy` 初始化普通新项目。

## 放了 PDF，rebuild 却没有加入

`rebuild` 只处理已登记论文，不扫描文件夹。使用 `python matrix_tool.py build`；PDF 放在其他文件夹时用 `build --input-dir 文件夹`。扫描范围为指定目录本层，不包含子文件夹。

## 批量构建有论文失败

查看 `[失败] 文件名: 原因` 提示。成功论文已保存，有已登记论文时会导出可用结果，命令返回失败状态。修复 PDF 或服务问题后重跑相同 `build`，不会重复解析已成功且未变的论文。

## 注销论文后 build 又重新加入

`remove` 保留原 PDF。将该 PDF 从扫描目录移出后再注销；使用自定义输入目录时，也检查 `data/seed_papers/` 中的归档副本。

## 本地模型或翻译失败

检查 `.env` 中的 `MATRIX_LLM_BASE_URL`、`MATRIX_LLM_API_KEY`、`MATRIX_LLM_MODEL`。缺译句会回退英文，不影响出表；服务恢复后重新 `rebuild`。

## 关系标签大量待复核

运行 `python matrix_tool.py export-labels`，只处理导出的待复核项。也可以运行 `rebuild --relabel` 重试自动分类。

## xlsx 写入失败

关闭 Excel 中打开的 `data/exports/科研矩阵表_AgentMemory.xlsx` 后重试。最终 xlsx 是导出物，不需要手工编辑。

## 找不到 PDF 或 TEI

配置中的路径必须是项目根相对路径，并以 `data/` 开头。检查 `project.json` 中的 `pdf` 和 `tei` 字段。

## 编辑器包导出告警

`NavigableString is not exported from bs4` 等提示不等于运行错误；以终端命令和 pytest 结果为准。
