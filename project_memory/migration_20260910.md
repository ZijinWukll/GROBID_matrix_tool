# 2026-09-10 层级重构记录

## 迁移映射

| 原位置 | 新位置 |
| --- | --- |
| `matrix_tool.py`、`util_get_current_time.py` | `src/`，根目录保留 `matrix_tool.py` 兼容入口 |
| `config/` | `data/config/` |
| `state/` | `data/state/` |
| `Input/seed_papers/` | `data/seed_papers/` |
| `Output/` | `data/exports/` |
| `README_科研矩阵表工具.md` | 根目录 `README.md` + `manual_files/` |
| `PATH_backup_20260901.txt` | `project_memory/archive/` |

## 验证

- 重构前冻结 `tests/baselines/logical_rows.json`，覆盖 121 行矩阵数据、上下文、简写和译文池。
- 冒烟测试检查目录、兼容命令、临时数据重建和日志生成。
- 回归测试要求逻辑行结果与基线完全一致。
- 旧 `Output/` 中的数据和状态文件只移动、不重写。
