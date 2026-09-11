# 回归基线

`logical_rows.json` 由本机私有种子论文生成，包含抽取后的标题、引用上下文和译文，因此不提交到 Git。

本地有 `data/config/project.json`、TEI 缓存和译文池后，可重新生成基线；缺少基线和私有数据时，相关回归测试会自动跳过。
