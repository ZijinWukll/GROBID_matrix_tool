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

查看 `[失败] 文件名: 原因` 提示。成功论文已保存并导出可用结果，命令返回失败状态；默认同步模式下失败的新版本不会使用旧缓存冒充本轮结果。全部 PDF 都失败时保留上一张表与原范围。修复 PDF 或服务问题后重跑相同 `build`，不会重复解析已成功且未变的论文。

## 换了 PDF，旧论文还在表格里

更新后 `build` 以当前扫描文件夹为准：不在文件夹中的论文会退出当前矩阵，缓存留存不会自动把论文重新加入。无需删除 `data/state/papers/`。`status` 会区分当前论文和历史缓存。

`build --keep-existing` 是累加模式；`rebuild` 保持当前矩阵范围，只更新处理结果。确认没有把这两种方式误当成目录同步。

## 抽取完成后一直等待，没有 Excel

后续是模型关系分类和逐句翻译，GROBID 能解析 PDF 不代表模型服务可用。新版本显示分类批次、翻译句数、单次读取超时与写入阶段；连接超时为 5 秒，不做 SDK 隐式重试。关系分类的 `timeout` 默认 30 秒，翻译默认 60 秒，可在 `project.json` 中分别设置。

请求失败后停止本轮连续模型调用，保留结果并继续出表。HTTP 502 可能来自代理或服务端网关，需结合实际网络检查定位；不要把它当作模型返回空标签。

暂时跳过模型，先拿到表格：

```powershell
python matrix_tool.py build --no-llm
```

已有 TEI、并且希望保持当前论文范围时，用 `python matrix_tool.py rebuild --no-llm` 可离线重建。仅 `--no-translate` 仍会执行关系分类。

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
