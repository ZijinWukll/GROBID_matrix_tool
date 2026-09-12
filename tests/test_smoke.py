from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import PROJECT_ROOT


HAS_PRIVATE_DATA = (PROJECT_ROOT / "data" / "config" / "project.json").is_file()
requires_private_data = pytest.mark.skipif(
    not HAS_PRIVATE_DATA,
    reason="本地私有数据和配置未安装",
)


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "matrix_tool.py"), *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_source_tree_uses_the_refactored_layout() -> None:
    assert (PROJECT_ROOT / "src" / "matrix_tool.py").is_file()
    assert (PROJECT_ROOT / "src" / "util_get_current_time.py").is_file()
    assert not (PROJECT_ROOT / "render_qa.py").exists()
    assert (PROJECT_ROOT / "data" / "config" / "project.example.json").is_file()
    assert (PROJECT_ROOT / "data" / "config" / "README.md").is_file()
    assert (PROJECT_ROOT / "data" / "state" / "papers").is_dir()
    assert (PROJECT_ROOT / "data" / "seed_papers").is_dir()
    assert (PROJECT_ROOT / "data" / "exports" / ".gitkeep").is_file()
    assert (PROJECT_ROOT / "log").is_dir()


def test_help_uses_the_new_data_paths() -> None:
    result = _run_cli("help", "add")

    assert result.returncode == 0, result.stderr
    assert "data/seed_papers" in result.stdout


@requires_private_data
def test_status_reports_the_new_export_path() -> None:
    result = _run_cli("status")

    assert result.returncode == 0, result.stderr
    assert "data/exports/科研矩阵表_AgentMemory.xlsx" in result.stdout


@requires_private_data
def test_rebuild_on_a_temporary_copy_creates_xlsx_and_daily_log(
    monkeypatch, tmp_path: Path
) -> None:
    from src import matrix_tool as mt

    shutil.copytree(PROJECT_ROOT / "data", tmp_path / "data")
    (tmp_path / "log").mkdir()

    patched = {
        "PROJECT_ROOT": tmp_path,
        "ROOT": tmp_path,
        "DATA_DIR": tmp_path / "data",
        "CONFIG_DIR": tmp_path / "data" / "config",
        "STATE_DIR": tmp_path / "data" / "state",
        "PAPERS_STATE_DIR": tmp_path / "data" / "state" / "papers",
        "INPUT_SEED_DIR": tmp_path / "data" / "seed_papers",
        "OUTPUT_DIR": tmp_path / "data" / "exports",
        "TRANS_POOL": tmp_path / "data" / "state" / "translations_by_hash.json",
        "LOG_DIR": tmp_path / "log",
    }
    for name, value in patched.items():
        monkeypatch.setattr(mt, name, value)
    monkeypatch.setattr(
        mt,
        "auto_label_missing",
        lambda rows, project, quiet=False, client=None, relabel=False: {"labels": {}},
    )

    mt.main(["rebuild", "--no-translate"])

    output = tmp_path / "data" / "exports" / "科研矩阵表_AgentMemory.xlsx"
    assert output.is_file()
    assert list((tmp_path / "log").glob("matrix_tool_*.log"))


def test_log_file_is_structured_json_lines() -> None:
    result = _run_cli("help")
    assert result.returncode == 0, result.stderr

    log_files = sorted((PROJECT_ROOT / "log").glob("matrix_tool_*.log"))
    assert log_files, "运行 CLI 后应生成按日日志"

    records = [
        json.loads(line)
        for line in log_files[-1].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(record.get("event") == "command_finished" for record in records)
