# 本地配置目录

真实的 `project.json`、规则表和修正表只保存在本机，并已被 `.gitignore` 排除。推荐把 PDF 放入 `data/seed_papers/` 后直接运行：

```powershell
python matrix_tool.py build
```

`build` / `add` 会自动创建缺失配置，保留已有文件；如暂不处理论文，可用 `init` 创建空项目，或用 `init --force` 补齐缺失配置。示例文件仅用于了解格式，其中论文名、文件名和数据路径均为占位内容，不能直接作为真实登记使用。

人工关系标签覆盖保存在本地 `relation_label_overrides.json`。该文件由 `import-labels` 自动写入，格式可参考 `relation_label_overrides.example.json`。
