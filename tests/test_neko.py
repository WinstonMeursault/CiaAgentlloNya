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


class TestSystemPromptAssembly:
    """拆分后：系统 prompt 按固定顺序组装，占位符被正确替换。"""

    def test_sections_assembled_in_order(self, tmp_path: Path):
        neko = Neko(_DummyHistory(), configPath=_make_config(tmp_path))
        system = neko._generateSystemPrompt("g1:u1", historyLimit=7)
        markers = [
            "【身份锚定", "【人格矩阵", "【语言协议",
            "【行为协议", "【人设防火墙", "【记忆与连续性",
        ]
        positions = [system.index(marker) for marker in markers]
        assert positions == sorted(positions)
        assert "【输出质量检查清单" in system
        assert "【背景信息】" in system

    def test_placeholders_replaced(self, tmp_path: Path):
        neko = Neko(_DummyHistory(), configPath=_make_config(tmp_path))
        system = neko._generateSystemPrompt("g1:u1", historyLimit=7)
        assert "{chatHistory}" not in system
        assert "{time}" not in system

    def test_warm_is_default_mode(self, tmp_path: Path):
        neko = Neko(_DummyHistory(), configPath=_make_config(tmp_path))
        system = neko._generateSystemPrompt("g1:u1", historyLimit=7)
        assert "热情模式" in system
        assert "高冷模式" not in system

    def test_cold_mode_uses_cold_sections(self, tmp_path: Path):
        neko = Neko(_DummyHistory(), configPath=_make_config(tmp_path))
        system = neko._generateSystemPrompt("g1:u1", historyLimit=7, mode="cold")
        assert "高冷模式" in system
        assert "热情模式" not in system

    def test_user_prompt_follows_mode(self, tmp_path: Path):
        neko = Neko(_DummyHistory(), configPath=_make_config(tmp_path))
        assert "主人说" in neko._generateUserPrompt("x", mode="warm")
        assert "对方说" in neko._generateUserPrompt("x", mode="cold")


class TestBackgroundInjection:
    """拆分后：{knowledge}/{searchResults} 占位符被背景信息正确替换。"""

    def test_blocks_injected_with_labels(self, tmp_path: Path):
        neko = Neko(_DummyHistory(), configPath=_make_config(tmp_path))
        system = neko._generateSystemPrompt(
            "g1:u1", historyLimit=7, searchResults="SEARCHBLOCK", knowledge="KNOWBLOCK"
        )
        assert "知识库检索结果" in system
        assert "KNOWBLOCK" in system
        assert "联网搜索结果" in system
        assert "SEARCHBLOCK" in system

    def test_empty_blocks_omitted(self, tmp_path: Path):
        neko = Neko(_DummyHistory(), configPath=_make_config(tmp_path))
        system = neko._generateSystemPrompt("g1:u1", historyLimit=7)
        # 占位符必须被替换掉（即使为空），不能残留字面 token
        assert "{knowledge}" not in system
        assert "{searchResults}" not in system

    def test_payload_forwards_blocks(self, tmp_path: Path):
        neko = Neko(_DummyHistory(), configPath=_make_config(tmp_path))
        payload = neko._buildDeepSeekPayload(
            "u", "x", historyLimit=5, stream=False, searchResults="SR", knowledge="KB"
        )
        system = payload["messages"][0]["content"]
        assert "SR" in system
        assert "KB" in system
