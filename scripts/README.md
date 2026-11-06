# 辅助脚本

- matrix.ps1 / matrix.sh：把参数传给根目录 matrix_tool.py。
- test.ps1 / test.sh：运行 pytest。

默认使用当前环境里的 python；设置 MATRIX_PYTHON 可指定其他解释器。一般直接按根目录 README 中的命令运行即可。

测试生成的 __pycache__、.pytest_cache 和临时测试目录可删除；tests 下的 .py 测试与本机私有基线应保留。
