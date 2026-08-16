"""Unit tests for the QQ plugin's prompt extraction (no NcatBot runtime needed)."""

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

from core.chatHistory import ChatHistory

REPO_ROOT = Path(__file__).resolve().parent.parent


def _install_ncatbot_stub() -> None:
    """Provide the minimal ``ncatbot`` surface the plugin imports at module load."""
    registrar = SimpleNamespace()
    registrar.qq = SimpleNamespace()
    registrar.qq.on_group_message = lambda *a, **k: (lambda f: f)
    registrar.qq.on_private_message = lambda *a, **k: (lambda f: f)

    for name in (
        "ncatbot",
        "ncatbot.core",
        "ncatbot.event",
        "ncatbot.event.qq",
        "ncatbot.plugin",
        "ncatbot.utils",
    ):
        sys.modules[name] = types.ModuleType(name)

    sys.modules["ncatbot.core"].registrar = registrar
    sys.modules["ncatbot.event.qq"].GroupMessageEvent = object
    sys.modules["ncatbot.event.qq"].PrivateMessageEvent = object
    sys.modules["ncatbot.plugin"].NcatBotPlugin = object
    sys.modules["ncatbot.utils"].get_config_manager = lambda: None

    def _fake_logger(name):
        log = SimpleNamespace()
        for level in ("debug", "info", "warning", "error", "exception", "critical"):
            setattr(log, level, lambda *a, **k: None)
        return log

    sys.modules["ncatbot.utils"].get_log = _fake_logger


_install_ncatbot_stub()

_plugin_path = REPO_ROOT / "qq" / "AI Chat" / "plugin.py"
_spec = importlib.util.spec_from_file_location("ai_chat_plugin", _plugin_path)
_plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_plugin)

extract_prompt_from_event = _plugin.extract_prompt_from_event
extract_text_from_event = _plugin.extract_text_from_event
extract_reply_id = _plugin.extract_reply_id
format_quoted_context = _plugin.format_quoted_context
summarize_message = _plugin.summarize_message
extract_sender_name = _plugin.extract_sender_name
split_on_blank_lines = _plugin.split_on_blank_lines


def _obj(seg_type: str, **kwargs):
    seg = SimpleNamespace(**kwargs)
    seg.type = seg_type
    return seg


class TestExtractPromptFromEvent:
    def test_dict_segments(self):
        message = [
            {"type": "at", "data": {"qq": "123"}},
            {"type": "text", "data": {"text": " 你好呀 "}},
        ]
        assert extract_prompt_from_event(message, "123") == "你好呀"

    def test_object_segments(self):
        message = [
            _obj("at", user_id="123"),
            _obj("text", text="喵"),
        ]
        assert extract_prompt_from_event(message, "123") == "喵"

    def test_no_at_returns_none(self):
        assert extract_prompt_from_event([_obj("text", text="你好")], "123") is None

    def test_at_other_bot_returns_none(self):
        message = [
            {"type": "at", "data": {"qq": "999"}},
            {"type": "text", "data": {"text": "x"}},
        ]
        assert extract_prompt_from_event(message, "123") is None

    def test_at_only_returns_none(self):
        assert extract_prompt_from_event([{"type": "at", "data": {"qq": "123"}}], "123") is None

class TestExtractTextFromEvent:
    def test_dict_segments(self):
        message = [
            {"type": "text", "data": {"text": " 你好 "}},
            {"type": "text", "data": {"text": "世界"}},
        ]
        assert extract_text_from_event(message) == "你好 世界"

    def test_object_segments(self):
        message = [_obj("text", text="喵"), _obj("image", url="x")]
        assert extract_text_from_event(message) == "喵"

    def test_ignores_at_and_other_segments(self):
        message = [
            {"type": "at", "data": {"qq": "123"}},
            {"type": "text", "data": {"text": "hi"}},
            {"type": "image", "data": {"url": "x"}},
        ]
        assert extract_text_from_event(message) == "hi"

    def test_empty_when_no_text(self):
        assert extract_text_from_event([_obj("image", url="x")]) == ""


class TestFormatGroupContext:
    def _make_plugin(self, tmp_path, group_context_limit=50):
        plugin = _plugin.AiChatPlugin()
        plugin._chat_history = ChatHistory(dbPath=str(tmp_path / "chatHistory.db"))
        plugin._prompts = {}
        plugin._group_context_limit = group_context_limit
        plugin._bot_uin = "123"
        return plugin

    def test_dedup_removes_current_user_dialogue(self, tmp_path):
        plugin = self._make_plugin(tmp_path)
        h = plugin._chat_history
        # 当前用户 g1:1001 的 @问答（用户上下文）
        h.addMessage("g1:1001", "user", "我的问题", chatId="g1")
        h.addMessage("g1:1001", "bot", "我的回答", chatId="g1")
        # 群流：当前用户 @问答 + 他人消息 + 机器人给别人的回复
        h.addGroupMessage("g1", "1001", "user", "我的问题")
        h.addGroupMessage("g1", "123", "bot", "我的回答")
        h.addGroupMessage("g1", "1002", "user", "其他人说的")
        h.addGroupMessage("g1", "123", "bot", "给别人的回复")

        ctx = plugin._format_group_context("g1", "1001", 50)

        assert "其他人说的" in ctx
        assert "给别人的回复" in ctx
        assert "我的问题" not in ctx
        assert "我的回答" not in ctx
        assert "群聊上下文" in ctx

    def test_limit_zero_disabled(self, tmp_path):
        plugin = self._make_plugin(tmp_path, group_context_limit=0)
        plugin._chat_history.addGroupMessage("g1", "1002", "user", "x")
        assert plugin._format_group_context("g1", "1001", 50) == ""

    def test_empty_group_returns_empty(self, tmp_path):
        plugin = self._make_plugin(tmp_path)
        assert plugin._format_group_context("g1", "1001", 50) == ""
    def test_dedup_keeps_other_users_identical_text(self, tmp_path):
        plugin = self._make_plugin(tmp_path)
        h = plugin._chat_history
        h.addMessage("g1:1001", "user", "哈哈", chatId="g1")
        h.addGroupMessage("g1", "1001", "user", "哈哈")
        h.addGroupMessage("g1", "1002", "user", "哈哈")

        ctx = plugin._format_group_context("g1", "1001", 50)
        assert ctx.count("哈哈") == 1
        assert "1002" in ctx

    def test_dedup_keeps_bot_reply_to_others(self, tmp_path):
        plugin = self._make_plugin(tmp_path)
        h = plugin._chat_history
        h.addMessage("g1:1001", "bot", "我的回答", chatId="g1")
        h.addGroupMessage("g1", "123", "bot", "我的回答")
        h.addGroupMessage("g1", "123", "bot", "给别人的")

        ctx = plugin._format_group_context("g1", "1001", 50)
        assert "给别人的" in ctx
        assert "我的回答" not in ctx

    def test_nickname_display(self, tmp_path):
        plugin = self._make_plugin(tmp_path)
        h = plugin._chat_history
        h.addGroupMessage("g1", "1002", "user", "hi", nickname="江星繁")

        ctx = plugin._format_group_context("g1", "1001", 50)
        assert "江星繁(UID:1002): hi" in ctx

    def test_bot_labeled_as_persona(self, tmp_path):
        plugin = self._make_plugin(tmp_path)
        h = plugin._chat_history
        h.addGroupMessage("g1", "123", "bot", "你好喵")

        ctx = plugin._format_group_context("g1", "1001", 50)
        assert "月羽雪乃: 你好喵" in ctx
        assert "机器人" not in ctx

    def test_user_without_nickname_uses_uid(self, tmp_path):
        plugin = self._make_plugin(tmp_path)
        h = plugin._chat_history
        h.addGroupMessage("g1", "1002", "user", "hi")

        ctx = plugin._format_group_context("g1", "1001", 50)
        assert "用户(UID:1002): hi" in ctx

class TestExtractReplyId:
    def test_dict_reply(self):
        message = [
            {"type": "reply", "data": {"id": "576210509"}},
            {"type": "text", "data": {"text": "那肯定不会了"}},
        ]
        assert extract_reply_id(message) == "576210509"

    def test_object_reply(self):
        message = [_obj("reply", id="576210509"), _obj("text", text="x")]
        assert extract_reply_id(message) == "576210509"

    def test_message_id_fallback_dict(self):
        message = [{"type": "reply", "data": {"message_id": "123"}}]
        assert extract_reply_id(message) == "123"

    def test_no_reply_returns_none(self):
        assert extract_reply_id([_obj("text", text="hi")]) is None
        assert extract_reply_id([{"type": "at", "data": {"qq": "1"}}]) is None


class TestFormatQuotedContext:
    def test_basic(self):
        assert format_quoted_context("江星繁", "我想看看他会不会给我") == "（引用回复 江星繁：我想看看他会不会给我）"

    def test_content_with_braces_is_untouched(self):
        assert format_quoted_context("A", "看这个 {1,2}") == "（引用回复 A：看这个 {1,2}）"


class TestResolveReplyContext:
    def _make_plugin(self):
        return _plugin.AiChatPlugin()

    def _make_event(self, msg_data):
        async def get_msg(reply_id):
            return msg_data

        return SimpleNamespace(api=SimpleNamespace(query=SimpleNamespace(get_msg=get_msg)))

    def test_uses_card_when_present(self):
        plugin = self._make_plugin()
        data = SimpleNamespace(
            sender=SimpleNamespace(user_id="2727400364", nickname="江星繁", card="江繁繁", role="member"),
            message=[{"type": "text", "data": {"text": "hello"}}],
        )
        out = asyncio.run(plugin._resolve_reply_context(self._make_event(data), "1"))
        assert "江繁繁" in out
        assert "hello" in out

    def test_falls_back_to_nickname(self):
        plugin = self._make_plugin()
        data = SimpleNamespace(
            sender=SimpleNamespace(user_id="2727400364", nickname="江星繁", card="", role="member"),
            message=[{"type": "text", "data": {"text": "我想看看他会不会给我"}}],
        )
        out = asyncio.run(plugin._resolve_reply_context(self._make_event(data), "576210509"))
        assert "江星繁" in out

    def test_non_text_message_falls_back(self):
        plugin = self._make_plugin()
        data = SimpleNamespace(
            sender=SimpleNamespace(user_id="1", nickname="B", card="", role="member"),
            message=[{"type": "image", "data": {"url": "x"}}],
        )
        out = asyncio.run(plugin._resolve_reply_context(self._make_event(data), "1"))
        assert "[非文本消息]" in out

    def test_sender_none_uses_unknown(self):
        plugin = self._make_plugin()
        data = SimpleNamespace(sender=None, message=[{"type": "text", "data": {"text": "hi"}}])
        out = asyncio.run(plugin._resolve_reply_context(self._make_event(data), "1"))
        assert "未知用户" in out

    def test_get_msg_raises_returns_empty(self):
        plugin = self._make_plugin()

        async def boom(reply_id):
            raise RuntimeError("boom")

        event = SimpleNamespace(api=SimpleNamespace(query=SimpleNamespace(get_msg=boom)))
        out = asyncio.run(plugin._resolve_reply_context(event, "1"))
        assert out == ""

class TestSummarizeMessage:
    def test_text(self):
        assert summarize_message([{"type": "text", "data": {"text": "你好"}}]) == "你好"

    def test_image_placeholder(self):
        assert summarize_message([_obj("image", url="x")]) == "[图片]"

    def test_record_placeholder(self):
        assert summarize_message([{"type": "record", "data": {"url": "x"}}]) == "[语音]"

    def test_face_placeholder(self):
        assert summarize_message([_obj("face", id="1")]) == "[表情]"

    def test_empty_at_only(self):
        assert summarize_message([_obj("at", user_id="123")]) == ""

    def test_unknown_non_text(self):
        assert summarize_message([_obj("video", url="x")]) == "[非文本消息]"


class TestExtractSenderName:
    def test_card_priority(self):
        sender = SimpleNamespace(card="江繁繁", nickname="江星繁", user_id="2727400364")
        assert extract_sender_name(sender) == "江繁繁"

    def test_nickname_fallback(self):
        sender = SimpleNamespace(card="", nickname="江星繁", user_id="2727400364")
        assert extract_sender_name(sender) == "江星繁"

    def test_user_id_fallback(self):
        sender = SimpleNamespace(card=None, nickname=None, user_id="2727400364")
        assert extract_sender_name(sender) == "2727400364"

    def test_none(self):
        assert extract_sender_name(None) is None


class TestSplitOnBlankLines:
    def test_single_newline_kept(self):
        assert split_on_blank_lines("A\nB") == ["A\nB"]

    def test_blank_line_splits(self):
        assert split_on_blank_lines("A\n\nB") == ["A", "B"]

    def test_multiple_blank_lines_collapse(self):
        assert split_on_blank_lines("A\n\n\nB") == ["A", "B"]

    def test_strips_whitespace(self):
        assert split_on_blank_lines("  A  \n\n  B  ") == ["A", "B"]

    def test_windows_line_endings(self):
        assert split_on_blank_lines("A\r\n\r\nB") == ["A", "B"]

    def test_empty_text(self):
        assert split_on_blank_lines("") == []

    def test_trailing_blank_lines_ignored(self):
        assert split_on_blank_lines("A\n\n") == ["A"]
