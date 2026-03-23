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

## Testing

No test framework is currently configured.

```bash
# Recommended: add pytest
pip install pytest

# Run all tests
pytest

# Run a single test
pytest path/to/test_file.py::test_function

# Run tests with verbose output
pytest -v
```

## Code Style Guidelines

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Classes | PascalCase | `ChatHistory` |
| Methods/Functions | camelCase | `addMessage()` |
| Variables | camelCase | `dbPath`, `chatId` |
| Constants | UPPER_SNAKE_CASE | `MAX_RETRIES` |
| Private methods | `_` prefix | `_initializeDatabase()` |

### Imports

Organize in three groups separated by blank lines:

```python
# Standard library
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Third-party
import aiohttp
from loguru import logger
from yaml import safe_load as yamlSafeLoad

# Local
from neko import neko
from chatHistory import ChatHistory
```

### Type Hints

Always use type hints for parameters and return values.

```python
def addMessage(
    self,
    username: str,
    role: str,
    message: str,
    chatId: Optional[Any] = None,
    timestamp: Optional[datetime] = None,
) -> None:
    ...

def getRecentMessages(self, username: str, limit: int) -> List[Dict[str, str]]:
    ...
```

### Docstrings (Google Style)

```python
class ChatHistory:
    """SQLite-backed chat history store.

    Attributes:
        dbPath: Filesystem path of the SQLite database file.
    """

    def addMessage(
        self,
        username: str,
        role: str,
        message: str,
    ) -> None:
        """Persist a message record.

        Args:
            username: Telegram username associated with the message.
            role: Role of the speaker, either ``user`` or ``bot``.
            message: Message body.

        Raises:
            ValueError: If ``role`` is neither ``user`` nor ``bot``.
        """
```

### Error Handling

- Catch specific exceptions before general ones
- Log errors with context before re-raising
- Handle Telegram rate limits with backoff

```python
try:
    await context.bot.send_message(chat_id=chatId, text=text)
except RetryAfter as e:
    self.logger.warning(f"Rate limit exceeded. Retrying after {e.retry_after}")
    await asyncio.sleep(e.retry_after)
except BadRequest as e:
    self.logger.error(f"Bad request: {e}")
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

- Use `async`/`await` for all async operations
- Use `asyncio.create_task()` for fire-and-forget
- Never block the event loop with synchronous calls

```python
async def handleMessage(self, update: Update) -> None:
    response = await self.getResponse(update.message.text)
    asyncio.create_task(self.sendMessage(update.effective_chat.id, response))
```

### Database Operations

- Use context managers for connections
- Validate data before insertion
- Handle corruption gracefully

```python
with sqlite3.connect(self.dbPath) as connection:
    connection.execute(
        "INSERT INTO chatHistory (timestamp, username, role, message) VALUES (?, ?, ?, ?)",
        (timestamp.isoformat(), username, role, message),
    )
```

### Configuration

Store in `config/config.yaml`:

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
