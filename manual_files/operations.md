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

首次自动创建配置，以后重复同一命令即可。只扫描文件夹本层的 PDF（扩展名不区分大小写），未变且 TEI 完整的论文复用解析缓存；旧登记没有 PDF 哈希时重新解析一次。同批保留已有列顺序，新论文按文件名排序追加。所有论文处理后统一生成一次 `data/exports/科研矩阵表_AgentMemory.xlsx`。

`build` 以当前输入目录同步矩阵：移走或替换 PDF 后，旧论文不再参与本轮矩阵，历史 TEI、人工标签和译文保留作缓存。放回同名、同内容 PDF 可复用缓存。清空曾使用的目录会生成不含论文的空表，新项目空目录则仅提示放入 PDF。

使用自己的文件夹，例如项目根目录的 `input/`：

```powershell
python matrix_tool.py build --input-dir input
python matrix_tool.py build --no-translate
python matrix_tool.py build --relabel --window 3
python matrix_tool.py build --no-llm
python matrix_tool.py build --keep-existing
```

自定义文件夹中的 PDF 会复制到标准目录，但本轮只纳入指定目录中的论文，不额外加入标准目录的其他归档。`--no-translate` 只跳过翻译，`--no-llm` 同时跳过模型分类和翻译、复用缓存及人工结果；新 PDF 仍需要 GROBID。`--keep-existing` 使用累加模式，保留先前已参与矩阵的其他论文。TEI 单独导入的论文也遵循此范围规则；只想保持当前矩阵范围时用 `rebuild`。

某篇 PDF 解析失败会显示文件名，保留成功论文并导出本轮可用表格，同时返回失败状态；默认同步模式不会拿失败的新版本对应的旧 TEI 冒充本轮结果。全部 PDF 都失败时保留上一张表与原范围。修复后重新运行即可续跑。GROBID 不可达时不会改写现有表格；全部命中解析缓存时无需连接 GROBID。

模型阶段显示批次/句数进度。请求异常后不逐条重试，继续用待复核标签与英文生成表格；分类服务失败时也跳过同一服务的本轮翻译。分类每批保存结果，翻译每 10 句及结束/中断时保存。无效回复连续出现两批/两句时停止本轮对应阶段，避免耗尽整轮等待时间。网络失败的兜底标签后续会自动重试，不永久当作成功分类。

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

只读取当前参与矩阵的论文 TEI，不扫描新 PDF、不改变矩阵范围、不连接 GROBID。重建顺序固定为：抽取 → 关系标签 → 自动翻译 → 写 xlsx。默认复用标签和译文缓存，只处理新增或失效内容。

常用选项：

```powershell
python matrix_tool.py rebuild --no-translate
python matrix_tool.py rebuild --relabel
python matrix_tool.py rebuild --window 3
python matrix_tool.py rebuild --no-llm
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

一般换论文只需移动 PDF 后运行 `build`，无需操作缓存。要彻底注销某篇登记及其 TEI/JSON 时使用 `remove`，`KEY` 可通过 `status` 查看。该命令保留 PDF；若不想下一次 `build` 重新导入，先将 PDF 移出扫描目录。译文池与人工覆盖不会删除。

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
