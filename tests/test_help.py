from __future__ import annotations


def test_help_overview_has_quickstart_and_command_groups(capsys) -> None:
    from src import matrix_tool as mt

    mt.main(["help"])

    output = capsys.readouterr().out
    assert "快速开始" in output
    assert "日常流程" in output
    assert "标签与翻译" in output
    assert "维护" in output
    assert "matrix_tool.py help 命令名" in output


def test_help_rebuild_describes_label_order_and_relabel(capsys) -> None:
    from src import matrix_tool as mt

    mt.main(["help", "rebuild"])

    output = capsys.readouterr().out
    assert "关系标签" in output
    assert "自动翻译" in output
    assert "--relabel" in output


def test_help_export_labels_explains_review_only_default(capsys) -> None:
    from src import matrix_tool as mt

    mt.main(["help", "export-labels"])

    output = capsys.readouterr().out
    assert "默认仅待复核项" in output
    assert "--all" in output
