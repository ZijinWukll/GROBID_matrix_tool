# 故障排查

## 命令太多记不住

```powershell
python matrix_tool.py help
python matrix_tool.py help rebuild
python matrix_tool.py help import-labels
```

## GROBID 不可达

连接校园 VPN，确认 `project.json` 的 `grobid_url` 可达。离线时用 `add ... --from-tei`。

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
