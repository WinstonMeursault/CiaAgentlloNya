# QQ Bot

QQ bot implementation for CiaBotlloNya, built on the NcatBot framework (NapCat + NcatBot5) running inside a Docker container.

The bot replies via the shared [`core/`](../core/) LLM backend (**DeepSeek chat/completions** + **月羽雪乃** persona + persistent context) when a group message mentions (@) it.

## Structure

```text
qq/
├── requirements.txt          # Local reference deps (actually runs in the NcatBot image)
├── README.md / README_CN.md  # This doc
├── OPERATIONS.md             # Internal ops manual (gitignored, deployment details)
└── AI Chat/                  # ai_chat plugin (the actual bot logic)
    ├── manifest.toml         # Plugin manifest
    ├── __init__.py
    ├── plugin.py             # Plugin logic (NcatBotPlugin → core/Neko + ChatHistory)
    ├── configExample.yaml    # QQ-side config template (copy to config.yaml)
    ├── prompts.yaml          # Guide text (persona lives in core)
    ├── messages.yaml         # Fixed reply texts
    └── README.md             # Plugin details
```

## Configuration

LLM backend settings (provider / base_url / api_key / model / thinking / reasoning_effort / max_tokens / timeout / language) are shared and live in **`core/config/config.yaml`** (copy from `core/config/configExample.yaml`).

Copy `AI Chat/configExample.yaml` to `AI Chat/config.yaml` and fill in the QQ-side values:

- `admin_uins` — QQ numbers allowed unlimited calls (and a larger context window)
- `rate_limit.*` — per-user daily limit (Beijing time UTC+8)
- `context.*` — context window size (normal vs admin, recent message count)
- `chat_history.db_path` — optional SQLite path (defaults to the container `data/ai_chat/` dir)

> Both `core/config/config.yaml` and `AI Chat/config.yaml` contain secrets and are **gitignored** — never commit them.

## Deployment note

The plugin imports the shared `core` package. Copy the repository `core/` directory into the deployed plugin folder (`plugins/ai_chat/core/`) — the plugin resolves `core` automatically from either the plugin directory or the container root. See `OPERATIONS.md` for the exact steps.

## Running

The bot runs inside the NcatBot Docker image. Start / stop it with:

```bash
docker start ncatbot
docker stop ncatbot
docker restart ncatbot
```

See `AI Chat/README.md` for plugin behavior details.

## Related

- [Telegram bot](../telegram/)
- [Shared core](../core/)
