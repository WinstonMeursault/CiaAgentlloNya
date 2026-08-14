# Telegram Bot

Telegram bot implementation for CiaBotlloNya.

## Prerequisites

The Telegram bot also requires the shared LLM configuration. Copy `../core/config/configExample.yaml` to `../core/config/config.yaml` and fill in the `Nekomimi` section before running.

## Configuration

Copy `config/configExample.yaml` to `config/config.yaml` and fill in your values.

```yaml
TelegramBot:
    Token: xxxxxxxxxx:xxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxx
    Language: xx
    StreamingResponse: False
```

### Token

Enter your Telegram Bot token (HTTP API). If you have not registered a bot yet, use [@BotFather](https://t.me/BotFather): send `/start`, then `/newbot`, and follow the instructions to set the bot name and username. You will then receive the token.

### Language

The language used by the bot. Supported values:

- `CN` — (Simplified) Chinese
- `EN` — English

### StreamingResponse

Whether the bot replies with a single complete response (`False`) or a streamed response (`True`).

Streamed responses currently have a bug: users may receive two identical responses simultaneously, and one of the messages may disappear after some time or under certain undefined conditions. Since the response content is generally not very long, it is recommended to set this to `False`.

## Running

From the repository root:

```bash
pip install -r telegram/requirements.txt
python telegram/bot.py
```

Or as a module:

```bash
python -m telegram.bot
```
