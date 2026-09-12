from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from conftest import PROJECT_ROOT


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class _FakeClient:
    def __init__(self, content: str) -> None:
        self.completions = _FakeCompletions(content)
        self.chat = SimpleNamespace(completions=self.completions)


def test_translation_connection_comes_from_environment(monkeypatch) -> None:
    from src import matrix_tool as mt

    monkeypatch.setenv("MATRIX_LLM_BASE_URL", "http://llm.test:8900/v1")
    monkeypatch.setenv("MATRIX_LLM_API_KEY", "test-key")
    monkeypatch.setenv("MATRIX_LLM_MODEL", "TestModel")

    cfg = mt.load_translation_cfg({"translation": {"enabled": True}})

    assert cfg is not None
    assert cfg["base_url"] == "http://llm.test:8900/v1"
    assert cfg["api_key"] == "test-key"
    assert cfg["model"] == "TestModel"


def test_translate_via_llm_uses_configured_model_and_translation_prompt() -> None:
    from src import matrix_tool as mt

    assert hasattr(mt, "translate_via_llm"), "缺少本地 LLM 翻译函数"
    fake = _FakeClient("你好，世界。")
    cfg = {
        "model": "TestModel",
        "timeout": 30,
        "temperature": 0.2,
        "top_p": 0.95,
        "max_tokens": 512,
        "source_lang": "en",
        "target_lang": "zh-CN",
    }

    result = mt.translate_via_llm("Hello, world.", cfg, client=fake)

    assert result == "你好，世界。"
    assert len(fake.completions.calls) == 1
    call = fake.completions.calls[0]
    assert call["model"] == "TestModel"
    assert "只输出译文" in call["messages"][0]["content"]
    assert call["messages"][1]["content"] == "Hello, world."


def test_auto_translate_missing_writes_llm_result_to_pool(monkeypatch) -> None:
    from src import matrix_tool as mt

    assert hasattr(mt, "translate_via_llm"), "缺少本地 LLM 翻译函数"
    rows = [
        {
            "per_paper": {
                "PAPER1": {
                    "count": 1,
                    "blocks": [{"sentences": [{"text": "Hello, world."}]}],
                }
            }
        }
    ]
    cfg = {
        "enabled": True,
        "model": "TestModel",
        "source_lang": "en",
        "target_lang": "zh-CN",
        "timeout": 30,
        "temperature": 0.2,
        "top_p": 0.95,
        "max_tokens": 512,
        "delay": 0,
        "max_per_run": 10,
    }
    fake = _FakeClient("你好，世界。")
    written: dict[str, str] = {}
    monkeypatch.setattr(mt, "load_translation_cfg", lambda project: cfg)
    monkeypatch.setattr(mt, "load_pool", lambda: {})
    monkeypatch.setattr(mt, "write_pool", lambda pool: written.update(pool))

    stats = mt.auto_translate_missing(rows, {}, quiet=True, client=fake)

    assert written == {mt._hash8("Hello, world."): "你好，世界。"}
    assert stats["translated"] == 1
    assert stats["failed"] == 0


def test_repository_has_sanitized_env_example() -> None:
    example = PROJECT_ROOT / ".env.example"
    assert example.is_file()
    text = example.read_text(encoding="utf-8")
    assert "MATRIX_LLM_BASE_URL=" in text
    assert "MATRIX_LLM_API_KEY=" in text
    assert "MATRIX_LLM_MODEL=" in text


def test_non_linguistic_fragment_is_not_treated_as_translation_missing() -> None:
    from src import matrix_tool as mt

    assert mt.is_translatable_text("5:") is False
    assert mt.is_translatable_text("Hello, world.") is True
