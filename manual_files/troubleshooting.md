# 故障排查

## GROBID 不可达

先连接校园 VPN，再确认 `data/config/project.json` 中的 `grobid_url` 可访问。完全离线时改用 `add ... --from-tei`。

## 自动翻译失败

先检查 `.env` 是否包含 `MATRIX_LLM_BASE_URL`、`MATRIX_LLM_API_KEY` 和 `MATRIX_LLM_MODEL`，再确认学校服务器可达。缺译句会保留英文原文，不影响重建和出表；服务恢复后再次运行 `rebuild`。

## 找不到 PDF 或 TEI

检查 `data/config/project.json` 中的路径必须以 `data/` 开头，并确认对应文件存在。路径按项目根目录解析，不以当前终端目录为准。

## 导出 xlsx 失败

如果提示无法写入，先关闭 Excel 中打开的 `data/exports/科研矩阵表_AgentMemory.xlsx`，再运行 `rebuild`。

## 编辑器包导出告警

`NavigableString is not exported from bs4` 之类提示不等于运行错误；以测试和终端命令结果为准。
