"""Unit tests for the QQ plugin's prompt extraction (no NcatBot runtime needed)."""

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent


def _install_ncatbot_stub() -> None:
    """Provide the minimal ``ncatbot`` surface the plugin imports at module load."""
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
    sys.modules["ncatbot.utils"].get_config_manager = lambda: None
    sys.modules["ncatbot.utils"].get_log = lambda name: None


_install_ncatbot_stub()

_plugin_path = REPO_ROOT / "qq" / "AI Chat" / "plugin.py"
_spec = importlib.util.spec_from_file_location("ai_chat_plugin", _plugin_path)
_plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_plugin)

extract_prompt_from_event = _plugin.extract_prompt_from_event


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
