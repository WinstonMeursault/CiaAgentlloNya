"""Unit tests for the QQ repeater plugin (no NcatBot runtime needed)."""

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent


def _install_ncatbot_stub() -> None:
    """Provide the minimal ncatbot surface the plugin imports at module load."""
    registrar = SimpleNamespace()
    registrar.qq = SimpleNamespace()
    registrar.qq.on_group_message = lambda *a, **k: (lambda f: f)

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
    sys.modules["ncatbot.plugin"].NcatBotPlugin = object

    config_manager = SimpleNamespace(config=SimpleNamespace(bot_uin="123456"))
    sys.modules["ncatbot.utils"].get_config_manager = lambda: config_manager

    def _fake_logger(name):
        log = SimpleNamespace()
        for level in ("debug", "info", "warning", "error", "exception", "critical"):
            setattr(log, level, lambda *a, **k: None)
        return log

    sys.modules["ncatbot.utils"].get_log = _fake_logger


_install_ncatbot_stub()

_plugin_path = REPO_ROOT / "qq" / "Repeater" / "plugin.py"
_spec = importlib.util.spec_from_file_location("repeater_plugin", _plugin_path)
_plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_plugin)

extract_text_from_event = _plugin.extract_text_from_event
step_repeat = _plugin.step_repeat


def _obj(seg_type: str, **kwargs):
    seg = SimpleNamespace(**kwargs)
    seg.type = seg_type
    return seg


class TestStepRepeat:
    def _state(self):
        return {"last": "", "repeated": ""}

    def test_first_message_no_repeat(self):
        state = self._state()
        assert step_repeat(state, "哈哈") is False
        assert state == {"last": "哈哈", "repeated": ""}

    def test_two_identical_repeat(self):
        state = {"last": "哈哈", "repeated": ""}
        assert step_repeat(state, "哈哈") is True
        assert state == {"last": "哈哈", "repeated": "哈哈"}

    def test_third_identical_no_repeat(self):
        state = {"last": "哈哈", "repeated": "哈哈"}
        assert step_repeat(state, "哈哈") is False
        assert state == {"last": "哈哈", "repeated": "哈哈"}

    def test_different_resets_run(self):
        state = {"last": "哈哈", "repeated": "哈哈"}
        assert step_repeat(state, "喵") is False
        assert state == {"last": "喵", "repeated": ""}

    def test_repeat_again_after_change(self):
        state = {"last": "喵", "repeated": ""}
        assert step_repeat(state, "喵") is True
        assert state == {"last": "喵", "repeated": "喵"}

    def test_empty_text_resets(self):
        state = {"last": "哈哈", "repeated": "哈哈"}
        assert step_repeat(state, "") is False
        assert state == {"last": "", "repeated": ""}

    def test_same_user_twice_counts(self):
        # 同一人连发两条相同内容也算复读（用户确认的行为）
        state = {"last": "哈哈", "repeated": ""}
        assert step_repeat(state, "哈哈") is True


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

    def test_ignores_at_and_other(self):
        message = [
            {"type": "at", "data": {"qq": "123"}},
            {"type": "text", "data": {"text": "hi"}},
            {"type": "image", "data": {"url": "x"}},
        ]
        assert extract_text_from_event(message) == "hi"

    def test_empty_when_no_text(self):
        assert extract_text_from_event([_obj("image", url="x")]) == ""


class TestOnGroupMessage:
    def _make_plugin(self):
        plugin = _plugin.RepeaterPlugin()
        plugin._bot_uin = "123456"
        plugin._enabled = True
        plugin._state = {}
        return plugin

    def _make_event(self, group_id, user_id, message, sent):
        async def send_group_msg(group_id=None, message=None, **kwargs):
            sent.append({"group_id": str(group_id), "text": message[0]["data"]["text"]})

        return SimpleNamespace(
            group_id=group_id,
            user_id=user_id,
            message=message,
            api=SimpleNamespace(messaging=SimpleNamespace(send_group_msg=send_group_msg)),
        )

    def test_two_identical_sends_once(self):
        plugin = self._make_plugin()
        sent = []
        text = [{"type": "text", "data": {"text": "哈哈"}}]
        asyncio.run(plugin.on_group_message(self._make_event("g1", "1", text, sent)))
        asyncio.run(plugin.on_group_message(self._make_event("g1", "2", text, sent)))
        assert sent == [{"group_id": "g1", "text": "哈哈"}]

    def test_three_identical_sends_once(self):
        plugin = self._make_plugin()
        sent = []
        text = [{"type": "text", "data": {"text": "哈哈"}}]
        asyncio.run(plugin.on_group_message(self._make_event("g1", "1", text, sent)))
        asyncio.run(plugin.on_group_message(self._make_event("g1", "2", text, sent)))
        asyncio.run(plugin.on_group_message(self._make_event("g1", "3", text, sent)))
        assert len(sent) == 1

    def test_change_then_repeat_again(self):
        plugin = self._make_plugin()
        sent = []
        a = [{"type": "text", "data": {"text": "哈哈"}}]
        b = [{"type": "text", "data": {"text": "喵"}}]
        asyncio.run(plugin.on_group_message(self._make_event("g1", "1", a, sent)))
        asyncio.run(plugin.on_group_message(self._make_event("g1", "2", a, sent)))
        asyncio.run(plugin.on_group_message(self._make_event("g1", "3", b, sent)))
        asyncio.run(plugin.on_group_message(self._make_event("g1", "4", b, sent)))
        assert sent == [{"group_id": "g1", "text": "哈哈"}, {"group_id": "g1", "text": "喵"}]

    def test_same_user_twice(self):
        plugin = self._make_plugin()
        sent = []
        text = [{"type": "text", "data": {"text": "哈哈"}}]
        asyncio.run(plugin.on_group_message(self._make_event("g1", "1", text, sent)))
        asyncio.run(plugin.on_group_message(self._make_event("g1", "1", text, sent)))
        assert sent == [{"group_id": "g1", "text": "哈哈"}]

    def test_disabled(self):
        plugin = self._make_plugin()
        plugin._enabled = False
        sent = []
        text = [{"type": "text", "data": {"text": "哈哈"}}]
        asyncio.run(plugin.on_group_message(self._make_event("g1", "1", text, sent)))
        asyncio.run(plugin.on_group_message(self._make_event("g1", "2", text, sent)))
        assert sent == []

    def test_bot_self_ignored(self):
        plugin = self._make_plugin()
        sent = []
        text = [{"type": "text", "data": {"text": "哈哈"}}]
        asyncio.run(plugin.on_group_message(self._make_event("g1", "1", text, sent)))
        asyncio.run(plugin.on_group_message(self._make_event("g1", "123456", text, sent)))
        assert sent == []

    def test_non_text_resets(self):
        plugin = self._make_plugin()
        sent = []
        a = [{"type": "text", "data": {"text": "哈哈"}}]
        img = [{"type": "image", "data": {"url": "x"}}]
        asyncio.run(plugin.on_group_message(self._make_event("g1", "1", a, sent)))
        asyncio.run(plugin.on_group_message(self._make_event("g1", "2", img, sent)))
        asyncio.run(plugin.on_group_message(self._make_event("g1", "3", a, sent)))
        assert sent == []

    def test_per_group_isolation(self):
        plugin = self._make_plugin()
        sent = []
        text = [{"type": "text", "data": {"text": "哈哈"}}]
        asyncio.run(plugin.on_group_message(self._make_event("g1", "1", text, sent)))
        asyncio.run(plugin.on_group_message(self._make_event("g2", "1", text, sent)))
        assert sent == []
