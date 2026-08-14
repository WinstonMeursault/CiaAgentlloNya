# QQ Bot

QQ bot implementation for CiaBotlloNya, built on the NcatBot framework (NapCat + NcatBot5) running inside a Docker container.

The bot replies via the DeepSeek LLM when a group message mentions (@) it.

## Structure

```text
qq/
├── requirements.txt          # Local reference deps (actually runs in the NcatBot image)
├── README.md / README_CN.md  # This doc
└── AI Chat/                  # ai_chat plugin (the actual bot logic)
    ├── manifest.toml         # Plugin manifest
    ├── __init__.py
    ├── plugin.py             # Plugin logic (NcatBotPlugin)
    ├── configExample.yaml    # Configuration template (copy to config.yaml)
    ├── prompts.yaml          # System prompt / guide text
    ├── messages.yaml         # Fixed reply texts
    └── README.md             # Plugin details
```

## Configuration

Copy `AI Chat/configExample.yaml` to `AI Chat/config.yaml` and fill in your values:

- `deepseek.*` — DeepSeek API (`base_url` / `api_key` / `model` / `thinking` / `reasoning_effort` / `max_tokens` / `timeout_seconds`)
- `admin_uins` — QQ numbers allowed unlimited calls
- `rate_limit.*` — per-user daily limit (Beijing time UTC+8)

> `config.yaml` contains the API key and is **gitignored** — never commit it.

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
