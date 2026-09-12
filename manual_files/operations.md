# 日常操作

所有命令都在项目根目录运行。推荐先执行：

```powershell
python matrix_tool.py help
```

## 添加论文

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

重建顺序固定为：抽取 → 关系标签 → 自动翻译 → 写 xlsx。默认复用缓存，只处理新增或失效内容。

常用选项：

```powershell
python matrix_tool.py rebuild --no-translate
python matrix_tool.py rebuild --relabel
python matrix_tool.py rebuild --window 3
```

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
