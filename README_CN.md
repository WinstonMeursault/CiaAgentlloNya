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
│   ├── neko.py               # 猫娘 LLM API 客户端（含两段式判需）
│   ├── chatHistory.py        # 基于 SQLite 的聊天历史存储
│   ├── search.py             # 搜索供应商抽象（SearXNG，JSON 优先 + HTML 兜底）
│   ├── knowledge.py          # RAG 知识库（fastembed + chromadb）
│   ├── enhancer.py           # SearchEnhancer：判需 → 检索 → 格式化编排
│   ├── requirements.txt      # 共享依赖
│   ├── requirements-rag.txt  # RAG 可选依赖（fastembed、chromadb）
│   └── config/               # 共享 LLM 配置
│       ├── configExample.yaml
│       ├── inf.yaml
│       ├── prompt_CN.yaml
│       └── prompt_EN.yaml
├── deploy/                   # 部署配置
│   └── searxng/              # 自建 SearXNG（docker-compose 一键部署）
│       ├── docker-compose.yml
│       └── settings.yml.example
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

## 联网搜索与 RAG（可选增强）

`core/` 内置两个 opt-in 增强能力，配置位于 `core/config/config.yaml` 的 `llm.enhance` 段：

- **联网搜索**（`enhance.search`）：两段式——先用中性路由判断是否需要搜索，需要则经 SearXNG 检索并把结果注入 `{searchResults}`。默认判需策略：除情感类、时间日期类问题外一律联网。
- **RAG 语义检索**（`enhance.rag`）：本地 fastembed（BGE-small-zh-v1.5）+ chromadb，把文档库内容注入 `{knowledge}`。

搜索供应商建议自建 SearXNG：`deploy/searxng/` 提供 docker-compose 一键部署（宿主端口 `127.0.0.1:8888`，bot 容器经 `searxng-net` 网络以 `http://searxng:8080` 访问）。详见 [`docs/search-rag-design.md`](docs/search-rag-design.md)。

## 路线图

- [x] Telegram Bot
- [x] QQ Bot
- [x] 联网搜索（可选，两段式判需 + SearXNG）— 见 `docs/search-rag-design.md`
- [x] RAG 语义检索（可选，fastembed + chromadb）— 见 `docs/search-rag-design.md`

## 许可证

[GPL-3.0](LICENSE)
