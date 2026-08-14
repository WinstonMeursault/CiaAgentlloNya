"""Unit tests for the DeepSeek (chat/completions) backend of core.neko.Neko."""

from pathlib import Path

import pytest

from core.neko import Neko


def _make_config(tmp_path: Path, provider: str = "DeepSeek") -> str:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "llm:\n"
        f"  api_provider: {provider}\n"
        "  base_url: https://api.deepseek.com\n"
        "  api_key: sk-test\n"
        "  model: deepseek-v4-flash\n"
        "  max_tokens: 512\n"
        "  timeout_seconds: 30\n"
        "  language: CN\n",
        encoding="utf-8",
    )
    return str(cfg)


class _DummyHistory:
    """Minimal stand-in for ChatHistory; records retrieval limits."""

    def __init__(self) -> None:
        self.calls = []

    def getRecentMessages(self, username: str, limit: int):
        self.calls.append((username, limit))
        return []


class TestParseChatCompletions:
    def test_extracts_and_strips_content(self):
        resp = {"choices": [{"message": {"content": " 喵~主人好 "}}]}
        assert Neko._parseChatCompletions(resp) == "喵~主人好"

    def test_ignores_reasoning_content(self):
        resp = {"choices": [{"message": {"content": "回答", "reasoning_content": "思考"}}]}
        assert Neko._parseChatCompletions(resp) == "回答"

    def test_missing_content_returns_empty(self):
        assert Neko._parseChatCompletions({"choices": []}) == ""
        assert Neko._parseChatCompletions({}) == ""


class TestParseChatCompletionsStream:
    def test_yields_delta(self):
        line = 'data: {"choices":[{"delta":{"content":"喵"}}]}'
        assert Neko._parseChatCompletionsStream(line) == "喵"

    def test_done_returns_none(self):
        assert Neko._parseChatCompletionsStream("data: [DONE]") is None

    def test_non_data_line_returns_none(self):
        assert Neko._parseChatCompletionsStream(": keep-alive") is None

    def test_invalid_json_returns_none(self):
        assert Neko._parseChatCompletionsStream("data: not-json") is None

    def test_reasoning_only_returns_none(self):
        line = 'data: {"choices":[{"delta":{"reasoning_content":"思考"}}]}'
        assert Neko._parseChatCompletionsStream(line) is None


class TestDeepSeekPayload:
    def test_builds_system_and_user_messages(self, tmp_path: Path):
        history = _DummyHistory()
        neko = Neko(history, configPath=_make_config(tmp_path))
        payload = neko._buildDeepSeekPayload("g1:u1", "你好", historyLimit=7, stream=False)

        assert payload["stream"] is False
        assert payload["model"] == "deepseek-v4-flash"
        assert payload["max_tokens"] == 512
        assert [m["role"] for m in payload["messages"]] == ["system", "user"]
        assert payload["messages"][1]["content"].endswith("你好")

    def test_history_limit_passed_to_history(self, tmp_path: Path):
        history = _DummyHistory()
        neko = Neko(history, configPath=_make_config(tmp_path))
        neko._buildDeepSeekPayload("g1:u1", "你好", historyLimit=42, stream=True)
        assert history.calls == [("g1:u1", 42)]

    def test_stream_flag(self, tmp_path: Path):
        neko = Neko(_DummyHistory(), configPath=_make_config(tmp_path))
        payload = neko._buildDeepSeekPayload("u", "x", historyLimit=10, stream=True)
        assert payload["stream"] is True

class TestExtraContext:
    def test_extra_context_appended_after_history(self, tmp_path: Path):
        neko = Neko(_DummyHistory(), configPath=_make_config(tmp_path))
        payload = neko._buildDeepSeekPayload(
            "g1:u1", "你好", historyLimit=7, stream=False, extraContext="GROUP_CONTEXT_MARKER",
        )
        system = payload["messages"][0]["content"]
        assert "[]\n\nGROUP_CONTEXT_MARKER" in system

    def test_no_extra_context_omits_marker(self, tmp_path: Path):
        neko = Neko(_DummyHistory(), configPath=_make_config(tmp_path))
        payload = neko._buildDeepSeekPayload("g1:u1", "你好", historyLimit=7, stream=False)
        system = payload["messages"][0]["content"]
        assert "GROUP_CONTEXT_MARKER" not in system
