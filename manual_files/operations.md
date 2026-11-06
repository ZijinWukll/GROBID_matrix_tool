# 日常操作

所有命令在项目根目录运行。查看帮助：`python matrix_tool.py help`。

## 构建

将 PDF 放入 `data/seed_papers/`，运行 `python matrix_tool.py build`。它始终只纳入本层 PDF；有效 TEI 复用，没有缓存或已知 PDF 变化时重新解析。没有哈希的旧缓存先复用并记录哈希，不自动删除任何缓存。

新增、替换、移走论文后重复同一命令即可。清空已使用的输入目录会导出空矩阵；新项目空目录只提示放入 PDF。部分解析失败时输出可用论文并返回失败状态，不用旧版本冒充新版本；全部 PDF 失败时保留上一张表并明确失败。

完整流程自动处理所有缺译，自动补试无效输出，并对不确定标签进行一次检查。保留的分歧只标记为可选复核，不要求用户操作才能完成。网络故障不会无限重试，服务恢复后再次 build 继续。

```powershell
python matrix_tool.py build
python matrix_tool.py build --no-llm
python matrix_tool.py build --no-translate
python matrix_tool.py build --relabel
python matrix_tool.py build --window 3
```

## 从外部导入

```powershell
python matrix_tool.py import "下载目录/论文.pdf"
python matrix_tool.py import "下载目录/多篇论文文件夹"
python matrix_tool.py import "论文.pdf" --from-tei "已有.tei.xml"
python matrix_tool.py import "论文.pdf" --from-tei "已有.tei.xml" --key PAPER
python matrix_tool.py import "新版论文.pdf" --replace
```

只复制 PDF 到标准目录、保存可选 TEI，不联网、不构建、不改变最近矩阵范围。普通同名不同内容 PDF 会被拒绝，明确 `--replace` 才更新。已有 PDF 放在标准目录时无需使用 import。导入后运行 build。

## 离线导出

```powershell
python matrix_tool.py export
python matrix_tool.py export --output "data/exports/矩阵副本.xlsx"
```

从最近一次构建的 `data/state/papers/<KEY>.json` 导出，不扫描 PDF、不读 TEI、不调用模型。适合恢复 Excel、另存、修改标题或简写显示后的重新导出。没有 JSON 快照时先 build。上下文、分类、译文需要重新处理时仍用 build。

## 缓存管理

```powershell
python matrix_tool.py cache
python matrix_tool.py cache clean
python matrix_tool.py cache clean --apply
python matrix_tool.py cache clean --all --apply
```

默认 clean 只选择不参与最近矩阵、且原 PDF 已移走的历史解析文件。默认只预览，--apply 才删除。--all 包含当前解析文件，可能令 export 暂时不可用，build 会自动补建。PDF、短名登记、译文和人工覆盖保留；清理当前缓存不会丢失自定义短名。

## 可选人工精修

```powershell
python matrix_tool.py export-labels
python matrix_tool.py export-labels --all
python matrix_tool.py import-labels "标签复核表.xlsx"
python matrix_tool.py export-untranslated
python matrix_tool.py import-translations "译文.json"
```

这些工具只服务于需要主动精修的场景，不属于自动构建的前置条件。导出不请求服务；导入后离线刷新表格。标签表留空不修改，选择“自动”清除覆盖，其他有效值为人工优先标签。

## 旧命令

add 兼容为 import，只导入；rebuild 兼容为 export，仅离线导出。旧 --relabel、--window 请交给 build。remove 退役，移走 PDF 后 build 即退出矩阵；缓存用 cache clean 显式清理。

build 不再接受 --input-dir 或 --keep-existing。从其他目录导入请先 import；需要同时纳入的 PDF 应全部放在 seed_papers。

init 仅作为可选维护创建空项目，init --force 补齐缺失配置；旧三篇种子迁移仍可显式使用 init --migrate-legacy，带 --force 会替换登记表。
