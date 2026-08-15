"""群聊复读机插件：连续两条相同文本消息时，机器人立刻复读一次。

自包含插件，不依赖共享 core 包；仅处理群聊消息事件。
"""

from __future__ import annotations

from typing import Dict

from ncatbot.core import registrar
from ncatbot.event.qq import GroupMessageEvent
from ncatbot.plugin import NcatBotPlugin
from ncatbot.utils import get_config_manager, get_log

LOG = get_log("RepeaterPlugin")


def _iter_segments(message):
    """遍历消息段，统一 dict 与对象两种形态，产出 (seg_type, payload)。

    payload 对 dict 形态为 data dict，对对象形态为对象本身。
    """
    if isinstance(message, list):
        segments = message
    elif hasattr(message, "__iter__"):
        segments = list(message)
    else:
        segments = []

    for seg in segments or []:
        if isinstance(seg, dict):
            yield seg.get("type"), (seg.get("data") or {})
        else:
            yield (getattr(seg, "type", None) or getattr(seg, "_type", None)), seg


def extract_text_from_event(message) -> str:
    """拼接消息中的所有纯文本段（忽略 @ / 图片 / 表情等），返回去首尾空白的文本。"""
    parts = []
    for seg_type, payload in _iter_segments(message):
        if seg_type != "text":
            continue
        if isinstance(payload, dict):
            parts.append(str(payload.get("text", "")))
        else:
            parts.append(str(getattr(payload, "text", "")))
    return "".join(parts).strip()


def step_repeat(state: Dict[str, str], text: str) -> bool:
    """复读机状态转移：判断本次是否应复读，并就地更新 state。

    Args:
        state: 形如 {"last": 上一条文本, "repeated": 本段已复读的文本} 的字典。
        text: 当前消息的纯文本（已去首尾空白）。

    Returns:
        是否应立即复读该文本。
    """
    if not text:
        # 非文本消息打断「连续」
        state["last"] = ""
        state["repeated"] = ""
        return False
    if text == state["last"] and text != state["repeated"]:
        # 连续两条相同且本段尚未复读：先标记，保证每段只复读一次
        state["repeated"] = text
        state["last"] = text
        return True
    if text != state["last"]:
        # 内容变化 → 重置本段
        state["repeated"] = ""
    state["last"] = text
    return False


class RepeaterPlugin(NcatBotPlugin):
    name = "repeater"
    version = "0.1.0"
    author = "Meursault"
    description = "群聊复读机：连续两条相同文本消息时复读一次"

    async def on_load(self):
        self._bot_uin = str(get_config_manager().config.bot_uin)
        self._enabled = bool(self.get_config("enabled", True))
        self._state: Dict[str, Dict[str, str]] = {}  # group_id -> state
        LOG.info("%s 已加载 (enabled=%s)", self.name, self._enabled)

    @registrar.qq.on_group_message()
    async def on_group_message(self, event: GroupMessageEvent):
        if not self._enabled:
            return
        group_id = str(event.group_id)
        if str(event.user_id) == self._bot_uin:
            return  # 防御性忽略自身消息（防自回环）
        try:
            text = extract_text_from_event(event.message).strip()
        except Exception:
            LOG.exception("%s: 消息解析失败，已跳过", self.name)
            return

        state = self._state.setdefault(group_id, {"last": "", "repeated": ""})
        if not step_repeat(state, text):
            return
        try:
            await event.api.messaging.send_group_msg(
                group_id=group_id,
                message=[{"type": "text", "data": {"text": text}}],
            )
        except Exception:
            LOG.exception("%s: 复读发送失败 group=%s", self.name, group_id)
