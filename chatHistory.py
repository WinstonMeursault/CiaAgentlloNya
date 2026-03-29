"""SQLite-backed chat history storage module."""

import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ChatHistory:
    """SQLite-backed chat history store.

    Attributes:
        dbPath: Filesystem path of the SQLite database file.
    """

    def __init__(
        self,
        dbPath: str = os.path.dirname(os.path.realpath(__file__))
        + "/database/chatHistory.db",
    ) -> None:
        """Initialize the chat history store.

        Args:
            dbPath: Destination for the SQLite database file.
        """
        self.dbPath = dbPath
        os.makedirs(os.path.dirname(self.dbPath), exist_ok=True)
        self._ensureValidDatabase()
        self._initializeDatabase()

    def _ensureValidDatabase(self) -> None:
        """Validate the database file and recreate it if corruption is detected."""
        if not os.path.exists(self.dbPath):
            return

        try:
            with sqlite3.connect(self.dbPath) as connection:
                result = connection.execute("PRAGMA integrity_check;").fetchone()
                if not result or result[0].lower() != "ok":
                    raise sqlite3.DatabaseError("integrity check failed")
        except sqlite3.DatabaseError:
            self._resetDatabase()

    def _resetDatabase(self) -> None:
        """Delete the existing database file to allow recreation."""
        if os.path.exists(self.dbPath):
            os.remove(self.dbPath)

    def _initializeDatabase(self) -> None:
        """Create the chat history table and supporting indexes."""
        with sqlite3.connect(self.dbPath) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chatHistory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    chatId TEXT,
                    username TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'bot')),
                    message TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idxChatHistoryUsernameTimestamp
                ON chatHistory (username, timestamp DESC)
                """
            )

    def addMessage(
        self,
        username: str,
        role: str,
        message: str,
        chatId: Optional[Any] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Persist a message record.

        Args:
            username: Telegram username associated with the message.
            role: Role of the speaker, either ``user`` or ``bot``.
            message: Message body.
            chatId: Telegram chat identifier if available.
            timestamp: Timestamp for the message; defaults to current UTC time.

        Raises:
            ValueError: If ``role`` is neither ``user`` nor ``bot``.
        """
        if role not in {"user", "bot"}:
            raise ValueError("role must be either 'user' or 'bot'")

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        with sqlite3.connect(self.dbPath) as connection:
            connection.execute(
                """
                INSERT INTO chatHistory (timestamp, chatId, username, role, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    timestamp.isoformat(),
                    None if chatId is None else str(chatId),
                    username,
                    role,
                    message,
                ),
            )

    def getRecentMessages(self, username: str, limit: int) -> List[Dict[str, str]]:
        """Retrieve the latest messages for a username.

        Args:
            username: Telegram username to filter by.
            limit: Maximum number of rows to return.

        Returns:
            A list of dictionaries for each message ordered from newest to oldest.
        """
        if limit <= 0:
            return []

        with sqlite3.connect(self.dbPath) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.execute(
                """
                SELECT timestamp, chatId, username, role, message
                FROM chatHistory
                WHERE username = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (username, limit),
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def getUsernames(self) -> List[str]:
        """Return distinct usernames stored in the chat history.

        Returns:
            A list of usernames ordered alphabetically.
        """
        with sqlite3.connect(self.dbPath) as connection:
            cursor = connection.execute(
                """
                SELECT DISTINCT username
                FROM chatHistory
                ORDER BY username ASC
                """
            )
            rows = cursor.fetchall()

        return [row[0] for row in rows]
