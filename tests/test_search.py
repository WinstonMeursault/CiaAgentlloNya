"""Unit tests for core.search (SearXNG provider + factory)."""

import asyncio
import json

from core import search as search_module
from core.search import SearXNGSearch, makeSearchProvider


def _run(coro):
    return asyncio.run(coro)


class _Resp:
    def __init__(self, status=200, body="{}"):
        self.status = status
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self):
        return json.loads(self._body)

    async def text(self):
        return self._body


class _Session:
    def __init__(self, timeout=None):
        self.requested = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def get(self, url, headers=None):
        self.requested = (url, headers)
        return _Session.next_resp


class TestBuildUrl:
    def test_with_language(self):
        p = SearXNGSearch(instanceUrl="https://searx.be/", language="zh-CN")
        assert p.buildUrl("上海 天气") == "https://searx.be/search?q=%E4%B8%8A%E6%B5%B7+%E5%A4%A9%E6%B0%94&format=json&language=zh-CN"

    def test_without_language(self):
        p = SearXNGSearch(instanceUrl="https://x.example", language="")
        assert p.buildUrl("hi") == "https://x.example/search?q=hi&format=json"


class TestFormat:
    def test_empty(self):
        assert SearXNGSearch.format([]) == ""

    def test_with_url(self):
        out = SearXNGSearch.format([{"title": "t", "url": "u", "content": "c"}])
        assert "[1] t\nc\n来源: u" in out

    def test_without_url(self):
        out = SearXNGSearch.format([{"title": "t", "content": "c"}])
        assert "来源" not in out
        assert "[1] t\nc" in out


class TestParseHtmlResults:
    def test_parses_article(self):
        html = (
            '<article class="result">'
            '<h3><a href="https://e.com/p" rel="noreferrer">Title &amp; Co</a></h3>'
            '<p class="content">Some <b>bold</b> text.<br>More</p>'
            '</article>'
        )
        assert SearXNGSearch._parseHtmlResults(html) == [
            {
                "title": "Title & Co",
                "url": "https://e.com/p",
                "content": "Some bold text. More",
                "engine": "",
            }
        ]

    def test_no_articles_returns_empty(self):
        assert SearXNGSearch._parseHtmlResults("<html><body>challenge</body></html>") == []


class TestSearch:
    def _patch(self, monkeypatch, resp):
        _Session.next_resp = resp
        monkeypatch.setattr("core.search.aiohttp.ClientSession", _Session)

    def test_happy_path_json(self, monkeypatch):
        body = json.dumps({"results": [{"title": "t", "url": "u", "content": "c", "engine": "e"}]})
        self._patch(monkeypatch, _Resp(200, body))
        results = _run(SearXNGSearch().search("hello"))
        assert results == [{"title": "t", "url": "u", "content": "c", "engine": "e"}]

    def test_truncates_to_max_results(self, monkeypatch):
        body = json.dumps({"results": [{"title": f"t{i}"} for i in range(10)]})
        self._patch(monkeypatch, _Resp(200, body))
        results = _run(SearXNGSearch(maxResults=3).search("hello"))
        assert len(results) == 3

    def test_html_fallback(self, monkeypatch):
        html = (
            '<article class="result">'
            '<h3><a href="https://e.com/p">HTML Title</a></h3>'
            '<p class="content">HTML body</p>'
            '</article>'
        )
        self._patch(monkeypatch, _Resp(200, html))
        results = _run(SearXNGSearch().search("hello"))
        assert results == [
            {"title": "HTML Title", "url": "https://e.com/p", "content": "HTML body", "engine": ""}
        ]

    def test_non_200_returns_empty(self, monkeypatch):
        self._patch(monkeypatch, _Resp(500, "err"))
        assert _run(SearXNGSearch().search("x")) == []

    def test_exception_returns_empty(self, monkeypatch):
        class BoomSession:
            def __init__(self, timeout=None):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            def get(self, url, headers=None):
                raise RuntimeError("net down")

        monkeypatch.setattr("core.search.aiohttp.ClientSession", BoomSession)
        assert _run(SearXNGSearch().search("x")) == []


class TestMakeSearchProvider:
    def test_empty_disabled(self):
        assert makeSearchProvider({}) is None

    def test_explicit_disabled(self):
        assert makeSearchProvider({"enabled": False}) is None

    def test_searxng(self):
        p = makeSearchProvider(
            {
                "enabled": True,
                "provider": "searxng",
                "instance_url": "https://s.be",
                "language": "en",
                "max_results": 5,
                "timeout_seconds": 7,
            }
        )
        assert isinstance(p, SearXNGSearch)
        assert p.instanceUrl == "https://s.be"
        assert p.maxResults == 5
        assert p.timeoutSeconds == 7

    def test_unknown_provider(self):
        assert makeSearchProvider({"enabled": True, "provider": "bing"}) is None
