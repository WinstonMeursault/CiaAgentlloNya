# QQ 机器人

CiaBotlloNya 的 QQ 机器人实现，基于 NcatBot 框架（NapCat + NcatBot5），运行在 Docker 容器内。

机器人在群聊中被 @ 时，经共享 [`core/`](../core/) LLM 后端（**DeepSeek chat/completions** + **月羽雪乃**人设 + 持久上下文）进行回复。

## 目录结构

```text
qq/
├── requirements.txt          # 本地参考依赖（实际运行于 NcatBot 镜像内）
├── README.md / README_CN.md  # 本文档
├── OPERATIONS.md             # 内部运维手册（gitignore，含部署细节）
└── AI Chat/                  # ai_chat 插件（实际业务逻辑）
    ├── manifest.toml         # 插件清单
    ├── __init__.py
    ├── plugin.py             # 插件逻辑（NcatBotPlugin → core/Neko + ChatHistory）
    ├── configExample.yaml    # QQ 侧配置模板（复制为 config.yaml）
    ├── prompts.yaml          # 引导文案（人设在 core）
    ├── messages.yaml         # 固定回复文案
    └── README.md             # 插件详情
```

## 配置

LLM 后端（provider / base_url / api_key / model / thinking / reasoning_effort / max_tokens / timeout / language）由 Telegram 与 QQ 共享，统一放在 **`core/config/config.yaml`**（复制自 `core/config/configExample.yaml`）。

将 `AI Chat/configExample.yaml` 复制为 `AI Chat/config.yaml` 并填入 QQ 侧的值：

- `admin_uins` — 可无限次调用（且使用更大上下文窗口）的 QQ 号
- `unlimited_groups` — 无限额群：群内所有成员的问答均不记入额度（不影响其他群/私聊额度）
- `rate_limit.*` — 普通用户每日限额（北京时间 UTC+8）
- `context.*` — 上下文窗口大小（普通 / 高权限，按最近消息条数）
- `chat_history.db_path` — 可选 SQLite 路径（默认落到容器 `data/ai_chat/` 目录）

> `core/config/config.yaml` 与 `AI Chat/config.yaml` 均含密钥，已被 **gitignore**，请勿提交。

## 部署注意

插件依赖共享 `core` 包。将仓库 `core/` 目录复制到部署后的插件目录（`plugins/AI Chat/core/`）——插件会从「插件目录」或「容器根目录」自动定位 `core`。具体步骤见 `OPERATIONS.md`。

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
