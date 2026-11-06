# 命令参考

在项目根目录运行。`[]` 表示可选，`<>` 表示必填；占位符换成真实值，路径含空格时加双引号。

日常：PDF 放进 `data/seed_papers/` → `python matrix_tool.py build` → 打开 Excel。

## 日常流程

### build

自动提取引用、生成关系标签、自动翻译并出表。

```text
python matrix_tool.py build [--no-llm] [--no-translate] [--relabel]
    [--window N] [--window-before N] [--window-after N]
```

- --no-llm       暂时跳过分类和翻译，复用缓存及人工结果后出表
- --no-translate 仅跳过翻译
- --relabel      重算非人工标签
- --window N     前后各 N 句（0=只取引用句）
- --window-before N / --window-after N  单独设置前后句数

```powershell
python matrix_tool.py build
```

只纳入 data/seed_papers/ 中的 PDF；有效缓存复用，历史缓存保留。

### import

把外部 PDF 放入标准目录，可附带 TEI；不构建。

```text
python matrix_tool.py import <PDF或文件夹> [更多路径...]
    [--from-tei XML] [--key KEY] [--replace]
```

- --from-tei  单篇 PDF 对应的现成 TEI，供 build 离线复用
- --key       单篇带 TEI 导入时指定短名
- --replace   允许替换同名 PDF

```powershell
python matrix_tool.py import "下载目录/论文.pdf"
python matrix_tool.py import "下载目录"
python matrix_tool.py import "论文.pdf" --from-tei "论文.tei.xml"
```

已手动放好 PDF 时无需导入。--from-tei 和 --key 仅用于单篇。

### export

从最近 JSON 快照离线出表。

```text
python matrix_tool.py export [--output 文件.xlsx]
```

- --output  另存到指定位置；默认使用项目输出路径

```powershell
python matrix_tool.py export
```

不扫描 PDF、不抽取、不调用模型；新增论文或重新处理内容用 build。

### status

查看输入论文、最近构建结果和待处理数量。

```text
python matrix_tool.py status
```

```powershell
python matrix_tool.py status
```

只读，不构建。

## 维护

### cache

查看解析缓存，或预览、执行清理。

```text
python matrix_tool.py cache [list]
    或 python matrix_tool.py cache clean [--all] [--apply]
```

- clean      默认选择不再使用且 PDF 已移走的历史缓存
- --all      清理范围包含当前使用的 TEI/JSON
- --apply    执行删除；不加时仅预览

```powershell
python matrix_tool.py cache clean
```

--apply 才删除；PDF、短名、译文池和人工结果保留。

### init

可选：创建空项目或补齐缺失配置。

```text
python matrix_tool.py init [--force] [--migrate-legacy]
```

- --force    补齐缺失配置，保留已有文件
- --migrate-legacy 显式迁移早期三篇种子，需旧 TEI

```powershell
python matrix_tool.py init
```

一般无需运行；旧迁移与 --force 同用会替换登记表。

## 标签与翻译（可选，不影响自动构建）

### export-labels

可选导出标签表；默认仅待复核项，不请求模型。

```text
python matrix_tool.py export-labels [--all]
```

- --all 导出全部标签

```powershell
python matrix_tool.py export-labels
```

人工修正不是构建前提；需要时仅编辑人工标签列，再 import-labels。

### import-labels

可选回填人工标签并离线刷新表格。

```text
python matrix_tool.py import-labels <标签表.xlsx>
```

- file 标签表；留空不修改，自动清除覆盖

```powershell
python matrix_tool.py import-labels 校对.xlsx
```

人工覆盖优先，非法标签整批拒绝；不会触发额外模型处理。

### export-untranslated

可选导出残留缺译清单，供排查或人工精修。

```text
python matrix_tool.py export-untranslated
```

```powershell
python matrix_tool.py export-untranslated
```

build 默认自动补译；服务不可用时再次 build 即可，不要求手工填表。

### import-translations

可选回填人工译文并离线刷新表格。

```text
python matrix_tool.py import-translations <译文.json>
```

- file {hash:中文} 或 {英文句:中文}

```powershell
python matrix_tool.py import-translations 译文.json
```

人工译文保留优先，不会触发额外模型处理。

## 旧命令

`add` 兼容 `import`，`rebuild` 兼容 `export`；`remove` 已退役。内容更新用 `build`，范围通过 PDF 文件夹管理。
