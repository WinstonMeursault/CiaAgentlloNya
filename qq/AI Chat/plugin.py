"""群内 @离岛酱 触发 DeepSeek V4 Flash 问答插件。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import aiohttp
import yaml

from ncatbot.core import registrar
from ncatbot.event.qq import GroupMessageEvent
from ncatbot.plugin import NcatBotPlugin
from ncatbot.utils import get_config_manager, get_log

LOG = get_log("AiChatPlugin")


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
    version = "0.1.0"
    author = "Meursault"
    description = "群内 @离岛酱 触发 DeepSeek V4 Flash 问答（带每日限额）"

    async def on_load(self):
        self._bot_uin = str(get_config_manager().config.bot_uin)
        self._admin_uins: set[str] = {
            str(uin) for uin in self.get_config("admin_uins", [])
        }
        self._prompts = self._load_extra_yaml("prompts.yaml")
        self._messages = self._load_extra_yaml("messages.yaml")
        self._deepseek = self.get_config("deepseek", {}) or {}
        rate_limit = self.get_config("rate_limit", {}) or {}
        self._daily_limit = max(1, int(rate_limit.get("daily_limit", 10)))
        self._timezone = timezone(timedelta(hours=int(rate_limit.get("utc_offset_hours", 8))))
        LOG.info(
            "%s 已加载 (bot_uin=%s, admins=%s, 每日限额=%d)",
            self.name,
            self._bot_uin,
            sorted(self._admin_uins),
            self._daily_limit,
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

    async def _ask_deepseek(self, prompt: str) -> str:
        base_url = str(self._deepseek.get("base_url", "https://api.deepseek.com")).rstrip("/")
        api_key = str(self._deepseek.get("api_key", "")).strip()
        if not api_key:
            raise RuntimeError("未配置 DeepSeek API Key")

        payload: dict = {
            "model": self._deepseek.get("model", "deepseek-v4-flash"),
            "messages": [
                {"role": "system", "content": self._prompts.get("system_prompt", "")},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "max_tokens": int(self._deepseek.get("max_tokens", 1024)),
        }
        if self._deepseek.get("reasoning_effort"):
            payload["reasoning_effort"] = str(self._deepseek["reasoning_effort"])
        thinking = self._deepseek.get("thinking")
        if thinking:
            payload["thinking"] = thinking

        timeout = aiohttp.ClientTimeout(
            total=int(self._deepseek.get("timeout_seconds", 60))
        )
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status != 200:
                    raise RuntimeError(f"DeepSeek API 返回 {resp.status}: {data}")
                try:
                    content = data["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError) as exc:
                    raise RuntimeError(f"DeepSeek API 响应异常: {data}") from exc
        return str(content).strip()

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

        try:
            answer = await self._ask_deepseek(prompt)
        except Exception:
            LOG.exception("%s: DeepSeek 调用失败", self.name)
            await event.reply(
                self._messages.get("api_error", "呜……我刚刚遇到了一点问题，请稍后再试一次。")
            )
            return

        await event.reply(answer)
