# ai_chat 插件

群内 @离岛酱 触发 DeepSeek V4 Flash 问答。

## 功能

- 群消息中 `@机器人` 时，将 @ 之外的完整文本作为 prompt 调用 DeepSeek
- 每次问答相互独立，不携带上下文
- 高权限用户组（`admin_uins`）不限次数
- 普通用户每天（北京时间 UTC+8）最多 10 次，超出后回复固定道歉语

## 配置

首次使用请先复制 `configExample.yaml` 为 `config.yaml`（`config.yaml` 含密钥、已被 gitignore，不入库）。

- `config.yaml`：DeepSeek API（base_url / api_key / model / thinking / reasoning_effort / max_tokens / timeout）、高权限用户组、每日限额
- `prompts.yaml`：系统提示词、无输入引导语
- `messages.yaml`：限额用尽、调用出错时的固定文案

修改后热重载即可生效；如未自动重载，`docker restart ncatbot`。

## 说明

“DeepSeek V4 Flash Medium”对应配置为 `model: deepseek-v4-flash` + `reasoning_effort: medium`（官方 API 已实测可用）。
调用次数按“触发即计数”计算（含 API 失败的情况），防止刷接口。
