# 本地配置目录

真实的 `project.json`、规则表和修正表只保存在本机，并已被 `.gitignore` 排除。首次使用时可复制示例文件：

```powershell
Copy-Item data/config/project.example.json data/config/project.json
Copy-Item data/config/abbrev_rules.example.json data/config/abbrev_rules.json
Copy-Item data/config/alias_mentions.example.json data/config/alias_mentions.json
Copy-Item data/config/display_title_fixes.example.json data/config/display_title_fixes.json
```

示例中的论文名、文件名和数据路径均为占位内容，不包含任何本机研究数据。

人工关系标签覆盖保存在本地 `relation_label_overrides.json`。该文件由 `import-labels` 自动写入，格式可参考 `relation_label_overrides.example.json`。
