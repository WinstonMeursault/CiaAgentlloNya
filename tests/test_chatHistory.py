"""Unit tests for the group chat context storage in core.chatHistory.ChatHistory."""

from datetime import datetime, timedelta, timezone

import pytest

from core.chatHistory import ChatHistory


class TestGroupChatHistory:
    def test_add_and_get_in_chronological_order(self, tmp_path):
        history = ChatHistory(dbPath=str(tmp_path / "chatHistory.db"))
        history.addGroupMessage("g1", "1001", "user", "第一条")
        history.addGroupMessage("g1", "1002", "user", "第二条")
        history.addGroupMessage("g1", "3997493374", "bot", "回复")

        rows = history.getRecentGroupMessages("g1", 50)
        assert [r["message"] for r in rows] == ["第一条", "第二条", "回复"]
        assert [r["role"] for r in rows] == ["user", "user", "bot"]
        assert rows[0]["user_id"] == "1001"
        assert rows[2]["user_id"] == "3997493374"

    def test_group_isolation(self, tmp_path):
        history = ChatHistory(dbPath=str(tmp_path / "chatHistory.db"))
        history.addGroupMessage("g1", "1001", "user", "a")
        history.addGroupMessage("g2", "2001", "user", "b")

        assert [r["message"] for r in history.getRecentGroupMessages("g1", 50)] == ["a"]
        assert [r["message"] for r in history.getRecentGroupMessages("g2", 50)] == ["b"]

    def test_limit_returns_most_recent(self, tmp_path):
        history = ChatHistory(dbPath=str(tmp_path / "chatHistory.db"))
        for i in range(5):
            history.addGroupMessage("g1", "u", "user", f"msg{i}")

        rows = history.getRecentGroupMessages("g1", 3)
        assert [r["message"] for r in rows] == ["msg2", "msg3", "msg4"]

    def test_zero_limit_returns_empty(self, tmp_path):
        history = ChatHistory(dbPath=str(tmp_path / "chatHistory.db"))
        history.addGroupMessage("g1", "u", "user", "x")
        assert history.getRecentGroupMessages("g1", 0) == []

    def test_invalid_role_raises(self, tmp_path):
        history = ChatHistory(dbPath=str(tmp_path / "chatHistory.db"))
        with pytest.raises(ValueError):
            history.addGroupMessage("g1", "u", "admin", "x")

class TestPrune:
    def test_prune_messages_keeps_newest(self, tmp_path):
        history = ChatHistory(dbPath=str(tmp_path / "chatHistory.db"))
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i in range(5):
            history.addMessage("u1", "user", f"m{i}", timestamp=base + timedelta(seconds=i))
        history.pruneMessages("u1", 3)
        rows = history.getRecentMessages("u1", 100)
        assert [r["message"] for r in rows] == ["m2", "m3", "m4"]

    def test_prune_group_messages_keeps_newest(self, tmp_path):
        history = ChatHistory(dbPath=str(tmp_path / "chatHistory.db"))
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i in range(5):
            history.addGroupMessage("g1", "u", "user", f"m{i}", timestamp=base + timedelta(seconds=i))
        history.pruneGroupMessages("g1", 2)
        rows = history.getRecentGroupMessages("g1", 100)
        assert [r["message"] for r in rows] == ["m3", "m4"]

    def test_prune_zero_does_nothing(self, tmp_path):
        history = ChatHistory(dbPath=str(tmp_path / "chatHistory.db"))
        history.addMessage("u1", "user", "x")
        history.pruneMessages("u1", 0)
        assert len(history.getRecentMessages("u1", 100)) == 1


class TestGroupNickname:
    def test_nickname_roundtrip(self, tmp_path):
        history = ChatHistory(dbPath=str(tmp_path / "chatHistory.db"))
        history.addGroupMessage("g1", "1001", "user", "hello", nickname="江星繁")
        rows = history.getRecentGroupMessages("g1", 10)
        assert rows[0]["nickname"] == "江星繁"

    def test_nickname_defaults_none(self, tmp_path):
        history = ChatHistory(dbPath=str(tmp_path / "chatHistory.db"))
        history.addGroupMessage("g1", "1001", "user", "hello")
        rows = history.getRecentGroupMessages("g1", 10)
        assert rows[0]["nickname"] is None
