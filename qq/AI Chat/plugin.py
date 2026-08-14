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


def extract_prompt_from_event(message, bot_uin: str) -> Optional[str]:
    """判断消息是否 @ 了机器人；是则返回 @ 之外的完整文本作为 prompt。

    兼容两种消息段形态：OneBot dict（{"type", "data"}）与框架消息段对象
    （PlainText / At / Image ...），不依赖具体类名，便于后续扩展。
    """
    if isinstance(message, list):
        segments = message
    elif hasattr(message, "__iter__"):
        segments = list(message)
    else:
        segments = []

    at_bot = False
    parts: List[str] = []
    for seg in segments or []:
        if isinstance(seg, dict):
            seg_type = seg.get("type")
            data = seg.get("data") or {}
            if seg_type == "at":
                qq = str(data.get("qq", data.get("user_id", ""))).strip()
            elif seg_type == "text":
                parts.append(str(data.get("text", "")))
                qq = ""
            else:
                qq = ""
        else:
            seg_type = getattr(seg, "type", None) or getattr(seg, "_type", None)
            if seg_type == "at":
                qq = str(
                    getattr(seg, "user_id", "") or getattr(seg, "qq", "")
                ).strip()
            elif seg_type == "text":
                parts.append(str(getattr(seg, "text", "")))
                qq = ""
            else:
                qq = ""
        if seg_type == "at" and qq == str(bot_uin).strip():
            at_bot = True
    if not at_bot:
        return None
    prompt = "".join(parts).strip()
    return prompt or None


class AiChatPlugin(NcatBotPlugin):
    name = "ai_chat"
    version = "0.2.0"
    author = "Meursault"
    description = "群内 @离岛酱 触发月羽雪乃问答（共享 core/DeepSeek 后端，带每日限额与持久上下文）"

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

        # 共享后端：SQLite 历史 + DeepSeek/月羽雪乃 人设（core）
        self._chat_history = ChatHistory(dbPath=self._resolve_db_path())
        self._neko = Neko(self._chat_history)

        LOG.info(
            "%s 已加载 (bot_uin=%s, admins=%s, 每日限额=%d, 上下文:普通%d/高权限%d)",
            self.name,
            self._bot_uin,
            sorted(self._admin_uins),
            self._daily_limit,
            self._history_limit_normal,
            self._history_limit_admin,
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

    @registrar.qq.on_group_message()
    async def on_group_message(self, event: GroupMessageEvent):
        try:
            prompt = extract_prompt_from_event(event.message, self._bot_uin)
        except Exception:
            LOG.exception("%s: 消息解析失败，已跳过", self.name)
            return
        if prompt is None:
            return
        if not prompt:
            await event.reply(self._prompts.get("no_prompt", "请先 @我 再输入问题哦～"))
            return

        uin = str(event.user_id)
        if not self._consume_quota(uin):
            await event.reply(
                self._messages.get("quota_exceeded", "抱歉，今天的提问次数用完啦，明天再来吧～")
            )
            return

        group_id = str(event.group_id)
        # 上下文按「群 + 用户」隔离，避免跨群/跨用户串味
        user_key = f"{group_id}:{uin}"
        history_limit = (
            self._history_limit_admin
            if uin in self._admin_uins
            else self._history_limit_normal
        )

        try:
            answer = await self._neko.askNeko(user_key, prompt, historyLimit=history_limit)
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
        await event.reply(answer)
