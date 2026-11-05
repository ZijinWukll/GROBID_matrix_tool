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


def _logical_snapshot(mt, project=None) -> dict:
    project = project if project is not None else mt.load_project()
    rows = mt.sort_rows(mt.compute_rows(mt.papers_data_fresh(project), mt.load_fixes()))
    rules = mt.load_rules()
    return {
        "project": {
            "schema_version": project["schema_version"],
            "paper_order": project["paper_order"],
            "papers": {
                key: {
                    "header": info["header"],
                    "added": info["added"],
                }
                for key in project["paper_order"]
                for info in [project["papers"][key]]
            },
            "translation": project["translation"],
            "relationship_labeling": project.get("relationship_labeling", {}),
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
    # 回归比较冻结的种子集合，而不是用户当前选择的 PDF 集合。
    # build 切换范围后仍保留历史 TEI，可继续检验旧语料的抽取与排序。
    project = mt.load_project()
    frozen_order = baseline["project"]["paper_order"]
    if any(key not in project["papers"] or not (mt.ROOT / project["papers"][key]["tei"]).is_file()
           for key in frozen_order):
        pytest.skip("冻结基线所需的历史 TEI 缓存不完整")
    assert _logical_snapshot(mt, {**project, "paper_order": frozen_order}) == baseline


def test_project_config_points_only_at_existing_refactored_paths() -> None:
    from src import matrix_tool as mt

    project = mt.load_project()
    assert project["output_path"].startswith("data/exports/")
    for key in project["paper_order"]:
        info = project["papers"][key]
        assert info["pdf"].startswith("data/seed_papers/")
        assert info["tei"].startswith("data/state/papers/")
        assert (mt.ROOT / info["pdf"]).is_file()
        assert (mt.ROOT / info["tei"]).is_file()
