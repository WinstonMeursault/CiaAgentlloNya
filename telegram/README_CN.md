# Telegram 机器人

CiaBotlloNya 的 Telegram 机器人实现。

## 前置条件

Telegram 机器人也需要共享 LLM 配置。运行前请将 `../core/config/configExample.yaml` 复制为 `../core/config/config.yaml`，并填写 `llm`（DeepSeek）段。

## 配置

将 `config/configExample.yaml` 复制为 `config/config.yaml` 并填入你的值。

```yaml
TelegramBot:
    Token: xxxxxxxxxx:xxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxx
    Language: xx
    StreamingResponse: False
```

### Token

填写你的 Telegram Bot 的 Token（HTTP API）。如果你还没有在 Telegram 上注册机器人，请使用 [@BotFather](https://t.me/BotFather)：发送 `/start` 后执行 `/newbot`，按提示设置机器人名称与用户名，即可获得 Token。

### Language

机器人使用的语言。支持的值：

- `CN` — （简体）中文
- `EN` — 英文

### StreamingResponse

机器人回复时是单次完整响应（`False`）还是流式响应（`True`）。

流式响应目前存在 bug：用户可能同时收到两条相同的响应，且其中一条可能在一段时间后或在某些未确定条件下消失。由于回复内容一般不会太长，建议设置为 `False`。

## 运行

在仓库根目录：

```bash
pip install -r telegram/requirements.txt
python telegram/bot.py
```

或以模块方式运行：

```bash
python -m telegram.bot
```
