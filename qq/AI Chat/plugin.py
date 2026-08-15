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
from ncatbot.event.qq import GroupMessageEvent, PrivateMessageEvent
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

from core.neko import Neko, PROMPT_MODE_WARM, PROMPT_MODE_COLD  # noqa: E402
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


def summarize_message(message) -> str:
    """返回消息文本；无文本时用非文本段占位，全空则返回空串。"""
    text = extract_text_from_event(message)
    if text:
        return text
    for seg_type, _ in _iter_segments(message):
        if seg_type in ("at", "reply"):
            continue
        if seg_type == "image":
            return "[图片]"
        if seg_type == "record":
            return "[语音]"
        if seg_type in ("face", "marketFace"):
            return "[表情]"
        return "[非文本消息]"
    return ""


def extract_sender_name(sender) -> Optional[str]:
    """从 sender 取显示名：群名片 > 昵称 > QQ号；取不到返回 None。"""
    if sender is None:
        return None
    card = getattr(sender, "card", None)
    if card:
        return str(card)
    nickname = getattr(sender, "nickname", None)
    if nickname:
        return str(nickname)
    user_id = getattr(sender, "user_id", None)
    return str(user_id) if user_id else None


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
        self._max_history_rows = max(0, int(context.get("max_history_rows", 2000)))
        self._max_group_rows = max(0, int(context.get("max_group_rows", 5000)))

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

    def _record_group_message(
        self, group_id: str, uin: str, role: str, message: str, nickname: Optional[str] = None
    ) -> None:
        """把一条消息写入群聊上下文（非致命；关闭群聊上下文时跳过）。"""
        if self._group_context_limit <= 0:
            return
        try:
            self._chat_history.addGroupMessage(group_id, uin, role, message, nickname=nickname)
            if self._max_group_rows > 0:
                self._chat_history.pruneGroupMessages(group_id, self._max_group_rows)
        except Exception:
            LOG.exception("%s: 群聊上下文写入失败，已忽略", self.name)

    def _record_user_message(self, user_key: str, role: str, message: str, chatId: str) -> None:
        """把一条消息写入用户上下文，并按配置清理旧记录。"""
        self._chat_history.addMessage(user_key, role, message, chatId=chatId)
        if self._max_history_rows > 0:
            self._chat_history.pruneMessages(user_key, self._max_history_rows)

    def _format_group_context(self, group_id: str, uin: str, history_limit: int) -> str:
        """把「不在该用户对话记录里的」群聊上下文格式化为可拼进 prompt 的文本。

        Args:
            group_id: 群号。
            uin: 当前用户 QQ，用于精确去重其本人发言。
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
        bot_texts = {
            row["message"]
            for row in self._chat_history.getRecentMessages(f"{group_id}:{uin}", history_limit)
            if row["role"] == "bot"
        }
        filtered = []
        for row in records:
            if row["role"] == "user" and row["user_id"] == uin:
                continue
            if row["role"] == "bot" and row["message"] in bot_texts:
                continue
            filtered.append(row)
        if not filtered:
            return ""
        header = self._prompts.get(
            "group_context_header", "## 群聊上下文（群友最近的聊天，仅作背景参考）"
        )
        lines = [header]
        for row in filtered:
            if row["role"] == "bot":
                speaker = "机器人"
            else:
                speaker = row.get("nickname") or row["user_id"]
            lines.append(f"- {speaker}: {row['message']}")
        return "\n".join(lines)

    @registrar.qq.on_group_message()
    async def on_group_message(self, event: GroupMessageEvent):
        group_id = str(event.group_id)
        uin = str(event.user_id)
        user_key = f"{group_id}:{uin}"

        try:
            text = summarize_message(event.message)
            prompt = extract_prompt_from_event(event.message, self._bot_uin)
            reply_id = extract_reply_id(event.message)
        except Exception:
            LOG.exception("%s: 消息解析失败，已跳过", self.name)
            return

        nickname = extract_sender_name(getattr(event, "sender", None))

        # 解析引用内容（若有），供群流记录与 prompt 使用
        quoted = ""
        if reply_id and self._reply_context_enabled:
            quoted = await self._resolve_reply_context(event, reply_id)

        # 群聊上下文记录内容：引用回复时附带被引用内容
        group_text = text
        if quoted and text:
            group_text = f"{quoted} {text}"
        elif quoted:
            group_text = quoted

        # 1) 立即写入群聊上下文（真实接收时间）
        if group_text:
            self._record_group_message(group_id, uin, "user", group_text, nickname)
        # 2) 写入用户上下文（原文，用户维度记忆）
        if text:
            self._record_user_message(user_key, "user", text, group_id)

        # 3) 未 @机器人：到此结束
        if prompt is None:
            return

        if not prompt:
            await event.reply(self._prompts.get("no_prompt", "请先 @我 再输入问题哦～"))
            return

        if not self._consume_quota(uin):
            await event.reply(
                self._messages.get("quota_exceeded", "抱歉，今天的提问次数用完啦，明天再来吧～")
            )
            return

        # 引用回复拼进 prompt，让 bot 知道在回复什么
        if quoted:
            prompt = f"{quoted}\n{prompt}"

        history_limit = (
            self._history_limit_admin
            if uin in self._admin_uins
            else self._history_limit_normal
        )
        group_context = self._format_group_context(group_id, uin, history_limit)

        try:
            answer = await self._neko.askNeko(
                user_key,
                prompt,
                historyLimit=history_limit,
                extraContext=group_context,
                mode=PROMPT_MODE_COLD,
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

        self._record_user_message(user_key, "bot", answer, group_id)
        self._record_group_message(group_id, self._bot_uin, "bot", answer)
        await event.reply(answer)

    @registrar.qq.on_private_message()
    async def on_private_message(self, event: PrivateMessageEvent):
        """处理私聊消息：无需 @，整条消息作为 prompt，warm 模式回复。"""
        uin = str(event.user_id)

        try:
            text = summarize_message(event.message)
            reply_id = extract_reply_id(event.message)
        except Exception:
            LOG.exception("%s: 私聊消息解析失败，已跳过", self.name)
            return

        nickname = extract_sender_name(getattr(event, "sender", None))

        # 解析引用回复（若有）
        quoted = ""
        if reply_id and self._reply_context_enabled:
            quoted = await self._resolve_reply_context(event, reply_id)

        # 私聊不写群聊上下文，只写用户上下文（key = uin）
        if text:
            self._record_user_message(uin, "user", text, chatId=uin)

        prompt = text
        if quoted and prompt:
            prompt = f"{quoted}\n{prompt}"
        elif quoted:
            prompt = quoted

        if not prompt:
            await event.reply("主人想说什么呢？本喵在听哦～")
            return

        if not self._consume_quota(uin):
            await event.reply(
                self._messages.get("quota_exceeded", "抱歉，今天的提问次数用完啦，明天再来吧～")
            )
            return

        history_limit = (
            self._history_limit_admin
            if uin in self._admin_uins
            else self._history_limit_normal
        )

        try:
            answer = await self._neko.askNeko(
                uin, prompt, historyLimit=history_limit, mode=PROMPT_MODE_WARM
            )
        except Exception:
            LOG.exception("%s: 私聊 LLM 调用失败", self.name)
            await event.reply(
                self._messages.get("api_error", "呜……我刚刚遇到了一点问题，请稍后再试一次。")
            )
            return

        if not answer:
            await event.reply(
                self._messages.get("api_error", "呜……我刚刚遇到了一点问题，请稍后再试一次。")
            )
            return

        self._record_user_message(uin, "bot", answer, chatId=uin)
        await event.reply(answer)
