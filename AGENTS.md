# AGENTS.md - Developer Guide for CiaBotlloNya

## Project Overview
A multi-platform nekomimi agent bot with LLM integration and persistent chat history (Telegram and QQ implemented).

| File | Description |
|------|-------------|
| `telegram/bot.py` | Telegram bot application |
| `core/neko.py` | Nekomimi LLM API client |
| `core/chatHistory.py` | SQLite-backed conversation storage |
| `core/config/` | Shared LLM YAML configuration |
| `telegram/config/` | Telegram YAML configuration |
| `qq/AI Chat/` | QQ bot ai_chat plugin (NcatBot) |

## Running the Bot
```bash
pip install -r telegram/requirements.txt
python telegram/bot.py
```

## Testing & Linting
Currently, no test framework or linter is strictly enforced, but `pytest` is recommended for future development.

```bash
# Run all tests (if any)
pytest

# Run a single test file
pytest path/to/test_file.py

# Run a single test function
pytest path/to/test_file.py::test_function

# Run tests with verbose output
pytest -v
```

## Code Style Guidelines

### Naming Conventions
- **Classes:** `PascalCase` (e.g., `ChatHistory`, `Bot`, `Neko`)
- **Methods/Functions:** `camelCase` (e.g., `addMessage()`, `askNeko()`)
- **Variables/Parameters:** `camelCase` (e.g., `dbPath`, `chatId`, `streamId`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `MAX_SEND_RETRIES`)
- **Private methods:** `_` prefix (e.g., `__sendMessage()`)

### Imports
Organize in three groups: Standard library, Third-party, Local.
```python
import os
import sqlite3
from typing import Any, Dict, List, Optional

import aiohttp
from loguru import logger

from core.neko import Neko
from core.chatHistory import ChatHistory
```

### Type Hints
Always use type hints for parameters and return values.
```python
def getRecentMessages(self, username: str, limit: int) -> List[Dict[str, str]]:
    ...
```

### Docstrings (Google Style)
```python
class ChatHistory:
    """SQLite-backed chat history store."""
    def addMessage(self, username: str, role: str, message: str) -> None:
        """Persist a message record.

        Args:
            username: Username associated with the message.
            role: Role of the speaker, either ``user`` or ``bot``.
            message: Message body.
        """
```

### Error Handling
- Catch specific exceptions before general ones.
- Log errors with context using `loguru` before re-raising.
- Handle Telegram rate limits (`RetryAfter`) with `asyncio.sleep()`.
- Use a naked `raise` to preserve the original traceback when re-raising from a catch-all block.
```python
try:
    await context.bot.send_message(chat_id=chatId, text=text)
except RetryAfter as e:
    self.logger.warning(f"Rate limit exceeded. Retrying after {e.retry_after}")
    await asyncio.sleep(e.retry_after)
except Exception as e:
    self.logger.error(f"Unexpected error: {e}")
    raise
```

### Logging
Use `loguru` with module binding:
```python
from loguru import logger
self.logger = logger.bind(module="bot")
self.logger.info(f"Message sent to {chatId}")
```

### Async/Await
- Use `async`/`await` for all async operations.
- Avoid blocking the event loop with synchronous calls; use `aiohttp` for HTTP.
- Use `asyncio.create_task()` for non-critical fire-and-forget tasks.
- Use `asyncio.get_running_loop()` for the event loop.

### Database Operations
Use context managers for connections and handle corruption gracefully by backing up the database file.
```python
with sqlite3.connect(self.dbPath) as connection:
    connection.execute(
        "INSERT INTO chatHistory (timestamp, username, role, message) VALUES (?, ?, ?, ?)",
        (timestamp.isoformat(), username, role, message),
    )
```

### Configuration
Configuration is split between shared LLM settings and per-platform settings. Ensure changes are persisted correctly by reading the `fullConfig` first.

Shared LLM (`core/config/config.yaml`):
```yaml
llm:
    api_provider: DeepSeek
    base_url: https://api.deepseek.com
    api_key: <api-key>
    model: deepseek-v4-flash
    thinking:
        type: enabled
    reasoning_effort: medium
    max_tokens: 1024
    timeout_seconds: 60
    language: CN
```

Telegram (`telegram/config/config.yaml`):
```yaml
TelegramBot:
    Token: <bot-token>
    Language: CN
    StreamingResponse: False
```

## File Structure
```
CiaBotlloNya/
├── core/                 # Shared, platform-agnostic package
│   ├── neko.py           # Nekomimi LLM API client
│   ├── chatHistory.py    # SQLite chat storage
│   ├── requirements.txt  # Shared dependencies
│   └── config/           # Shared LLM YAML configuration
├── telegram/             # Telegram bot
│   ├── bot.py            # Telegram bot application
│   ├── requirements.txt  # Telegram dependencies
│   └── config/           # Telegram YAML configuration
├── qq/                   # QQ bot (NcatBot + ai_chat plugin)
│   ├── AI Chat/          # ai_chat plugin
│   └── README.md
├── README.md             # English README
├── README_CN.md          # Chinese README
├── LICENSE               # GPL-3.0
└── AGENTS.md             # This file
```
