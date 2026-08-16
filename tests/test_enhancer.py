"""Unit tests for core.enhancer.SearchEnhancer."""

import asyncio

from core.enhancer import SearchEnhancer


def _run(coro):
    return asyncio.run(coro)


def _judge(needs, query):
    async def judge(request):
        return {"needs_search": needs, "query": query}

    return judge


class _FakeSearchProvider:
    def __init__(self) -> None:
        self.searched = []
        self.results = []
        self.raiseOnSearch = False

    async def search(self, query):
        self.searched.append(query)
        if self.raiseOnSearch:
            raise RuntimeError("search down")
        return self.results

    def format(self, results):
        return "SEARCH:" + ";".join(r.get("title", "") for r in results)


class _FakeKnowledgeBase:
    def __init__(self) -> None:
        self.retrieved = []
        self.results = []

    def retrieve(self, query):
        self.retrieved.append(query)
        return self.results

    def format(self, results):
        return "KNOWLEDGE:" + str(len(results))


class TestSearch:
    def test_disabled_without_provider(self):
        e = SearchEnhancer(searchProvider=None, judgeFn=_judge(True, "q"))
        assert _run(e.search("x")) == ""

    def test_disabled_without_judge(self):
        e = SearchEnhancer(searchProvider=_FakeSearchProvider(), judgeFn=None)
        assert _run(e.search("x")) == ""

    def test_no_search_needed(self):
        provider = _FakeSearchProvider()
        e = SearchEnhancer(searchProvider=provider, judgeFn=_judge(False, ""))
        assert _run(e.search("hello")) == ""
        assert provider.searched == []

    def test_search_with_rewritten_query(self):
        provider = _FakeSearchProvider()
        provider.results = [{"title": "t1"}]
        e = SearchEnhancer(searchProvider=provider, judgeFn=_judge(True, "上海 天气"))
        assert _run(e.search("看看今天冷不冷")) == "SEARCH:t1"
        assert provider.searched == ["上海 天气"]

    def test_judge_raises(self):
        async def bad(request):
            raise RuntimeError("judge down")

        e = SearchEnhancer(searchProvider=_FakeSearchProvider(), judgeFn=bad)
        assert _run(e.search("x")) == ""

    def test_search_raises(self):
        provider = _FakeSearchProvider()
        provider.raiseOnSearch = True
        e = SearchEnhancer(searchProvider=provider, judgeFn=_judge(True, "q"))
        assert _run(e.search("x")) == ""

    def test_empty_query_skips_search(self):
        provider = _FakeSearchProvider()
        e = SearchEnhancer(searchProvider=provider, judgeFn=_judge(True, "  "))
        assert _run(e.search("x")) == ""
        assert provider.searched == []


class TestRetrieve:
    def test_disabled(self):
        e = SearchEnhancer(knowledgeBase=None)
        assert e.retrieve("x") == ""

    def test_retrieve(self):
        kb = _FakeKnowledgeBase()
        kb.results = [{"text": "a"}]
        e = SearchEnhancer(knowledgeBase=kb)
        assert e.retrieve("hello") == "KNOWLEDGE:1"
        assert kb.retrieved == ["hello"]

    def test_retrieve_raises(self):
        class Boom:
            def retrieve(self, query):
                raise RuntimeError("kb down")

            def format(self, results):
                return "x"

        e = SearchEnhancer(knowledgeBase=Boom())
        assert e.retrieve("x") == ""
