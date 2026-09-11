from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import PROJECT_ROOT


BASELINE_PATH = PROJECT_ROOT / "tests" / "baselines" / "logical_rows.json"
CONFIG_PATH = PROJECT_ROOT / "data" / "config" / "project.json"
pytestmark = pytest.mark.skipif(
    not CONFIG_PATH.is_file() or not BASELINE_PATH.is_file(),
    reason="本地私有数据或回归基线未安装",
)


def _logical_snapshot(mt) -> dict:
    project = mt.load_project()
    rows = mt.sort_rows(mt.compute_rows(mt.papers_data_fresh(project), mt.load_fixes()))
    rules = mt.load_rules()
    return {
        "project": {
            "schema_version": project["schema_version"],
            "grobid_url": project["grobid_url"],
            "paper_order": project["paper_order"],
            "papers": {
                key: {
                    "header": info["header"],
                    "added": info["added"],
                }
                for key, info in project["papers"].items()
            },
            "translation": project["translation"],
            "context_window": project["context_window"],
        },
        "translations": mt.load_pool(),
        "rows": [
            {
                "id": row["id"],
                "display_title": row["display_title"],
                "year": row["year"],
                "abbrev": mt.abbrev_three_level(row["display_title"], rules)[0],
                "per_paper": row["per_paper"],
            }
            for row in rows
        ],
    }


def test_logical_rows_match_the_frozen_baseline() -> None:
    from src import matrix_tool as mt

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    assert _logical_snapshot(mt) == baseline


def test_project_config_points_only_at_existing_refactored_paths() -> None:
    from src import matrix_tool as mt

    project = mt.load_project()
    assert project["output_path"].startswith("data/exports/")
    for info in project["papers"].values():
        assert info["pdf"].startswith("data/seed_papers/")
        assert info["tei"].startswith("data/state/papers/")
        assert (mt.ROOT / info["pdf"]).is_file()
        assert (mt.ROOT / info["tei"]).is_file()
