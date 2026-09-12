# 开发与测试

## 目录职责

- `src/`：实现代码和兼容入口对应的核心程序。
- `tests/`：冒烟测试、回归测试和冻结基线。
- `scripts/`：PowerShell 与 Bash 薄封装。
- `data/`：运行数据和导出物。
- `project_memory/`、`road_map/`、`manual_files/`、`log/`：长期文档、路线、手册与运行记录。

## 安装开发依赖

```powershell
python -m pip install -r requirements-dev.txt
```

本地翻译配置放在 `.env`，不要提交。测试使用假的 OpenAI 兼容客户端验证请求参数和译文写回，不依赖学校服务器。

## 测试

```powershell
python -m pytest -q
```

回归测试读取 `tests/baselines/logical_rows.json`，不得在联网或无隔离的环境中改写正式 `data/`。临时重建测试会复制数据到 pytest 临时目录。

## 日志

每次 CLI 调用写入 `log/matrix_tool_YYYYMMDD.log`。日志使用 JSON Lines，新增字段时保持向后兼容，不输出正文数据。
