from __future__ import annotations

import pytest
from openpyxl import load_workbook


TEI = '''<TEI><teiHeader><fileDesc><titleStmt><title>Seed Paper</title>
</titleStmt></fileDesc></teiHeader><text><body><p>We extend prior work
<ref type="bibr" target="#b1">[1]</ref>.</p></body><back><listBibl>
<biblStruct xml:id="b1"><analytic><title level="a">Cited Paper</title>
</analytic></biblStruct></listBibl></back></text></TEI>'''


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    from src import matrix_tool as mt

    paths = {
        "PROJECT_ROOT": tmp_path, "ROOT": tmp_path,
        "DATA_DIR": tmp_path / "data", "CONFIG_DIR": tmp_path / "data/config",
        "STATE_DIR": tmp_path / "data/state",
        "PAPERS_STATE_DIR": tmp_path / "data/state/papers",
        "INPUT_SEED_DIR": tmp_path / "data/seed_papers",
        "OUTPUT_DIR": tmp_path / "data/exports", "LOG_DIR": tmp_path / "log",
        "TRANS_POOL": tmp_path / "data/state/translations_by_hash.json",
        "RELATION_LABELS_FILE": tmp_path / "data/state/relation_labels.json",
        "RELATION_OVERRIDES_FILE": tmp_path / "data/config/relation_label_overrides.json",
    }
    for name, path in paths.items():
        monkeypatch.setattr(mt, name, path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MATRIX_GROBID_URL", "http://grobid.test")
    for name in mt.TRANSLATION_ENV_VARS.values():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(mt, "grobid_alive", lambda base: True)
    calls = []

    def parse(base, pdf):
        calls.append(pdf.name)
        return TEI

    monkeypatch.setattr(mt, "grobid_fulltext", parse)
    return mt, calls


def put_pdf(mt, name, content=b"test pdf"):
    mt.INPUT_SEED_DIR.mkdir(parents=True, exist_ok=True)
    path = mt.INPUT_SEED_DIR / name
    path.write_bytes(content)
    return path


def test_init_creates_empty_project_without_legacy_files_or_network(workspace, monkeypatch):
    mt, calls = workspace
    monkeypatch.setattr(mt, "grobid_alive", lambda base: pytest.fail("不应联网"))
    mt.main(["init"])
    assert mt.load_project()["paper_order"] == []
    assert mt.load_project()["papers"] == {}
    mt.main(["status"])
    assert not calls


def test_build_bootstraps_and_renders_all_pdfs_once(workspace, monkeypatch):
    mt, calls = workspace
    put_pdf(mt, "B.PDF")
    put_pdf(mt, "A.pdf")
    (mt.INPUT_SEED_DIR / "ignore.txt").write_text("ignore")
    renders = []
    original = mt.render_xlsx

    def render(*args, **kwargs):
        renders.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(mt, "render_xlsx", render)
    mt.main(["build", "--no-translate"])
    assert calls == ["A.pdf", "B.PDF"]
    assert len(renders) == 1
    assert mt.load_project()["paper_order"] == ["A", "B"]
    wb = load_workbook(mt.ROOT / mt.load_project()["output_path"])
    assert wb.active.max_row == 2
    assert wb.active.max_column == 7
    wb.close()
    mt.main(["status"])


def test_build_reuses_cache_and_only_parses_changed_or_missing_tei(workspace, monkeypatch):
    mt, calls = workspace
    path = put_pdf(mt, "A.pdf")
    mt.main(["build", "--no-translate"])
    monkeypatch.setattr(mt, "grobid_alive", lambda base: pytest.fail("缓存完整时不应联网"))
    mt.main(["build", "--no-translate"])
    assert calls == ["A.pdf"]
    monkeypatch.setattr(mt, "grobid_alive", lambda base: True)
    path.write_bytes(b"updated pdf")
    mt.main(["build", "--no-translate"])
    (mt.PAPERS_STATE_DIR / "A.tei.xml").unlink()
    mt.main(["build", "--no-translate"])
    assert calls == ["A.pdf"] * 3


def test_build_accepts_custom_folder_and_preserves_custom_key_and_header(workspace):
    mt, calls = workspace
    inbox = mt.ROOT / "input"
    inbox.mkdir()
    source = inbox / "A.pdf"
    source.write_bytes(b"test pdf")
    tei = mt.ROOT / "existing.xml"
    tei.write_text(TEI)
    mt.main(["init"])
    mt.main(["add", str(source), "--key", "CUSTOM", "--from-tei", str(tei), "--no-translate"])
    project = mt.load_project()
    project["papers"]["CUSTOM"]["header"] = "人工表头"
    mt.write_json(mt.CONFIG_DIR / "project.json", project)
    mt.main(["build", "--input-dir", "input", "--no-translate"])
    assert not calls
    source.write_bytes(b"new content")
    mt.main(["build", "--input-dir", "input", "--no-translate"])
    assert calls == ["A.pdf"]
    assert mt.load_project()["paper_order"] == ["CUSTOM"]
    assert mt.load_project()["papers"]["CUSTOM"]["header"] == "人工表头"


def test_chinese_filenames_get_distinct_stable_keys(workspace):
    mt, calls = workspace
    put_pdf(mt, "论文甲.pdf")
    put_pdf(mt, "论文乙.pdf")
    mt.main(["build", "--no-translate"])
    keys = mt.load_project()["paper_order"]
    assert len(set(keys)) == 2
    mt.main(["build", "--no-translate"])
    assert mt.load_project()["paper_order"] == keys
    assert len(calls) == 2


def test_empty_folder_gives_actionable_message_without_export(workspace, capsys):
    mt, calls = workspace
    mt.main(["build"])
    output = capsys.readouterr().out
    assert "PDF" in output and "data/seed_papers" in output
    assert not list(mt.OUTPUT_DIR.glob("*.xlsx"))
    assert not calls


def test_build_syncs_current_folder_and_keeps_inactive_cache_for_restore(workspace):
    mt, calls = workspace
    pdf = put_pdf(mt, "A.pdf")
    mt.main(["build", "--no-translate"])
    pdf.unlink()
    mt.main(["build", "--no-translate"])
    assert mt.load_project()["paper_order"] == []
    assert (mt.PAPERS_STATE_DIR / "A.tei.xml").is_file()
    assert load_workbook(mt.ROOT / mt.load_project()["output_path"]).active.max_row == 1
    put_pdf(mt, "A.pdf")
    mt.main(["build", "--no-translate"])
    assert mt.load_project()["paper_order"] == ["A"]
    assert calls == ["A.pdf"]


def test_replacing_all_pdfs_only_exports_current_papers(workspace):
    mt, calls = workspace
    pdf = put_pdf(mt, "OLD.pdf")
    mt.main(["build", "--no-translate"])
    pdf.unlink()
    put_pdf(mt, "NEW.pdf")
    mt.main(["build", "--no-translate"])
    assert mt.load_project()["paper_order"] == ["NEW"]
    assert (mt.PAPERS_STATE_DIR / "OLD.tei.xml").is_file()
    wb = load_workbook(mt.ROOT / mt.load_project()["output_path"])
    assert wb.active.max_column == 5
    wb.close()


def test_custom_folder_is_authoritative_even_with_archived_pdfs(workspace):
    mt, calls = workspace
    put_pdf(mt, "OLD.pdf")
    mt.main(["build", "--no-translate"])
    inbox = mt.ROOT / "input"
    inbox.mkdir()
    (inbox / "NEW.pdf").write_bytes(b"new")
    mt.main(["build", "--input-dir", "input", "--no-translate"])
    assert mt.load_project()["paper_order"] == ["NEW"]


def test_keep_existing_build_preserves_accumulating_workflow(workspace):
    mt, calls = workspace
    pdf = put_pdf(mt, "OLD.pdf")
    mt.main(["build", "--no-translate"])
    pdf.unlink()
    put_pdf(mt, "NEW.pdf")
    mt.main(["build", "--keep-existing", "--no-translate"])
    assert mt.load_project()["paper_order"] == ["OLD", "NEW"]


def test_failed_changed_pdf_does_not_silently_export_its_old_version(workspace, monkeypatch):
    mt, calls = workspace
    changed = put_pdf(mt, "A.pdf")
    put_pdf(mt, "B.pdf")
    mt.main(["build", "--no-translate"])
    changed.write_bytes(b"changed")
    monkeypatch.setattr(mt, "grobid_fulltext", lambda *args: "invalid")
    with pytest.raises(SystemExit):
        mt.main(["build", "--no-translate"])
    assert mt.load_project()["paper_order"] == ["B"]


def test_no_llm_build_reuses_manual_results_without_model_calls(workspace, monkeypatch):
    mt, calls = workspace
    put_pdf(mt, "A.pdf")
    monkeypatch.setattr(mt, "build_llm_client", lambda cfg: pytest.fail("不应请求模型"))
    mt.main(["build", "--no-llm"])
    mt.main(["rebuild", "--no-llm"])
    assert (mt.ROOT / mt.load_project()["output_path"]).is_file()


def test_empty_folder_sync_excludes_tei_only_papers_but_rebuild_retains_them(workspace):
    mt, calls = workspace
    tei = mt.ROOT / "existing.xml"
    tei.write_text(TEI)
    mt.main(["add", "--from-tei", str(tei), "--key", "OFFLINE", "--no-translate"])
    mt.main(["rebuild", "--no-translate"])
    assert mt.load_project()["paper_order"] == ["OFFLINE"]
    mt.main(["build", "--no-translate"])
    assert mt.load_project()["paper_order"] == []


def test_parse_failure_keeps_successes_and_can_resume(workspace, monkeypatch, capsys):
    mt, calls = workspace
    put_pdf(mt, "A.pdf")
    put_pdf(mt, "B.pdf")
    parse = mt.grobid_fulltext

    def fail_second(base, pdf):
        if pdf.name == "B.pdf":
            raise RuntimeError("测试解析失败")
        return parse(base, pdf)

    monkeypatch.setattr(mt, "grobid_fulltext", fail_second)
    with pytest.raises(SystemExit):
        mt.main(["build", "--no-translate"])
    assert "B.pdf" in capsys.readouterr().out
    assert mt.load_project()["paper_order"] == ["A"]
    monkeypatch.setattr(mt, "grobid_fulltext", parse)
    mt.main(["build", "--no-translate"])
    assert calls == ["A.pdf", "B.pdf"]


def test_invalid_grobid_response_does_not_register_empty_paper(workspace, monkeypatch):
    mt, calls = workspace
    put_pdf(mt, "A.pdf")
    monkeypatch.setattr(mt, "grobid_fulltext", lambda *args: "<html>服务错误</html>")
    with pytest.raises(SystemExit):
        mt.main(["build", "--no-translate"])
    assert mt.load_project()["paper_order"] == []


def test_build_preserves_manual_data(workspace):
    mt, calls = workspace
    mt.main(["init"])
    overrides = {"citedpaper|A": "B&E"}
    mt.write_relation_label_overrides(overrides)
    mt.write_pool({mt._hash8("We extend prior work [1]."): "人工译文"})
    before = mt.TRANS_POOL.read_bytes()
    put_pdf(mt, "A.pdf")
    mt.main(["build", "--no-translate", "--relabel"])
    assert mt.load_relation_label_overrides() == overrides
    assert mt.TRANS_POOL.read_bytes() == before
    rows = mt.sort_rows(mt.compute_rows(mt.papers_data_fresh(mt.load_project()), mt.load_fixes()))
    assert mt.effective_relation_labels(rows, mt.load_project())["citedpaper|A"]["source"] == "manual"


def test_init_preserves_existing_rules_and_force_keeps_registered_papers(workspace):
    mt, calls = workspace
    put_pdf(mt, "A.pdf")
    mt.main(["build", "--no-translate"])
    rules = {"schema_version": 1, "rules": [{"match": "test", "abbr": "人工"}]}
    mt.write_json(mt.CONFIG_DIR / "abbrev_rules.json", rules)
    before = mt.load_project()
    mt.main(["init", "--force"])
    assert mt.load_project() == before
    assert mt.load_json(mt.CONFIG_DIR / "abbrev_rules.json") == rules


def test_legacy_migration_remains_explicitly_available(workspace):
    mt, calls = workspace
    mt.OUTPUT_DIR.mkdir(parents=True)
    for seed in mt.LEGACY_SEEDS.values():
        (mt.ROOT / seed["legacy_tei"]).write_text(TEI)
    mt.main(["init", "--migrate-legacy"])
    assert mt.load_project()["paper_order"] == list(mt.LEGACY_SEEDS)


def test_batch_key_conflict_does_not_overwrite_existing_paper(workspace):
    mt, calls = workspace
    source = put_pdf(mt, "A.pdf")
    tei = mt.ROOT / "existing.xml"
    tei.write_text(TEI)
    mt.main(["add", str(source), "--key", "B", "--from-tei", str(tei), "--no-translate"])
    before = mt.load_project()
    put_pdf(mt, "B.pdf", b"different")
    with pytest.raises(SystemExit):
        mt.main(["build", "--no-translate"])
    assert not calls
    assert mt.load_project() == before


def test_build_only_parses_new_pdfs_and_forwards_rebuild_options(workspace):
    mt, calls = workspace
    put_pdf(mt, "A.pdf")
    mt.main(["build", "--no-translate"])
    put_pdf(mt, "B.pdf")
    mt.main(["build", "--no-translate", "--window", "0", "--relabel"])
    assert calls == ["A.pdf", "B.pdf"]
    assert mt.load_project()["paper_order"] == ["A", "B"]


def test_unavailable_grobid_keeps_previous_export_and_state(workspace, monkeypatch):
    mt, calls = workspace
    put_pdf(mt, "A.pdf")
    mt.main(["build", "--no-translate"])
    project_bytes = (mt.CONFIG_DIR / "project.json").read_bytes()
    output = mt.ROOT / mt.load_project()["output_path"]
    before = output.read_bytes()
    put_pdf(mt, "B.pdf")
    monkeypatch.setattr(mt, "grobid_alive", lambda base: False)
    with pytest.raises(SystemExit, match="GROBID"):
        mt.main(["build", "--no-translate"])
    assert (mt.CONFIG_DIR / "project.json").read_bytes() == project_bytes
    assert output.read_bytes() == before


def test_tei_only_add_and_rebuild_work_without_grobid(workspace, monkeypatch):
    mt, calls = workspace
    monkeypatch.setattr(mt, "grobid_alive", lambda base: pytest.fail("不应联网"))
    tei = mt.ROOT / "existing.xml"
    tei.write_text(TEI)
    mt.main(["add", "--from-tei", str(tei), "--key", "OFFLINE", "--no-translate"])
    mt.main(["rebuild", "--no-translate"])
    assert mt.load_project()["paper_order"] == ["OFFLINE"]
    assert not calls


def test_missing_custom_folder_is_reported_without_scanning_default(workspace):
    mt, calls = workspace
    put_pdf(mt, "A.pdf")
    with pytest.raises(SystemExit, match="文件夹不存在"):
        mt.main(["build", "--input-dir", "typo"])
    assert not calls


def test_init_without_force_does_not_reset_existing_project(workspace):
    mt, calls = workspace
    put_pdf(mt, "A.pdf")
    mt.main(["build", "--no-translate"])
    before = mt.load_project()
    with pytest.raises(SystemExit, match="已初始化"):
        mt.main(["init"])
    assert mt.load_project() == before


def test_add_force_repairs_missing_tei(workspace):
    mt, calls = workspace
    pdf = put_pdf(mt, "A.pdf")
    mt.main(["build", "--no-translate"])
    (mt.PAPERS_STATE_DIR / "A.tei.xml").unlink()
    tei = mt.ROOT / "existing.xml"
    tei.write_text(TEI)
    mt.main(["add", str(pdf), "--force", "--from-tei", str(tei), "--no-translate"])
    assert (mt.PAPERS_STATE_DIR / "A.tei.xml").is_file()
    assert mt.load_project()["paper_order"] == ["A"]


def test_add_preserves_legacy_key_when_adding_same_filename(workspace):
    mt, calls = workspace
    pdf = put_pdf(mt, "Paper One.pdf")
    tei = mt.ROOT / "existing.xml"
    tei.write_text(TEI)
    mt.main(["add", str(pdf), "--key", "Paper_One", "--from-tei", str(tei), "--no-translate"])
    with pytest.raises(SystemExit, match="已存在"):
        mt.main(["add", str(pdf), "--from-tei", str(tei), "--no-translate"])
    assert mt.load_project()["paper_order"] == ["Paper_One"]


def test_add_does_not_overwrite_another_registered_pdf(workspace):
    mt, calls = workspace
    pdf = put_pdf(mt, "A.pdf")
    tei = mt.ROOT / "existing.xml"
    tei.write_text(TEI)
    mt.main(["add", str(pdf), "--from-tei", str(tei), "--no-translate"])
    other_dir = mt.ROOT / "other"
    other_dir.mkdir()
    other = other_dir / "A.pdf"
    other.write_bytes(b"different paper")
    with pytest.raises(SystemExit, match="冲突"):
        mt.main(["add", str(other), "--key", "OTHER", "--from-tei", str(tei), "--no-translate"])
    assert pdf.read_bytes() == b"test pdf"
    assert mt.load_project()["paper_order"] == ["A"]
