# ai_chat 插件

群内 @离岛酱 触发「月羽雪乃」nekomimi 问答，支持私聊。

LLM 后端已统一到共享 [`core/`](../../core/)（`Neko` + `ChatHistory`），与 Telegram 共用同一套 **DeepSeek chat/completions** 后端与**月羽雪乃**人设。

## 功能

- **双模式人设**：私聊走 `warm`（对主人的热情模式）、群聊一律走 `cold`（对陌生人害羞强装的高冷模式），由 `core/config/prompt_*.yaml` 的 `*_warm`/`*_cold` 分块驱动
- 群消息中 `@机器人` 时，将 @ 之外的完整文本作为 prompt，经 `core.neko.Neko` 调用 DeepSeek 回复（cold 模式）
- 私聊消息整条作为 prompt 直接回复（无需 @，warm 模式），同样计入每日限额与持久上下文
- 回复使用「月羽雪乃」猫娘人设（`core/config/prompt_CN/EN.yaml`，语言由 `core/config/config.yaml` 的 `llm.language` 决定）
- 持久上下文：按「群 + 用户」隔离，普通用户取最近 10 条、高权限组取最近 50 条消息作为上下文（存 SQLite）
- 用户维度记忆：每条群消息都记入对应用户的上下文（含一般闲聊、@问答与机器人回复），bot 能记得每个用户说过什么
- 群聊上下文：额外缓存本群最近 `group_context_limit` 条完整群消息流，拼进人设 prompt 的 `{chatHistory}` 时，剔除当前用户自己的 @问答记录后再一并注入
- 引用回复感知：@机器人 且带「引用回复」时，拉取被引用消息，把「被引用人 + 被引用内容」拼进 prompt；群聊上下文也记录引用关系（可经 `reply_context_enabled` 关闭）
- 高权限用户组（`admin_uins`）不限次数
- 普通用户每天（北京时间 UTC+8）最多 10 次，超出后回复固定道歉语

## 配置

- LLM 后端（DeepSeek base_url / api_key / model / thinking / reasoning_effort / max_tokens / timeout / language）：**在 `core/config/config.yaml` 配置**，本插件不再包含密钥。
- `config.yaml`：`admin_uins`（高权限组）、`rate_limit`（每日限额）、`context`（上下文条数，含 `group_context_limit` 群聊上下文条数、`reply_context_enabled` 引用回复开关、`max_history_rows`/`max_group_rows` 保留上限）、`chat_history.db_path`（可选，历史库路径）。首次使用复制 `configExample.yaml` 为 `config.yaml`（`config.yaml` 已被 gitignore，不入库）。
- `prompts.yaml`：无输入引导语
- `messages.yaml`：限额用尽、调用出错时的固定文案

修改 `.yaml` 后需 `docker restart ncatbot` 才生效（FileWatcher 只监听 `.py`）。

## 部署注意

插件依赖 `core` 包。推荐把仓库 `core/` 目录复制到 `plugins/AI Chat/core/`（随 `plugins/` 挂载一起持久化），并在容器内准备好 `core/config/config.yaml`。详见 [`qq/OPERATIONS.md`](../OPERATIONS.md)。

## 说明

- 上下文「10/50 条」指「最近 10/50 条消息」（非问答对数），可在 `context` 中调整。
- 群聊上下文默认缓存本群最近 50 条群消息（`context.group_context_limit`，0 关闭）；拼装时剔除当前用户自己的 @问答记录后，一并拼进人设 prompt 的 `{chatHistory}`。
- 引用回复：@机器人 且带引用时，会经 `get_msg` 拉取被引用消息的「群名片/昵称 + 文本」，失败或非文本时优雅降级；可用 `context.reply_context_enabled` 关闭。
- 保留策略：`context.max_history_rows`（每用户）与 `context.max_group_rows`（每群）控制最多保留条数，0 表示不清理，避免数据库无限增长。
- 调用次数按「触发即计数」计算（含 API 失败的情况），防止刷接口。
- 历史库默认落盘到容器 `data/ai_chat/chatHistory.db`，与 Telegram 的 `core/database/chatHistory.db` 相互独立。
