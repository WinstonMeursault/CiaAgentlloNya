# AGENTS.md - Developer Guide for CiaAgentlloNya

## Project Overview
A Telegram nekomimi agent bot with LLM integration and persistent chat history.

| File | Description |
|------|-------------|
| `bot.py` | Main Telegram bot application |
| `neko.py` | Nekomimi LLM API client |
| `chatHistory.py` | SQLite-backed conversation storage |
| `config/` | YAML configuration files |

## Running the Bot
```bash
pip install -r requirements.txt
python bot.py
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

from neko import Neko
from chatHistory import ChatHistory
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
            username: Telegram username associated with the message.
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

### Configuration (config/config.yaml)
Ensure all changes to the configuration are persisted correctly by reading the `fullConfig` first.
```yaml
Nekomimi:
    API Provider: <provider>
    Model: <model>
    Token: <api-token>
    Language: CN

TelegramBot:
    Token: <bot-token>
    Language: CN
    StreamingResponse: False
```

## File Structure
```
CiaAgentlloNya/
├── bot.py            # Telegram bot entry point
├── neko.py           # LLM API client
├── chatHistory.py    # SQLite chat storage
├── config/           # YAML configuration
├── database/         # SQLite database files
├── logs/             # Log output
├── requirements.txt  # Dependencies
└── AGENTS.md         # This file
```
