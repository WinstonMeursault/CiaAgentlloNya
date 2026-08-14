"""群内 @离岛酱 触发「月羽雪乃」nekomimi 问答插件。

LLM 后端已统一到共享 ``core.neko.Neko``（DeepSeek chat/completions +
SQLite 持久上下文），与 Telegram 共用同一套人设与后端。
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from ncatbot.core import registrar
from ncatbot.event.qq import GroupMessageEvent
from ncatbot.plugin import NcatBotPlugin
from ncatbot.utils import get_config_manager, get_log

LOG = get_log("AiChatPlugin")

# 定位共享 core 包：依次尝试「打包进插件目录」「仓库根 / 容器根」两种布局。
_PLUGIN_DIR = Path(__file__).resolve().parent
for _candidate in (_PLUGIN_DIR, _PLUGIN_DIR.parent.parent):
    if (_candidate / "core" / "__init__.py").exists():
        if str(_candidate) not in sys.path:
            sys.path.insert(0, str(_candidate))
        break
else:
    raise ImportError(
        "无法定位 core 包：请将 core/ 置于插件目录或容器根目录（见 qq/OPERATIONS.md）"
    )

from core.neko import Neko  # noqa: E402
from core.chatHistory import ChatHistory  # noqa: E402


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
    parts: List[str] = []
    for seg_type, payload in _iter_segments(message):
        if seg_type != "text":
            continue
        if isinstance(payload, dict):
            parts.append(str(payload.get("text", "")))
        else:
            parts.append(str(getattr(payload, "text", "")))
    return "".join(parts).strip()


def extract_prompt_from_event(message, bot_uin: str) -> Optional[str]:
    """判断消息是否 @ 了机器人；是则返回 @ 之外的完整文本作为 prompt。

    兼容两种消息段形态：OneBot dict（{"type", "data"}）与框架消息段对象
    （PlainText / At / Image ...），不依赖具体类名，便于后续扩展。
    """
    at_bot = False
    parts: List[str] = []
    for seg_type, payload in _iter_segments(message):
        if seg_type == "at":
            if isinstance(payload, dict):
                qq = str(payload.get("qq", payload.get("user_id", ""))).strip()
            else:
                qq = str(
                    getattr(payload, "user_id", "") or getattr(payload, "qq", "")
                ).strip()
            if qq == str(bot_uin).strip():
                at_bot = True
        elif seg_type == "text":
            if isinstance(payload, dict):
                parts.append(str(payload.get("text", "")))
            else:
                parts.append(str(getattr(payload, "text", "")))
    if not at_bot:
        return None
    prompt = "".join(parts).strip()
    return prompt or None


def extract_reply_id(message) -> Optional[str]:
    """返回消息中「引用回复」段引用的消息 id；没有引用则返回 None。

    兼容 dict 与对象两种消息段形态。
    """
    for seg_type, payload in _iter_segments(message):
        if seg_type != "reply":
            continue
        if isinstance(payload, dict):
            return str(payload.get("id", payload.get("message_id", ""))).strip() or None
        return str(getattr(payload, "id", "") or getattr(payload, "message_id", "")).strip() or None
    return None


def format_quoted_context(sender: str, content: str) -> str:
    """把被引用消息格式化为一行可拼进 prompt 的提示文本。"""
    return f"（引用回复 {sender}：{content}）"


class AiChatPlugin(NcatBotPlugin):
    name = "ai_chat"
    version = "0.4.0"
    author = "Meursault"
    description = "群内 @离岛酱 触发月羽雪乃问答（共享 core/DeepSeek 后端，带每日限额、持久上下文、群聊上下文与引用回复感知）"

    async def on_load(self):
        self._bot_uin = str(get_config_manager().config.bot_uin)
        self._admin_uins: set[str] = {
            str(uin) for uin in self.get_config("admin_uins", [])
        }
        self._prompts = self._load_extra_yaml("prompts.yaml")
        self._messages = self._load_extra_yaml("messages.yaml")

        rate_limit = self.get_config("rate_limit", {}) or {}
        self._daily_limit = max(1, int(rate_limit.get("daily_limit", 10)))
        self._timezone = timezone(timedelta(hours=int(rate_limit.get("utc_offset_hours", 8))))

        context = self.get_config("context", {}) or {}
        self._history_limit_normal = max(1, int(context.get("history_limit_normal", 10)))
        self._history_limit_admin = max(1, int(context.get("history_limit_admin", 50)))
        self._group_context_limit = max(0, int(context.get("group_context_limit", 50)))
        self._reply_context_enabled = bool(context.get("reply_context_enabled", True))

        # 共享后端：SQLite 历史 + DeepSeek/月羽雪乃 人设（core）
        self._chat_history = ChatHistory(dbPath=self._resolve_db_path())
        self._neko = Neko(self._chat_history)

        LOG.info(
            "%s 已加载 (bot_uin=%s, admins=%s, 每日限额=%d, 上下文:普通%d/高权限%d, 群聊上下文=%d)",
            self.name,
            self._bot_uin,
            sorted(self._admin_uins),
            self._daily_limit,
            self._history_limit_normal,
            self._history_limit_admin,
            self._group_context_limit,
        )

    # ------------------------------------------------------------------
    # 配置 / 工具
    # ------------------------------------------------------------------

    def _load_extra_yaml(self, filename: str) -> dict:
        path = Path(__file__).resolve().parent / filename
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            LOG.exception("%s: 加载 %s 失败", self.name, filename)
            return {}

    def _resolve_db_path(self) -> str:
        """返回 SQLite 历史库路径；未配置时落到容器 data 目录（已挂载持久化）。"""
        cfg = self.get_config("chat_history", {}) or {}
        configured = str(cfg.get("db_path", "") or "").strip()
        if configured:
            return configured
        return str(_PLUGIN_DIR.parent.parent / "data" / "ai_chat" / "chatHistory.db")

    @staticmethod
    def _today_str(tz) -> str:
        return datetime.now(tz).strftime("%Y-%m-%d")

    def _consume_quota(self, uin: str) -> bool:
        """高权限用户不限次；普通用户按天计数，超出返回 False。"""
        if uin in self._admin_uins:
            return True
        today = self._today_str(self._timezone)
        daily = self.data.setdefault("daily", {})
        for old_day in [k for k in daily.keys() if k != today]:
            del daily[old_day]
        day_map = daily.setdefault(today, {})
        used = int(day_map.get(uin, 0))
        if used >= self._daily_limit:
            return False
        day_map[uin] = used + 1
        self._save_data()
        return True

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    async def _resolve_reply_context(self, event, reply_id: str) -> str:
        """拉取被引用消息，格式化为可拼进 prompt 的上下文；失败返回空串。

        Args:
            event: 群消息事件（用于调用 event.api.query.get_msg）。
            reply_id: 被引用消息的 id。

        Returns:
            形如「（引用回复 某某：内容）」的文本；拉取失败或无有效内容时返回空串。
        """
        try:
            data = await event.api.query.get_msg(reply_id)
        except Exception:
            LOG.exception("%s: 拉取被引用消息失败，已忽略", self.name)
            return ""
        if data is None:
            return ""

        sender = getattr(data, "sender", None)
        if sender is None:
            sender_name = "未知用户"
        else:
            sender_name = (
                getattr(sender, "card", None)
                or getattr(sender, "nickname", None)
                or getattr(sender, "user_id", None)
                or "未知用户"
            )

        content = extract_text_from_event(getattr(data, "message", None) or [])
        if not content:
            content = "[非文本消息]"
        return format_quoted_context(str(sender_name), content)

    def _record_group_message(self, group_id: str, uin: str, role: str, message: str) -> None:
        """把一条消息写入群聊上下文（非致命：失败仅记日志，不阻断回复）。"""
        try:
            self._chat_history.addGroupMessage(group_id, uin, role, message)
        except Exception:
            LOG.exception("%s: 群聊上下文写入失败，已忽略", self.name)

    def _format_group_context(self, group_id: str, user_key: str, history_limit: int) -> str:
        """把「不在该用户对话记录里的」群聊上下文格式化为可拼进 prompt 的文本。

        Args:
            group_id: 群号。
            user_key: 当前用户的上下文键（{群}:{用户}），用于去重。
            history_limit: 该用户注入的上下文条数，去重范围与其保持一致。

        Returns:
            拼好的群聊上下文文本；无内容或已关闭时返回空字符串。
        """
        if self._group_context_limit <= 0:
            return ""
        records = self._chat_history.getRecentGroupMessages(
            group_id, self._group_context_limit
        )
        if not records:
            return ""
        seen = {
            (row["role"], row["message"])
            for row in self._chat_history.getRecentMessages(user_key, history_limit)
        }
        filtered = [
            row for row in records if (row["role"], row["message"]) not in seen
        ]
        if not filtered:
            return ""
        header = self._prompts.get(
            "group_context_header", "## 群聊上下文（群友最近的聊天，仅作背景参考）"
        )
        lines = [header]
        for row in filtered:
            speaker = "机器人" if row["role"] == "bot" else row["user_id"]
            lines.append(f"- {speaker}: {row['message']}")
        return "\n".join(lines)

    @registrar.qq.on_group_message()
    async def on_group_message(self, event: GroupMessageEvent):
        group_id = str(event.group_id)
        uin = str(event.user_id)

        try:
            text = extract_text_from_event(event.message)
            prompt = extract_prompt_from_event(event.message, self._bot_uin)
            reply_id = extract_reply_id(event.message)
        except Exception:
            LOG.exception("%s: 消息解析失败，已跳过", self.name)
            return

        # 未 @机器人：作为普通群聊记入群聊上下文后直接返回
        if prompt is None:
            recorded = text
            if reply_id and self._reply_context_enabled:
                quoted = await self._resolve_reply_context(event, reply_id)
                if quoted:
                    recorded = (f"{quoted} {text}").strip() if text else quoted
            if recorded:
                self._record_group_message(group_id, uin, "user", recorded)
            return

        if not prompt:
            await event.reply(self._prompts.get("no_prompt", "请先 @我 再输入问题哦～"))
            return

        if not self._consume_quota(uin):
            await event.reply(
                self._messages.get("quota_exceeded", "抱歉，今天的提问次数用完啦，明天再来吧～")
            )
            return

        # 引用回复：把被引用的内容拼进 prompt，让 bot 知道在回复什么
        if reply_id and self._reply_context_enabled:
            quoted = await self._resolve_reply_context(event, reply_id)
            if quoted:
                prompt = f"{quoted}\n{prompt}"

        # 上下文按「群 + 用户」隔离，避免跨群/跨用户串味
        user_key = f"{group_id}:{uin}"
        history_limit = (
            self._history_limit_admin
            if uin in self._admin_uins
            else self._history_limit_normal
        )
        group_context = self._format_group_context(group_id, user_key, history_limit)

        try:
            answer = await self._neko.askNeko(
                user_key, prompt, historyLimit=history_limit, extraContext=group_context
            )
        except Exception:
            LOG.exception("%s: LLM 调用失败", self.name)
            await event.reply(
                self._messages.get("api_error", "呜……我刚刚遇到了一点问题，请稍后再试一次。")
            )
            return

        if not answer:
            await event.reply(
                self._messages.get("api_error", "呜……我刚刚遇到了一点问题，请稍后再试一次。")
            )
            return

        self._chat_history.addMessage(user_key, "user", prompt, chatId=group_id)
        self._chat_history.addMessage(user_key, "bot", answer, chatId=group_id)
        # 本次 @问答与机器人回复一并记入群聊上下文（供后续拼装/去重）
        self._record_group_message(group_id, uin, "user", prompt)
        self._record_group_message(group_id, self._bot_uin, "bot", answer)
        await event.reply(answer)
