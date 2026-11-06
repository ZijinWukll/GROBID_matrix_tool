# 开发与测试

## 目录职责

- `src/`：实现代码和核心逻辑。
- `tests/`：帮助、冒烟、回归、翻译和关系标签测试。
- `scripts/`：PowerShell / Bash 命令封装。
- `data/`：本地配置、状态和导出物。
- `project_memory/`：架构与关键决策。
- `manual_files/`：面向用户和维护者的专题文档。

## 环境与测试

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

测试不得依赖真实私有数据或联网调用模型。缺少本地基线时，相关回归测试会自动跳过。

## 新增命令或帮助

修改 `src/matrix_tool.py` 时同步维护：

- `COMMANDS_HELP`：单命令说明、参数和示例。
- `COMMAND_GROUPS`：`help` 首页的命令分组。
- `HELP_QUICKSTART`：快速开始命令序列。
- `tests/test_help.py`：帮助输出回归测试。

## 关系标签开发约定

- 关系方向固定为：列论文 → 行论文。
- 单单元格只显示一个主标签。
- 冲突优先级：`Q&A > C&A > B&E > S&S > M/I`。
- 低于 `0.60` 或 evidence 为空时进入待复核。
- 默认 `export-labels` 只导出待复核项。

自动检查是模型辅助的有限补救，不是独立评测；分歧继续保留不确定状态。正常构建不要求用户逐条审核。新命令职责以 `project_memory/design_20261106.md` 为准：build 自动构建、import 仅导入、export 仅快照离线导出、cache 显式清理。

## 隐私与提交

`data/config` 真实配置、`data/state`、种子 PDF、导出物、`.env`、日志和回归基线均不提交。提交前检查 `git status --short`，不要使用 `git add -f` 添加被忽略文件。
