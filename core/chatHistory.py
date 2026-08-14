"""
SQLite-backed chat history storage module.

This module provides the ChatHistory class for persisting and retrieving
conversation logs between users and the nekomimi assistant.
"""

import os
import shutil
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger


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
        self.logger = logger.bind(module="chatHistory")
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
        """Back up and delete the corrupted database file to allow recreation."""
        if os.path.exists(self.dbPath):
            backupPath = (
                self.dbPath
                + ".corrupt."
                + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            )
            self.logger.warning(
                f"Database corruption detected. Backing up to {backupPath} and recreating."
            )
            shutil.copy2(self.dbPath, backupPath)
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS groupChatHistory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    group_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'bot')),
                    nickname TEXT,
                    message TEXT NOT NULL
                )
                """
            )
            # 迁移：为旧库补充 nickname 列
            columns = [
                row[1]
                for row in connection.execute("PRAGMA table_info(groupChatHistory)").fetchall()
            ]
            if "nickname" not in columns:
                connection.execute("ALTER TABLE groupChatHistory ADD COLUMN nickname TEXT")
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idxGroupChatHistoryGroupTimestamp
                ON groupChatHistory (group_id, timestamp DESC)
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
            username: Username associated with the message.
            role: Role of the speaker, either ``user`` or ``bot``.
            message: Message body.
            chatId: Chat identifier if available.
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

    def addGroupMessage(
        self,
        groupId: str,
        userId: str,
        role: str,
        message: str,
        nickname: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Persist a group chat message into the shared group context buffer.

        Args:
            groupId: Group the message belongs to.
            userId: Speaker identifier (QQ number), or the bot's UIN for replies.
            role: Role of the speaker, either 'user' or 'bot'.
            message: Message body.
            nickname: Display name of the speaker (group card or nickname).
            timestamp: Timestamp for the message; defaults to current UTC time.

        Raises:
            ValueError: If ``role`` is neither 'user' nor 'bot'.
        """
        if role not in {"user", "bot"}:
            raise ValueError("role must be either 'user' or 'bot'")

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        with sqlite3.connect(self.dbPath) as connection:
            connection.execute(
                """
                INSERT INTO groupChatHistory (timestamp, group_id, user_id, role, nickname, message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp.isoformat(),
                    str(groupId),
                    str(userId),
                    role,
                    None if nickname is None else str(nickname),
                    message,
                ),
            )

    def getRecentGroupMessages(self, groupId: str, limit: int) -> List[Dict[str, str]]:
        """Retrieve the latest group chat messages for a group in chronological order.

        Args:
            groupId: Group to filter by.
            limit: Maximum number of rows to return.

        Returns:
            A list of dictionaries for each message ordered from oldest to newest.
        """
        if limit <= 0:
            return []

        with sqlite3.connect(self.dbPath) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.execute(
                """
                SELECT timestamp, group_id, user_id, role, nickname, message
                FROM (
                    SELECT timestamp, group_id, user_id, role, nickname, message
                    FROM groupChatHistory
                    WHERE group_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                )
                ORDER BY timestamp ASC
                """,
                (str(groupId), limit),
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]


    def getRecentMessages(self, username: str, limit: int) -> List[Dict[str, str]]:
        """Retrieve the latest messages for a username in chronological order.

        Args:
            username: Username to filter by.
            limit: Maximum number of rows to return.

        Returns:
            A list of dictionaries for each message ordered from oldest to newest.
        """
        if limit <= 0:
            return []

        with sqlite3.connect(self.dbPath) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.execute(
                """
                SELECT timestamp, chatId, username, role, message
                FROM (
                    SELECT timestamp, chatId, username, role, message
                    FROM chatHistory
                    WHERE username = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                )
                ORDER BY timestamp ASC
                """,
                (username, limit),
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def pruneMessages(self, username: str, maxRows: int) -> None:
        """Delete the oldest messages for a username, keeping the newest maxRows.

        Args:
            username: Username to prune.
            maxRows: Number of most recent rows to keep; 0 or negative means no pruning.
        """
        if maxRows <= 0:
            return
        with sqlite3.connect(self.dbPath) as connection:
            connection.execute(
                """
                DELETE FROM chatHistory
                WHERE id IN (
                    SELECT id FROM chatHistory
                    WHERE username = ?
                    ORDER BY timestamp DESC
                    LIMIT -1 OFFSET ?
                )
                """,
                (username, maxRows),
            )

    def pruneGroupMessages(self, groupId: str, maxRows: int) -> None:
        """Delete the oldest group messages for a group, keeping the newest maxRows.

        Args:
            groupId: Group to prune.
            maxRows: Number of most recent rows to keep; 0 or negative means no pruning.
        """
        if maxRows <= 0:
            return
        with sqlite3.connect(self.dbPath) as connection:
            connection.execute(
                """
                DELETE FROM groupChatHistory
                WHERE id IN (
                    SELECT id FROM groupChatHistory
                    WHERE group_id = ?
                    ORDER BY timestamp DESC
                    LIMIT -1 OFFSET ?
                )
                """,
                (str(groupId), maxRows),
            )

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
