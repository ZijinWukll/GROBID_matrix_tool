# 日常操作

所有命令都在项目根目录运行。推荐先执行：

```powershell
python matrix_tool.py help
```

## 推荐：放入 PDF，一键生成

先配置 `.env` 并确认所需服务可达。把论文 PDF 放入 `data/seed_papers/`，运行：

```powershell
python matrix_tool.py build
```

首次自动创建配置，以后重复同一命令即可。只扫描文件夹本层的 PDF（扩展名不区分大小写），未变且 TEI 完整的论文复用解析缓存；旧登记没有 PDF 哈希时重新解析一次。新增论文按文件名顺序追加到已有列后面。所有论文处理后统一生成一次 `data/exports/科研矩阵表_AgentMemory.xlsx`。

使用自己的文件夹，例如项目根目录的 `input/`：

```powershell
python matrix_tool.py build --input-dir input
python matrix_tool.py build --no-translate
python matrix_tool.py build --relabel --window 3
```

自定义文件夹中的 PDF 会复制到标准目录。`--no-translate` 只跳过翻译，关系标签仍按配置执行。目录中没有 PDF、但已有登记论文时，仍从这些论文的 TEI 重建。

某篇 PDF 解析失败会显示文件名，保留成功论文，并在有已登记论文时导出可用表格，同时返回失败状态；修复后重新运行即可续跑。GROBID 不可达时不会改写现有表格；全部命中解析缓存时无需连接 GROBID。

## 单篇与离线添加

联网使用 GROBID：

```powershell
python matrix_tool.py add data/seed_papers/新论文.pdf
```

离线使用现成 TEI：

```powershell
python matrix_tool.py add data/seed_papers/新论文.pdf --from-tei 现成.tei.xml
```

## 重建表格

```powershell
python matrix_tool.py rebuild
```

只读取已登记论文的 TEI，不扫描新 PDF、不连接 GROBID。重建顺序固定为：抽取 → 关系标签 → 自动翻译 → 写 xlsx。默认复用标签和译文缓存，只处理新增或失效内容。

常用选项：

```powershell
python matrix_tool.py rebuild --no-translate
python matrix_tool.py rebuild --relabel
python matrix_tool.py rebuild --window 3
```

## 初始化与旧项目迁移

通常不必单独初始化，`build` / `add` 会自动完成。若只想创建配置、暂不处理论文：

```powershell
python matrix_tool.py init
```

该命令创建空项目，不需要旧论文、TEI 或网络，也不生成空 Excel。配置已经存在时会提示已初始化；`init --force` 仅补齐缺失配置，保留已有配置、论文、人工规则和缓存。

只有确实拥有早期 HMARS、MRAgent、PMA 三篇论文的旧 TEI 时，才使用：

```powershell
python matrix_tool.py init --migrate-legacy
```

该入口保留旧迁移、重建与对账流程。已有配置时需加 `--force`，这会替换论文登记表；先备份当前配置。规则文件、人工覆盖和已有译文池不会覆盖。

## 注销论文

```powershell
python matrix_tool.py remove KEY
```

`KEY` 可通过 `status` 查看。该命令删除对应 TEI/JSON 并重建，保留 PDF。若不想下一次 `build` 重新导入，先将该 PDF 移出扫描目录（自定义输入目录和标准目录都需要检查）。仅移动 PDF 不会注销论文。

## 复核关系标签

```powershell
python matrix_tool.py export-labels
```

打开导出的 xlsx，只编辑“人工标签”列：

- 自动标签正确：留空。
- 自动标签错误：从下拉框选择正确标签。
- 清除人工覆盖：选择“自动”。

保存后运行：

```powershell
python matrix_tool.py import-labels data/exports/relation_labels_时间戳.xlsx
```

默认只导出待复核项；需要全量标签时使用 `python matrix_tool.py export-labels --all`。

## 人工译文

```powershell
python matrix_tool.py export-untranslated
python matrix_tool.py import-translations data/exports/untranslated_时间戳.json
```

返回最终表格：

`data/exports/科研矩阵表_AgentMemory.xlsx`

不要直接编辑最终 xlsx。
