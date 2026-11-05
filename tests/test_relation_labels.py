from __future__ import annotations

from types import SimpleNamespace

import pytest
from openpyxl import load_workbook
from openpyxl.cell.rich_text import CellRichText


class _FakeRelationClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[dict] = []
        completions = SimpleNamespace(create=self._create)
        self.chat = SimpleNamespace(completions=completions)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


def _rows() -> list[dict]:
    return [
        {
            "id": "row1",
            "display_title": "Cited Paper",
            "year": "2024",
            "per_paper": {
                "P1": {
                    "count": 2,
                    "blocks": [
                        {
                            "sentences": [
                                {"text": "Our method extends the cited work.", "cite": True, "markers": []},
                                {"text": "It also improves robustness.", "cite": False, "markers": []},
                            ]
                        }
                    ],
                }
            },
        }
    ]


def _project() -> dict:
    return {
        "paper_order": ["P1"],
        "papers": {"P1": {"header": "Current Seed Paper"}},
        "relationship_labeling": {
            "enabled": True,
            "batch_size": 8,
            "review_threshold": 0.7,
            "temperature": 0,
            "top_p": 0.95,
            "max_excerpt_chars": 2400,
            "max_tokens": 1800,
        },
    }


def _cfg() -> dict:
    return {
        "enabled": True,
        "base_url": "http://llm.test/v1",
        "api_key": "test-key",
        "model": "TestModel",
        "timeout": 60,
        "batch_size": 8,
        "review_threshold": 0.7,
        "temperature": 0,
        "top_p": 0.95,
        "max_tokens": 1800,
        "max_excerpt_chars": 2400,
        "missing_env": [],
    }


def test_relation_label_normalization_accepts_codes_names_and_display() -> None:
    from src import matrix_tool as mt

    assert mt.normalize_relation_label("B&E") == "B&E"
    assert mt.normalize_relation_label("基于与拓展") == "B&E"
    assert mt.normalize_relation_label("【对比与替代｜C&A】") == "C&A"
    assert mt.normalize_relation_label("不支持") == ""
    assert mt.relation_label_display("Q&A") == "【质疑与反驳｜Q&A】"


def test_cell_source_text_marks_citation_and_removes_placeholder() -> None:
    from src import matrix_tool as mt

    info = _rows()[0]["per_paper"]["P1"]

    text = mt.cell_source_text(info)

    assert text.startswith("▶ Our method extends the cited work.")
    assert "[[0]]" not in text
    assert "It also improves robustness." in text


def test_auto_label_missing_uses_llm_batch_and_writes_cache(monkeypatch) -> None:
    from src import matrix_tool as mt

    fake = _FakeRelationClient(
        '{"items":[{"id":"row1|P1","label":"B&E","confidence":0.91,"evidence":"extends"}]}'
    )
    written: dict[str, dict] = {}
    monkeypatch.setattr(mt, "load_relationship_label_cfg", lambda project: _cfg())
    monkeypatch.setattr(mt, "load_relation_label_cache", lambda: {})
    monkeypatch.setattr(mt, "load_relation_label_overrides", lambda: {})
    monkeypatch.setattr(mt, "write_relation_label_cache", lambda data: written.update(data))

    stats = mt.auto_label_missing(_rows(), _project(), quiet=True, client=fake)

    assert stats["labels"]["row1|P1"]["label"] == "B&E"
    assert stats["labels"]["row1|P1"]["source"] == "auto"
    assert written["row1|P1"]["label"] == "B&E"
    assert len(fake.calls) == 1
    assert fake.calls[0]["response_format"] == {"type": "json_object"}


def test_auto_label_missing_reuses_valid_content_hash_cache(monkeypatch) -> None:
    from src import matrix_tool as mt

    info = _rows()[0]["per_paper"]["P1"]
    content_hash = mt._cell_hash(mt.cell_source_text(info))
    cache = {
        "row1|P1": {
            "label": "C&A",
            "confidence": 0.88,
            "evidence": "extends",
            "content_hash": content_hash,
            "needs_review": False,
            "model": "TestModel",
        }
    }
    fake = _FakeRelationClient("{}")
    monkeypatch.setattr(mt, "load_relationship_label_cfg", lambda project: _cfg())
    monkeypatch.setattr(mt, "load_relation_label_cache", lambda: cache)
    monkeypatch.setattr(mt, "load_relation_label_overrides", lambda: {})
    monkeypatch.setattr(mt, "write_relation_label_cache", lambda data: None)

    stats = mt.auto_label_missing(_rows(), _project(), quiet=True, client=fake)

    assert stats["labels"]["row1|P1"]["label"] == "C&A"
    assert stats["labels"]["row1|P1"]["source"] == "auto"
    assert fake.calls == []


def test_manual_override_wins_and_skips_llm(monkeypatch) -> None:
    from src import matrix_tool as mt

    fake = _FakeRelationClient("{}")
    monkeypatch.setattr(mt, "load_relationship_label_cfg", lambda project: _cfg())
    monkeypatch.setattr(mt, "load_relation_label_cache", lambda: {})
    monkeypatch.setattr(mt, "load_relation_label_overrides", lambda: {"row1|P1": "Q&A"})
    monkeypatch.setattr(mt, "write_relation_label_cache", lambda data: None)

    stats = mt.auto_label_missing(_rows(), _project(), quiet=True, client=fake)

    assert stats["labels"]["row1|P1"]["label"] == "Q&A"
    assert stats["labels"]["row1|P1"]["source"] == "manual"
    assert stats["manual_count"] == 1
    assert fake.calls == []


def test_relabel_reclassifies_cached_content_but_keeps_manual_override(monkeypatch) -> None:
    from src import matrix_tool as mt

    info = _rows()[0]["per_paper"]["P1"]
    content_hash = mt._cell_hash(mt.cell_source_text(info))
    cache = {"row1|P1": {"label": "B&E", "confidence": 0.8, "evidence": "extends",
                         "content_hash": content_hash, "needs_review": False,
                         "model": "TestModel"}}
    fake = _FakeRelationClient(
        '{"items":[{"id":"row1|P1","label":"S&S","confidence":0.8,"evidence":"extends"}]}'
    )
    monkeypatch.setattr(mt, "load_relationship_label_cfg", lambda project: _cfg())
    monkeypatch.setattr(mt, "load_relation_label_cache", lambda: cache)
    monkeypatch.setattr(mt, "load_relation_label_overrides", lambda: {})
    monkeypatch.setattr(mt, "write_relation_label_cache", lambda data: None)

    stats = mt.auto_label_missing(_rows(), _project(), quiet=True, client=fake, relabel=True)

    assert stats["labels"]["row1|P1"]["label"] == "S&S"
    assert len(fake.calls) == 1


def test_invalid_llm_result_falls_back_to_mi_and_review(monkeypatch) -> None:
    from src import matrix_tool as mt

    fake = _FakeRelationClient("not json")
    monkeypatch.setattr(mt, "load_relationship_label_cfg", lambda project: _cfg())
    monkeypatch.setattr(mt, "load_relation_label_cache", lambda: {})
    monkeypatch.setattr(mt, "load_relation_label_overrides", lambda: {})
    monkeypatch.setattr(mt, "write_relation_label_cache", lambda data: None)

    stats = mt.auto_label_missing(_rows(), _project(), quiet=True, client=fake)

    assert stats["labels"]["row1|P1"]["label"] == "M/I"
    assert stats["labels"]["row1|P1"]["source"] == "fallback"
    assert stats["labels"]["row1|P1"]["needs_review"] is True
    assert stats["needs_review"] == 1


def test_service_failure_stops_requests_and_fallback_is_retryable(monkeypatch, capsys):
    from src import matrix_tool as mt

    cache = {}
    calls = []
    monkeypatch.setattr(mt, "load_relationship_label_cfg", lambda project: _cfg())
    monkeypatch.setattr(mt, "load_relation_label_cache", lambda: dict(cache))
    monkeypatch.setattr(mt, "load_relation_label_overrides", lambda: {})
    monkeypatch.setattr(mt, "write_relation_label_cache", lambda data: cache.update(data))

    def failed_batch(items, cfg, client):
        calls.append(len(items))
        raise TimeoutError("测试网络超时")

    rows = [{**_rows()[0], "id": f"row{i}"} for i in range(20)]
    monkeypatch.setattr(mt, "_classify_relation_batch", failed_batch)
    stats = mt.auto_label_missing(rows, _project(), client=object())
    assert calls == [8]
    assert stats["service_unavailable"] is True
    assert stats["failed"] == 20
    assert "关系分类 [1/3]" in capsys.readouterr().out
    # 临时网络失败的兜底不能变成永久自动标签，下一次仍应尝试。
    mt.auto_label_missing(rows, _project(), client=object(), quiet=True)
    assert calls == [8, 8]
    labels = mt.effective_relation_labels(rows, _project())
    assert labels["row0|P1"]["source"] == "fallback"


def test_cached_labels_do_not_even_construct_model_client(monkeypatch):
    from src import matrix_tool as mt

    cfg = _cfg()
    monkeypatch.setattr(mt, "load_relationship_label_cfg", lambda project: cfg)
    monkeypatch.setattr(mt, "load_relation_label_cache", lambda: {})
    monkeypatch.setattr(mt, "load_relation_label_overrides", lambda: {"row1|P1": "B&E"})
    monkeypatch.setattr(mt, "write_relation_label_cache", lambda data: None)
    monkeypatch.setattr(mt, "build_llm_client", lambda cfg: pytest.fail("不应构造模型客户端"))
    mt.auto_label_missing(_rows(), _project())


def test_relation_cache_is_saved_before_next_request(monkeypatch):
    from src import matrix_tool as mt

    cfg = {**_cfg(), "batch_size": 1}
    saved = {}
    monkeypatch.setattr(mt, "load_relationship_label_cfg", lambda project: cfg)
    monkeypatch.setattr(mt, "load_relation_label_cache", lambda: {})
    monkeypatch.setattr(mt, "load_relation_label_overrides", lambda: {})
    monkeypatch.setattr(mt, "write_relation_label_cache", lambda data: saved.update(data))
    rows = [_rows()[0], {**_rows()[0], "id": "row2"}]

    def classify(items, cfg, client):
        if items[0]["id"] == "row2|P1":
            assert saved["row1|P1"]["label"] == "B&E"
            raise KeyboardInterrupt()
        return {"row1|P1": {"label": "B&E", "confidence": 0.9, "evidence": "extends"}}

    monkeypatch.setattr(mt, "_classify_relation_batch", classify)
    with pytest.raises(KeyboardInterrupt):
        mt.auto_label_missing(rows, _project(), client=object())


def test_render_xlsx_adds_bold_label_prefix_and_normal_body(tmp_path, monkeypatch) -> None:
    from src import matrix_tool as mt

    monkeypatch.setattr(mt, "load_pool", lambda: {})
    monkeypatch.setattr(mt, "load_rules", lambda: [])
    out_path = tmp_path / "matrix.xlsx"
    project = {
        "paper_order": ["P1"],
        "papers": {"P1": {"header": "Current Seed Paper"}},
        "output_path": str(out_path),
    }
    labels = {"row1|P1": {"label": "B&E", "source": "auto", "confidence": 0.9,
                           "evidence": "extends", "needs_review": False}}

    mt.render_xlsx(_rows(), project, labels)

    ws = load_workbook(out_path, rich_text=True).active
    value = ws["B2"].value
    assert isinstance(value, CellRichText)
    assert str(value).startswith("【基于与拓展｜B&E】 ▶ Our method extends")
    assert value[0].font.b is True
    assert value[1].font.b is not True


@pytest.mark.parametrize("source", ["missing", "fallback"])
def test_missing_or_failed_labels_are_not_presented_as_model_conclusions(tmp_path, monkeypatch, source):
    from src import matrix_tool as mt

    monkeypatch.setattr(mt, "load_pool", lambda: {})
    monkeypatch.setattr(mt, "load_rules", lambda: [])
    path = tmp_path / "matrix.xlsx"
    project = {**_project(), "output_path": str(path)}
    labels = {"row1|P1": {"label": "M/I", "source": source, "needs_review": True}}
    mt.render_xlsx(_rows(), project, labels)
    wb = load_workbook(path)
    value = str(wb.active["B2"].value)
    wb.close()
    assert "待分类" in value
    assert "简单提及或无关" not in value


def test_export_labels_xlsx_has_dropdown_and_import_roundtrip(tmp_path) -> None:
    from src import matrix_tool as mt

    path = mt.export_relation_labels(
        _rows(),
        _project(),
        out_path=tmp_path / "labels.xlsx",
        labels={"row1|P1": {"label": "B&E", "source": "auto", "confidence": 0.9,
                             "evidence": "extends", "needs_review": True}},
    )
    wb = load_workbook(path)
    ws = wb.active
    headers = [cell.value for cell in ws[1]]
    human_col = headers.index("人工标签") + 1
    assert len(ws.data_validations.dataValidation) == 1
    ws.cell(row=2, column=human_col, value="质疑与反驳")
    wb.save(path)

    new_overrides = mt.parse_relation_label_import(path, {})

    assert new_overrides == {"row1|P1": "Q&A"}


def test_import_labels_rejects_invalid_labels_without_partial_update(tmp_path) -> None:
    from src import matrix_tool as mt

    path = mt.export_relation_labels(
        _rows(),
        _project(),
        out_path=tmp_path / "labels.xlsx",
        labels={"row1|P1": {"label": "B&E", "source": "auto", "confidence": 0.9,
                             "evidence": "extends", "needs_review": False}},
        include_all=True,
    )
    wb = load_workbook(path)
    ws = wb.active
    headers = [cell.value for cell in ws[1]]
    ws.cell(row=2, column=headers.index("人工标签") + 1, value="无效标签")
    wb.save(path)

    with pytest.raises(ValueError, match="无效标签"):
        mt.parse_relation_label_import(path, {"existing|P1": "C&A"})


def test_import_labels_auto_value_clears_existing_override(tmp_path) -> None:
    from src import matrix_tool as mt

    path = mt.export_relation_labels(
        _rows(),
        _project(),
        out_path=tmp_path / "labels.xlsx",
        labels={"row1|P1": {"label": "B&E", "source": "manual", "confidence": 1.0,
                             "evidence": "", "needs_review": False}},
        include_all=True,
    )
    wb = load_workbook(path)
    ws = wb.active
    headers = [cell.value for cell in ws[1]]
    ws.cell(row=2, column=headers.index("人工标签") + 1, value="自动")
    wb.save(path)

    new_overrides = mt.parse_relation_label_import(path, {"row1|P1": "B&E"})

    assert new_overrides == {}


def test_rebuild_all_classifies_before_translation(monkeypatch) -> None:
    from src import matrix_tool as mt

    calls: list[str] = []
    rows = _rows()
    monkeypatch.setattr(
        mt,
        "papers_data_fresh",
        lambda project, quiet=True, window=None: {"P1": {"refs_meta": {}, "contexts": {}}},
    )
    monkeypatch.setattr(mt, "write_json", lambda path, data: None)
    monkeypatch.setattr(mt, "compute_rows", lambda data, fixes: rows)
    monkeypatch.setattr(mt, "sort_rows", lambda data: data)
    monkeypatch.setattr(
        mt,
        "auto_label_missing",
        lambda rows, project, quiet=False, client=None, relabel=False: (
            calls.append("label") or {"labels": {"row1|P1": {"label": "B&E"}}}
        ),
    )
    monkeypatch.setattr(mt, "auto_translate_missing", lambda rows, project, quiet=False: calls.append("translate"))
    monkeypatch.setattr(mt, "render_xlsx", lambda rows, project, labels=None: calls.append("render") or {"rows": 1})

    mt.rebuild_all(_project(), quiet=True)

    assert calls == ["label", "translate", "render"]


def test_rebuild_skips_translation_after_model_service_failure(monkeypatch) -> None:
    from src import matrix_tool as mt

    monkeypatch.setattr(mt, "papers_data_fresh", lambda *args, **kwargs: {})
    monkeypatch.setattr(mt, "compute_rows", lambda *args: [])
    monkeypatch.setattr(mt, "load_fixes", lambda: [])
    monkeypatch.setattr(mt, "auto_label_missing", lambda *args, **kwargs: {"labels": {}, "service_unavailable": True})
    monkeypatch.setattr(mt, "auto_translate_missing", lambda *args, **kwargs: pytest.fail("不应再次请求故障服务"))
    monkeypatch.setattr(mt, "render_xlsx", lambda *args: {"rows": 0})
    rows, stats = mt.rebuild_all(_project(), quiet=True)
    assert rows == []
    assert stats["rows"] == 0


def test_cli_help_lists_relation_label_commands(capsys) -> None:
    from src import matrix_tool as mt

    mt.main(["help"])

    output = capsys.readouterr().out
    assert "export-labels" in output
    assert "import-labels" in output


def test_relation_review_policy_uses_060_and_only_requires_evidence_presence() -> None:
    from src import matrix_tool as mt

    assert mt.DEFAULT_RELATIONSHIP_LABELING["review_threshold"] == 0.60
    assert mt.needs_relation_review(0.8, "paraphrased evidence", 0.60) is False
    assert mt.needs_relation_review(0.59, "quoted evidence", 0.60) is True
    assert mt.needs_relation_review(0.8, "", 0.60) is True


def test_export_labels_defaults_to_review_rows_only(tmp_path) -> None:
    from src import matrix_tool as mt

    first = _rows()[0]
    second = {
        "id": "row2",
        "display_title": "Another Paper",
        "year": "2025",
        "per_paper": {
            "P1": {
                "count": 1,
                "blocks": [{"sentences": [{"text": "A low confidence example.", "cite": True, "markers": []}]}],
            }
        },
    }
    labels = {
        "row1|P1": {"label": "B&E", "source": "auto", "confidence": 0.9,
                     "evidence": "extends", "needs_review": False},
        "row2|P1": {"label": "M/I", "source": "auto", "confidence": 0.4,
                     "evidence": "", "needs_review": True},
    }

    review_path = mt.export_relation_labels(
        [first, second], _project(), out_path=tmp_path / "review.xlsx", labels=labels
    )
    all_path = mt.export_relation_labels(
        [first, second], _project(), out_path=tmp_path / "all.xlsx", labels=labels,
        include_all=True,
    )

    review_ws = load_workbook(review_path).active
    all_ws = load_workbook(all_path).active
    assert review_ws.max_row == 2
    assert all_ws.max_row == 3
