# CiaBotlloNya

🌐 Languages: [![English](https://img.shields.io/badge/README-English-green)](README.md) [![中文](https://img.shields.io/badge/README-%E4%B8%AD%E6%96%87-blue)](README_CN.md)

一个**个人猫娘助手**机器人。 Cia Bot llo~ (∠·ω< )⌒★ Nya~~~

本项目是一个基于在线 LLM 的猫娘聊天机器人，按多平台机器人设计：共享的 LLM / 人设 / 存储逻辑集中在 [`core/`](core/)，各聊天平台以独立子包实现。

## 支持的平台

| 平台 | 状态 |
|------|------|
| Telegram | ✅ 已实现 — 见 [`telegram/`](telegram/) |
| QQ       | ✅ 已实现 — 见 [`qq/`](qq/) |

## 项目结构

```text
CiaBotlloNya/
├── core/                     # 共享、平台无关的包
│   ├── neko.py               # 猫娘 LLM API 客户端
│   ├── chatHistory.py        # 基于 SQLite 的聊天历史存储
│   ├── requirements.txt      # 共享依赖
│   └── config/               # 共享 LLM 配置
│       ├── configExample.yaml
│       ├── inf.yaml
│       ├── prompt_CN.yaml
│       └── prompt_EN.yaml
├── telegram/                 # Telegram 机器人
│   ├── bot.py                # Telegram 机器人应用
│   ├── requirements.txt      # Telegram 依赖
│   ├── README.md             # Telegram 专属说明
│   └── config/               # Telegram 配置
│       ├── configExample.yaml
│       ├── replyTemplate_CN.yaml
│       └── replyTemplate_EN.yaml
└── qq/                       # QQ 机器人（NcatBot + ai_chat 插件）
    ├── AI Chat/              # ai_chat 插件（plugin.py、configExample.yaml 等）
    └── README.md
```

## 配置

配置分为「共享 LLM 配置」与「各平台配置」两部分。

### 共享 LLM（`core/config/`）

将 `core/config/configExample.yaml` 复制为 `core/config/config.yaml` 并填入你的值。

```yaml
llm:
    api_provider: DeepSeek
    base_url: https://api.deepseek.com
    api_key: sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    model: deepseek-v4-flash
    thinking:
        type: enabled
    reasoning_effort: medium
    max_tokens: 1024
    timeout_seconds: 60
    language: CN
```

- **api_provider** — LLM 后端：`DeepSeek`（OpenAI 兼容 `chat/completions`，默认）或 `Opencode Zen`（旧 `responses` 路径）。
- **base_url / api_key / model** — DeepSeek 的地址、密钥与模型名。
- **thinking / reasoning_effort** — 可选，DeepSeek 思考模式开关与强度。
- **max_tokens / timeout_seconds** — 输出上限与请求超时。
- **language** — 人设语言：`CN` 或 `EN`。

### Telegram（`telegram/config/`）

将 `telegram/config/configExample.yaml` 复制为 `telegram/config/config.yaml`。完整配置与运行说明见 [`telegram/README.md`](telegram/README.md)。

### QQ（`qq/AI Chat/`）

将 `qq/AI Chat/configExample.yaml` 复制为 `qq/AI Chat/config.yaml`。完整配置与运行说明见 [`qq/README.md`](qq/README.md)。

## 运行

```bash
pip install -r telegram/requirements.txt
python telegram/bot.py
```

也可以在仓库根目录以模块方式运行：`python -m telegram.bot`。

## 路线图

- [x] Telegram Bot
- [x] QQ Bot

## 许可证

[GPL-3.0](LICENSE)
