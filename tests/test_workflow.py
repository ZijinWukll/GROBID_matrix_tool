from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from test_build import TEI, put_pdf, workspace


def test_build_reuses_legacy_tei_without_pdf_digest(workspace, monkeypatch):
    mt, calls = workspace
    put_pdf(mt, "A.pdf")
    mt.main(["build", "--no-llm"])
    p = mt.load_project()
    p["papers"]["A"].pop("pdf_sha256")
    mt.write_json(mt.CONFIG_DIR / "project.json", p)
    monkeypatch.setattr(mt, "grobid_alive", lambda base: pytest.fail("旧 TEI 应复用"))
    mt.main(["build", "--no-llm"])
    assert calls == ["A.pdf"]


def test_build_repairs_corrupt_tei_cache_automatically(workspace):
    mt, calls = workspace
    put_pdf(mt, "A.pdf")
    mt.main(["build", "--no-llm"])
    (mt.PAPERS_STATE_DIR / "A.tei.xml").write_text("broken XML")
    mt.main(["build", "--no-llm"])
    assert calls == ["A.pdf", "A.pdf"]


def test_truncated_grobid_xml_is_not_registered_as_success(workspace, monkeypatch):
    mt, calls = workspace
    put_pdf(mt, "A.pdf")
    monkeypatch.setattr(mt, "grobid_fulltext", lambda *args: "<TEI><text>truncated")
    with pytest.raises(SystemExit):
        mt.main(["build", "--no-llm"])
    assert mt.load_project()["paper_order"] == []


def test_build_cannot_include_papers_outside_input(workspace):
    mt, calls = workspace
    pdf = put_pdf(mt, "OLD.pdf")
    mt.main(["build", "--no-llm"])
    pdf.unlink()
    put_pdf(mt, "NEW.pdf")
    with pytest.raises(SystemExit):
        mt.main(["build", "--keep-existing", "--no-llm"])
    mt.main(["build", "--no-llm"])
    assert mt.load_project()["paper_order"] == ["NEW"]


def test_import_stages_pdf_and_tei_without_building(workspace, monkeypatch):
    mt, calls = workspace
    external = mt.ROOT / "download.pdf"
    external.write_bytes(b"external pdf")
    tei = mt.ROOT / "existing.xml"
    tei.write_text(TEI)
    monkeypatch.setattr(mt, "render_xlsx", lambda *args: pytest.fail("导入不应出表"))
    mt.main(["import", str(external), "--from-tei", str(tei)])
    assert mt.load_project()["paper_order"] == []
    assert (mt.INPUT_SEED_DIR / "download.pdf").is_file()
    assert (mt.PAPERS_STATE_DIR / "download.tei.xml").is_file()
    assert not calls


def test_export_uses_json_snapshot_without_pdf_tei_or_network(workspace, monkeypatch):
    mt, calls = workspace
    pdf = put_pdf(mt, "A.pdf")
    mt.main(["build", "--no-llm"])
    before = (mt.PAPERS_STATE_DIR / "A.json").read_bytes()
    pdf.unlink()
    (mt.PAPERS_STATE_DIR / "A.tei.xml").unlink()
    monkeypatch.setattr(mt, "papers_data_fresh", lambda *args, **kwargs: pytest.fail("离线导出不应抽取"))
    monkeypatch.setattr(mt, "build_llm_client", lambda *args: pytest.fail("离线导出不应联网"))
    mt.main(["export"])
    assert (mt.PAPERS_STATE_DIR / "A.json").read_bytes() == before
    assert (mt.ROOT / mt.load_project()["output_path"]).is_file()


def test_manual_cache_clean_previews_then_only_removes_inactive_parsing_cache(workspace):
    mt, calls = workspace
    pdf = put_pdf(mt, "OLD.pdf")
    mt.main(["build", "--no-llm"])
    pdf.unlink()
    put_pdf(mt, "NEW.pdf")
    mt.main(["build", "--no-llm"])
    mt.write_pool({"manual": "人工译文"})
    mt.write_relation_label_overrides({"ref|OLD": "B&E"})
    mt.main(["cache", "clean"])
    assert (mt.PAPERS_STATE_DIR / "OLD.tei.xml").is_file()
    mt.main(["cache", "clean", "--apply"])
    assert not (mt.PAPERS_STATE_DIR / "OLD.tei.xml").exists()
    assert not (mt.PAPERS_STATE_DIR / "OLD.json").exists()
    assert (mt.PAPERS_STATE_DIR / "NEW.tei.xml").is_file()
    assert (mt.INPUT_SEED_DIR / "NEW.pdf").is_file()
    assert mt.load_pool() == {"manual": "人工译文"}
    assert mt.load_relation_label_overrides() == {"ref|OLD": "B&E"}


def test_cache_clean_rejects_outside_path_before_any_deletion(workspace):
    mt, calls = workspace
    mt.main(["init"])
    outside = mt.STATE_DIR / "outside.json"
    outside.write_text("preserve")
    p = mt.load_project()
    p["papers"]["../outside"] = {"tei": "data/state/outside.tei.xml"}
    mt.write_json(mt.CONFIG_DIR / "project.json", p)
    with pytest.raises(SystemExit, match="路径"):
        mt.main(["cache", "clean", "--apply"])
    assert outside.read_text() == "preserve"


def test_short_request_ids_and_fenced_json_are_mapped_back():
    from src import matrix_tool as mt

    def create(**kwargs):
        payload = json.loads(kwargs["messages"][1]["content"])
        assert payload["items"][0]["id"] == "item_1"
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content='```json\n{"items":[{"id":"item_1","label":"B&E","confidence":0.9,"evidence":"extends"}]}\n```'
        ))])
    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    items = [{"id": "a_long_title|P", "current_paper": "Current", "cited_paper": "Prior", "excerpt": "extends"}]
    assert mt._classify_relation_batch(items, {"model": "test"}, fake)["a_long_title|P"]["label"] == "B&E"


def test_classification_recovers_empty_batch_by_splitting(monkeypatch):
    from src import matrix_tool as mt

    calls = []
    def classify(items, cfg, client):
        calls.append(len(items))
        if len(items) > 1:
            return {}
        return {items[0]["id"]: {"label": "S&S", "confidence": 0.9, "evidence": "supports"}}
    monkeypatch.setattr(mt, "_classify_relation_batch", classify)
    result = mt.classify_with_recovery([{"id": "A"}, {"id": "B"}], {"max_tokens": 100}, object())
    assert set(result) == {"A", "B"}
    assert calls == [2, 1, 1]


def test_translation_completes_all_chunks_and_recovers_empty_output(monkeypatch):
    from src import matrix_tool as mt

    texts = ["First sentence.", "Second sentence.", "Third sentence."]
    rows = [{"per_paper": {"P": {"blocks": [{"sentences": [{"text": t} for t in texts]}]}}}]
    cfg = {"model": "test", "max_per_run": 1, "max_tokens": 100}
    saved, calls = {}, []
    def create(**kwargs):
        calls.append(kwargs["max_tokens"])
        content = "" if len(calls) == 1 else "中文译文"
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(mt, "load_translation_cfg", lambda project: cfg)
    monkeypatch.setattr(mt, "load_pool", lambda: {})
    monkeypatch.setattr(mt, "write_pool", lambda pool: saved.update(pool))
    stats = mt.auto_translate_missing(rows, {}, client=client)
    assert stats["translated"] == 3
    assert stats["skipped"] == 0
    assert len(saved) == 3
    assert calls[:2] == [100, 200]


def test_low_confidence_cached_label_gets_one_automatic_check(workspace, monkeypatch):
    mt, calls = workspace
    put_pdf(mt, "A.pdf")
    mt.main(["build", "--no-llm"])
    p = mt.load_project()
    rows = mt.sort_rows(mt.compute_rows(mt.papers_data_fresh(p), mt.load_fixes()))
    row = rows[0]; item_key = f"{row['id']}|A"
    mt.write_relation_label_cache({item_key: {"label": "B&E", "confidence": 0.3, "evidence": "extend",
        "content_hash": mt._cell_hash(mt.cell_source_text(row["per_paper"]["A"]))}})
    monkeypatch.setattr(mt, "load_relationship_label_cfg", lambda p: {"model": "test", "batch_size": 1})
    requests = []
    def classify(items, cfg, client):
        requests.append(True)
        return {item_key: {"label": "B&E", "confidence": 0.9, "evidence": "extend"}}
    monkeypatch.setattr(mt, "_classify_relation_batch", classify)
    first = mt.auto_label_missing(rows, p, client=object())
    second = mt.auto_label_missing(rows, p, client=object())
    assert not first["labels"][item_key]["needs_review"]
    assert len(requests) == 1


def test_clean_all_preserves_custom_keys_and_manual_data(workspace):
    mt, calls = workspace
    pdf = put_pdf(mt, "A.pdf")
    tei = mt.ROOT / "cached.xml"
    tei.write_text(TEI)
    mt.main(["import", str(pdf), "--from-tei", str(tei), "--key", "CUSTOM"])
    mt.main(["build", "--no-llm"])
    mt.write_relation_label_overrides({"citedpaper|CUSTOM": "Q&A"})
    mt.main(["cache", "clean", "--all", "--apply"])
    assert mt.load_project()["paper_order"] == ["CUSTOM"]
    assert not (mt.PAPERS_STATE_DIR / "CUSTOM.json").exists()
    mt.main(["status"])
    mt.main(["build", "--no-llm"])
    assert mt.load_project()["paper_order"] == ["CUSTOM"]
    assert mt.load_relation_label_overrides() == {"citedpaper|CUSTOM": "Q&A"}


def test_import_conflict_is_checked_before_copying(workspace):
    mt, calls = workspace
    pdf = put_pdf(mt, "A.pdf")
    tei = mt.ROOT / "cached.xml"
    tei.write_text(TEI)
    mt.main(["import", str(pdf), "--from-tei", str(tei), "--key", "CUSTOM"])
    other = mt.ROOT / "B.pdf"
    other.write_bytes(b"different")
    with pytest.raises(SystemExit, match="冲突"):
        mt.main(["import", str(other), "--from-tei", str(tei), "--key", "CUSTOM"])
    assert not (mt.INPUT_SEED_DIR / "B.pdf").exists()


def test_auto_check_disagreement_is_not_hidden(workspace, monkeypatch):
    mt, calls = workspace
    put_pdf(mt, "A.pdf")
    mt.main(["build", "--no-llm"])
    p = mt.load_project()
    rows = mt.sort_rows(mt.compute_rows(mt.papers_data_fresh(p), mt.load_fixes()))
    key = f"{rows[0]['id']}|A"
    monkeypatch.setattr(mt, "load_relationship_label_cfg", lambda p: {"model": "test"})
    answers = iter([{"label": "B&E", "confidence": 0.3, "evidence": "extend"},
                    {"label": "C&A", "confidence": 0.9, "evidence": "extend"}])
    monkeypatch.setattr(mt, "_classify_relation_batch", lambda items, cfg, client: {key: next(answers)})
    first = mt.auto_label_missing(rows, p, client=object())
    assert first["labels"][key]["needs_review"]
    assert mt.load_relation_label_cache()[key]["review_reason"]
    mt.auto_label_missing(rows, p, client=object())  # 检查过的分歧不会每次重跑。


def test_auto_check_network_failure_keeps_first_valid_result(workspace, monkeypatch):
    mt, calls = workspace
    put_pdf(mt, "A.pdf")
    mt.main(["build", "--no-llm"])
    p = mt.load_project()
    rows = mt.sort_rows(mt.compute_rows(mt.papers_data_fresh(p), mt.load_fixes()))
    key = f"{rows[0]['id']}|A"
    monkeypatch.setattr(mt, "load_relationship_label_cfg", lambda p: {"model": "test"})
    n = []
    def classify(items, cfg, client):
        n.append(True)
        if len(n) > 1:
            raise TimeoutError()
        return {key: {"label": "B&E", "confidence": 0.3, "evidence": "extend"}}
    monkeypatch.setattr(mt, "_classify_relation_batch", classify)
    stats = mt.auto_label_missing(rows, p, client=object())
    assert stats["service_unavailable"]
    assert stats["labels"][key]["label"] == "B&E"
    assert mt.load_relation_label_cache()[key]["source"] == "auto"


def test_valid_but_uncertain_mi_is_not_retried_forever(workspace, monkeypatch):
    mt, calls = workspace
    put_pdf(mt, "A.pdf")
    mt.main(["build", "--no-llm"])
    p = mt.load_project()
    rows = mt.sort_rows(mt.compute_rows(mt.papers_data_fresh(p), mt.load_fixes()))
    key = f"{rows[0]['id']}|A"
    monkeypatch.setattr(mt, "load_relationship_label_cfg", lambda p: {"model": "test"})
    requests = []
    def classify(items, cfg, client):
        requests.append(True)
        return {key: {"label": "M/I", "confidence": 0, "evidence": ""}}
    monkeypatch.setattr(mt, "_classify_relation_batch", classify)
    mt.auto_label_missing(rows, p, client=object())
    mt.auto_label_missing(rows, p, client=object())
    assert len(requests) == 2
    assert mt.load_relation_label_cache()[key]["needs_review"]
