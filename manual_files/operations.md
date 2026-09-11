# 日常操作

所有命令都在项目根目录运行。先激活本机 conda/miniconda 环境，或通过 `MATRIX_PYTHON` 指定解释器；推荐使用 `scripts/matrix.ps1` 或 `scripts/matrix.sh` 作为薄封装。

## 查看现状

```powershell
python matrix_tool.py status
```

## 新增种子论文

需要校园 VPN 连接 GROBID：

```powershell
python matrix_tool.py add data/seed_papers/新论文.pdf
```

无 VPN 时使用现成 TEI：

```powershell
python matrix_tool.py add data/seed_papers/新论文.pdf --from-tei 现成.tei.xml
```

## 修改配置后重建

```powershell
python matrix_tool.py rebuild
```

临时跳过联网翻译时加 `--no-translate`。重建结果写入 `data/exports/科研矩阵表_AgentMemory.xlsx`，人工直接打开 xlsx 审查。

## 导出和回填译文

```powershell
python matrix_tool.py export-untranslated
python matrix_tool.py import-translations data/exports/untranslated_时间戳.json
```
