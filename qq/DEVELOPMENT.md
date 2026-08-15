# QQ 插件开发笔记（ai_chat）

面向后续接手开发的 Agent / 开发者。记录本仓库 QQ 机器人（NcatBot）侧的实测结论、数据模型、已知坑与待办，避免重复踩坑。

## 1. 运行环境与框架结构

- 机器人跑在 Docker 容器 ncatbot（huanyp/ncatbot:latest）内：NapCat（QQ 客户端 + OneBot11 服务端，监听 3001）+ NcatBot5（框架，WS 连本地 3001）。
- 仓库现有两个插件：`AI Chat/`（@问答，依赖 core）与 `Repeater/`（复读机，自包含不依赖 core）；两者的 `on_group_message` 由框架并行派发、互不影响。
- ncatbot 包路径（容器内）：/root/ncatbot/.venv/lib/python3.12/site-packages/ncatbot/
- 插件核心导入（已在 ai_chat 验证可用）：
  - from ncatbot.core import registrar
  - from ncatbot.event.qq import GroupMessageEvent
  - from ncatbot.plugin import NcatBotPlugin
  - from ncatbot.utils import get_config_manager, get_log
- 本地开发机没有 ncatbot（tests/test_qq_plugin.py 用桩模拟）。要读框架源码，直接 docker exec ncatbot sh -c cat 某个文件 最可靠。

## 2. 消息链路与日志归属

- 链路：NapCat 收 NT RawMessage -> 转 OB11 -> WS -> NcatBot -> MessageEvent（message 为 MessageArray）。
- 日志 [INFO] 接收 <- 群聊 [...]、[DEBUG] 收到新消息 RawMessage、[DEBUG] 转化为 OB11Message 都是 NapCat 打的，不是 NcatBot。调试时别去 ncatbot 源码里 grep 这些字符串（会找不到）。

## 3. 消息段模型（实测，重要）

- event.message 是 MessageArray（可迭代），元素是 pydantic MessageSegment 子类：
  - PlainText(_type="text", text)
  - At(_type="at", user_id)（OB11 别名 qq）
  - Reply(_type="reply", id)（只有被引用消息 id，不含内容）
  - Image / Video / Face / Record / ...（DownloadableSegment 等）
- 判类型用 getattr(seg, "_type", ...)，不是 seg.type（pydantic 用 _type ClassVar 标记类型）。
- MessageArray API：filter(cls) / filter_text() / filter_at() / filter_image() / filter_video() / is_at(user_id) / text 属性 / add_text / add_at / add_reply / add_segment / add_segments。
- 注意：没有 filter_reply()，取引用段用 filter(Reply)。
- 插件解析必须兼容 dict 形态（{"type":"text","data":{"text":"..."}}）与对象形态（pydantic 模型）两种；_iter_segments 已统一两者。

## 4. 引用回复（quote/reply）

- OB11 里 reply 段 = {"type":"reply","data":{"id":"..."}}，只有 id。
- 取被引用内容：await event.api.query.get_msg(reply_id) -> MessageData：
  - .sender: MessageSender(user_id, nickname, card, role)
  - .message: Optional[List[dict]]（OB11 段列表，可直接喂 extract_text_from_event）
  - .raw_message: CQ 码字符串（兜底用，不主用）
- event.api 是 QQAPIClient 门面：.query.get_msg / .messaging.send_group_msg / .manage.set_group_ban / .file.upload_group_file 等。
- 被引用消息被撤回/过期时 get_msg 返回空，必须 try/except 优雅降级。

## 5. 发送者信息

- event.sender 是 GroupSender（继承 QQSender -> BaseSender），字段：user_id / nickname / card（群名片）/ role / title 等。
- 显示名优先级：card（群名片）> nickname > user_id。无需额外 API 就能拿到昵称。

## 6. 聊天记录数据模型（当前实现）

- 同一 SQLite（默认 data/ai_chat/chatHistory.db）两张表：
  - chatHistory（用户上下文，username={group_id}:{uin}）：装「该用户所有发言（闲聊+@问答）+ bot 对其回复」，注入人设 {chatHistory}。
  - groupChatHistory（群聊上下文，group_id，含 nickname 列）：装「整群消息流」，拼成 extraContext 注入（精确去重后）。
- 记录时机：每条文本消息「收到时」立即写两侧（真实时间戳）；bot 回复在回复后写两侧。失败/超限的 @消息也会入群流（不丢）。
- 去重（_format_group_context）：剔除 role=user 且 user_id==当前用户 的记录 + role=bot 且 message 与该用户 bot 回复文本相同的记录；其余（他人同文本、bot 给别人的回复）保留。
- 保留策略：pruneMessages / pruneGroupMessages，max_history_rows（每用户，默认 2000）/ max_group_rows（每群，默认 5000），0=不清理。
- 非文本消息：summarize_message 给占位（图片->[图片]、语音->[语音]、表情->[表情]、其它->[非文本消息]）。

## 7. 关键配置（qq/AI Chat/config.yaml）

- context.history_limit_normal / history_limit_admin：用户上下文条数。
- context.group_context_limit：群聊上下文条数（0=关闭，同时停止写群流）。
- context.reply_context_enabled：是否解析引用回复。
- context.max_history_rows / max_group_rows：保留上限。
- 注意：config.yaml（含真实 QQ 号）与 OPERATIONS.md 被 gitignore；模板是 configExample.yaml。

## 8. 已知坑 / 待办

1. no_prompt 死代码：extract_prompt_from_event 用 return prompt or None，空文本返回 None，导致「只 @ 不说话」被当成「未 @」；on_group_message 里的 if not prompt 分支永远不会触发。要区分两者需改该函数返回契约（如返回 (at_bot, text) 二元组）。
2. 引用回复只解析一层、只取文本（多层嵌套不递归、图片/表情忽略）。
3. 私聊已实现：`@registrar.qq.on_private_message()` + `PrivateMessageEvent`（无 `group_id`，用 `event.user_id` 作上下文 key；`event.reply()` 对私聊自动不 @，内部走 `post_private_array_msg`）。模式接线：私聊 `PROMPT_MODE_WARM`、群聊 `PROMPT_MODE_COLD`。
4. history_limit 是「消息条数」不是「问答对数」；闲聊占窗后建议调大 normal（如 20~30）。
5. 时间戳默认 datetime.now(utc)（微秒精度）；测试里需要稳定顺序时显式传 timestamp，避免同微秒乱序。
6. 群聊上下文去重对「bot 给不同人发相同回复」仍有极小概率误删（bot 回复按文本匹配）。

## 9. 测试脚手架（tests/）

- test_qq_plugin.py 桩掉 ncatbot 各模块；get_log 返回带 no-op 方法的假 logger（否则 plugin.py 的 LOG.exception 会因 NoneType 崩溃）。
- _obj(seg_type, **kw) 造对象形态消息段（SimpleNamespace + .type）。
- 插件实例化用 _plugin.AiChatPlugin()（NcatBotPlugin 被桩成 object）；测方法前手动设 _chat_history / _prompts / _group_context_limit 等属性。
- 异步方法用 asyncio.run(...) 跑。

## 10. 部署与排查

- core/ 需复制进容器 plugins/AI Chat/core/（随 plugins 挂载持久化）。
- .py 改完热重载；.yaml 改完必须 docker restart ncatbot。
- groupChatHistory.nickname 列：旧库在下次启动时自动 ALTER TABLE 迁移。
- 看插件日志：docker logs -f ncatbot。