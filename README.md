# 科研矩阵表工具

把几篇论文的引用内容整理成中文 Excel，自动生成关系标签。

## 第一次使用

在项目根目录打开终端，安装依赖：

```powershell
conda create -n matrix python=3.13
conda activate matrix
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

打开 `.env`，填好 GROBID 和模型服务的地址、密钥、模型名。校园服务通常需要校园网络或 VPN。首次运行会自动创建项目配置，不用先执行 `init`。

## 平时就做三步

1. 把要整理的 PDF 放进 `data/seed_papers/`。
2. 在项目根目录运行：

```powershell
python matrix_tool.py build
```

3. 打开 `data/exports/科研矩阵表_AgentMemory.xlsx`。

以后加论文、换论文或移走论文，都改这个文件夹，再运行同一条命令。只处理文件夹本层的 PDF；已有有效解析会复用，旧缓存不会自动删除。

## 其他时候用什么

- PDF 在下载目录：`python matrix_tool.py import "下载目录/论文.pdf"`，再 `build`。已经手动放好就不用导入。
- 只想重新生成 Excel：`python matrix_tool.py export`。直接使用上次结果，完全离线。
- 查看处理情况：`python matrix_tool.py status`。
- 查看缓存：`python matrix_tool.py cache`。
- 清理历史解析缓存：先 `python matrix_tool.py cache clean` 预览，加 `--apply` 才删除。
- 暂时跳过模型：`python matrix_tool.py build --no-llm`。
- 查完整格式：`python matrix_tool.py help` 或 `python matrix_tool.py help build`。

构建会显示五步进度：扫描 PDF → 提取引用 → 关系分类 → 中文翻译 → 写入 Excel。长任务约每 10 秒更新一次，错误立即显示。

分类、翻译会自动补试，成功结果会保存。服务故障时保留已有结果，恢复后再运行 `build`。残留的不确定项只作可选复核，不挡住出表；人工精修不是必经步骤。

不要直接修改最终 Excel。标题和简写等显示规则改完可 `export`；重新处理引用、标签和翻译用 `build`。

## 文档和开发

- [完整命令格式](manual_files/commands.md)
- [日常操作](manual_files/operations.md)
- [服务与配置](manual_files/configuration.md)
- [遇到问题](manual_files/troubleshooting.md)
- [开发与测试](manual_files/development.md)
- [项目架构](project_memory/architecture.md)

代码在 `src/`，测试在 `tests/`，数据统一在 `data/`。真实配置、论文、缓存、译文和导出物仅保存在本机，不提交 Git。旧 `add` 等同 `import`，旧 `rebuild` 等同 `export`；`remove` 已退役。
