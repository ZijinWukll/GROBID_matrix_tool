# 运行日志

`matrix_tool.py` 每次运行都会向 `matrix_tool_YYYYMMDD.log` 追加 JSON Lines 记录。

日志记录命令、参数、开始与结束时间、耗时、退出状态和异常摘要，不记录论文全文、引用上下文或译文正文。运行日志由 `.gitignore` 排除；`CHANGELOG.md` 需要纳入版本管理。

运行日志仅用于排障，当前操作说明见根目录 README；不要把 log 中的历史记录当作当前命令指南。
