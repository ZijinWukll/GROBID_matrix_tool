from __future__ import annotations

import json

from conftest import PROJECT_ROOT


def test_grobid_url_comes_from_environment(monkeypatch) -> None:
    from src import matrix_tool as mt

    monkeypatch.setenv("MATRIX_GROBID_URL", "http://grobid.test:8070")

    assert mt.load_grobid_url({}) == "http://grobid.test:8070"


def test_grobid_url_legacy_project_fallback_is_supported(monkeypatch) -> None:
    from src import matrix_tool as mt

    monkeypatch.delenv("MATRIX_GROBID_URL", raising=False)

    assert mt.load_grobid_url({"grobid_url": "http://legacy.test:8070"}) == "http://legacy.test:8070"


def test_example_configs_keep_school_endpoints_out_of_project_json() -> None:
    example = json.loads(
        (PROJECT_ROOT / "data" / "config" / "project.example.json").read_text(encoding="utf-8")
    )
    env_example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")

    assert "grobid_url" not in example
    assert "MATRIX_GROBID_URL=" in env_example
