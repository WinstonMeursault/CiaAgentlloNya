# CiaBotlloNya

🌐 Languages: [![English](https://img.shields.io/badge/README-English-green)](README.md) [![中文](https://img.shields.io/badge/README-%E4%B8%AD%E6%96%87-blue)](README_CN.md)

A **personal nekomimi assistant bot**. Cia Bot llo~ (∠·ω< )⌒★ Nya~~~

This project is a nekomimi (cat-girl) chatbot powered by an online LLM. It is designed as a multi-platform bot: the shared LLM / persona / storage logic is centralized in [`core/`](core/), while each chat platform is implemented as an independent sub-package.

## Supported Platforms

| Platform | Status |
|----------|--------|
| Telegram | ✅ Implemented — see [`telegram/`](telegram/) |
| QQ       | ✅ Implemented — see [`qq/`](qq/) |

## Project Structure

```text
CiaBotlloNya/
├── core/                     # Shared, platform-agnostic package
│   ├── neko.py               # Nekomimi LLM API client
│   ├── chatHistory.py        # SQLite-backed chat history storage
│   ├── requirements.txt      # Shared dependencies
│   └── config/               # Shared LLM configuration
│       ├── configExample.yaml
│       ├── inf.yaml
│       ├── prompt_CN.yaml
│       └── prompt_EN.yaml
├── telegram/                 # Telegram bot
│   ├── bot.py                # Telegram bot application
│   ├── requirements.txt      # Telegram dependencies
│   ├── README.md             # Telegram-specific setup
│   └── config/               # Telegram configuration
│       ├── configExample.yaml
│       ├── replyTemplate_CN.yaml
│       └── replyTemplate_EN.yaml
└── qq/                       # QQ bot (NcatBot + ai_chat plugin)
    ├── AI Chat/              # ai_chat plugin (plugin.py, configExample.yaml, …)
    └── README.md
```

## Configuration

Configuration is split between shared LLM settings and per-platform settings.

### Shared LLM (`core/config/`)

Copy `core/config/configExample.yaml` to `core/config/config.yaml` and fill in your values.

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

- **api_provider** — the LLM backend. `DeepSeek` (OpenAI-compatible `chat/completions`, default) or `Opencode Zen` (legacy `responses`).
- **base_url / api_key / model** — DeepSeek endpoint, key, and model name.
- **thinking / reasoning_effort** — optional DeepSeek reasoning controls.
- **max_tokens / timeout_seconds** — output cap and request timeout.
- **language** — persona language: `CN` or `EN`.

### Telegram (`telegram/config/`)

Copy `telegram/config/configExample.yaml` to `telegram/config/config.yaml`. See [`telegram/README.md`](telegram/README.md) for the full setup and running instructions.

### QQ (`qq/AI Chat/`)

Copy `qq/AI Chat/configExample.yaml` to `qq/AI Chat/config.yaml`. See [`qq/README.md`](qq/README.md) for the full setup and running instructions.

## Running

```bash
pip install -r telegram/requirements.txt
python telegram/bot.py
```

You can also run it as a module from the repository root: `python -m telegram.bot`.

## Roadmap

- [x] Telegram Bot
- [x] QQ Bot
- [x] Web search (opt-in, two-pass judge + SearXNG) — see `docs/search-rag-design.md`
- [x] RAG semantic retrieval (opt-in, fastembed + chromadb) — see `docs/search-rag-design.md`

## License

[GPL-3.0](LICENSE)
