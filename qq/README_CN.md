# QQ 机器人

CiaBotlloNya 的 QQ 机器人实现，基于 NcatBot 框架（NapCat + NcatBot5），运行在 Docker 容器内。

机器人在群聊中被 @ 时，调用 DeepSeek LLM 进行回复。

## 目录结构

```text
qq/
├── requirements.txt          # 本地参考依赖（实际运行于 NcatBot 镜像内）
├── README.md / README_CN.md  # 本文档
└── AI Chat/                  # ai_chat 插件（实际业务逻辑）
    ├── manifest.toml         # 插件清单
    ├── __init__.py
    ├── plugin.py             # 插件逻辑（NcatBotPlugin）
    ├── configExample.yaml    # 配置模板（复制为 config.yaml）
    ├── prompts.yaml          # 系统提示词 / 引导文案
    ├── messages.yaml         # 固定回复文案
    └── README.md             # 插件详情
```

## 配置

将 `AI Chat/configExample.yaml` 复制为 `AI Chat/config.yaml` 并填入你的值：

- `deepseek.*` — DeepSeek API（`base_url` / `api_key` / `model` / `thinking` / `reasoning_effort` / `max_tokens` / `timeout_seconds`）
- `admin_uins` — 可无限次调用的 QQ 号
- `rate_limit.*` — 普通用户每日限额（北京时间 UTC+8）

> `config.yaml` 含 API 密钥，已被 **gitignore**，请勿提交。

## 运行

机器人运行在 NcatBot Docker 镜像内，用以下命令启停：

```bash
docker start ncatbot
docker stop ncatbot
docker restart ncatbot
```

插件行为详见 `AI Chat/README.md`。

## 相关

- [Telegram 机器人](../telegram/)
- [共享核心](../core/)
