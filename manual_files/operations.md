# 日常操作

命令都在项目根目录运行。路径有空格时加双引号。完整格式见 [命令参考](commands.md)。

## 生成或更新表格

把 PDF 放进 `data/seed_papers/`，运行：

```powershell
python matrix_tool.py build
```

新增论文就放入 PDF；移出矩阵就移走 PDF；替换论文就替换 PDF。每次改完都运行 build。只扫描本层文件，旧缓存保留，PDF 内容已变化时重新解析。

终端显示五步：扫描、引用、分类、翻译、Excel。长任务约每 10 秒刷新，不逐句刷屏。构建完成后看最后的文件路径。

## 从下载目录导入

```powershell
python matrix_tool.py import "下载目录/论文.pdf"
python matrix_tool.py import "下载目录/论文文件夹"
python matrix_tool.py import "论文.pdf" --from-tei "论文.tei.xml"
python matrix_tool.py build
```

import 只导入，不构建。同名不同内容需加 --replace；自定义短名 --key 只用于单篇带 TEI 导入。

## 只重新导出 Excel

```powershell
python matrix_tool.py export
python matrix_tool.py export --output "data/exports/矩阵副本.xlsx"
```

使用最近的 JSON 结果，不扫描 PDF、不抽取、不请求模型。适合文件丢失、另存、改标题或简写显示。更新引用或模型结果仍用 build。

## 查看和清理

```powershell
python matrix_tool.py status
python matrix_tool.py cache
python matrix_tool.py cache clean
python matrix_tool.py cache clean --apply
```

clean 默认仅预览不再使用的历史解析文件。--apply 才删，--all 包含当前解析文件。PDF、短名、译文池和人工覆盖保留；清理当前解析文件后先 build 才能 export。

## 暂时跳过模型

用 build --no-llm 跳过分类和翻译，或 build --no-translate 只跳过翻译。已有结果照常复用。缺译暂留英文，恢复服务后再次 build。

人工标签和译文导出、回填仅用于主动精修，详见命令参考，不是日常必经步骤。旧 add/rebuild 分别兼容 import/export；旧 remove、--input-dir、--keep-existing 不再使用。
