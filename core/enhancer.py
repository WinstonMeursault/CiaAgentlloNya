"""
Enhancement orchestration for the nekomimi bot.

"SearchEnhancer" wires optional web search (two-pass judge + provider) and RAG
knowledge retrieval into the answer pipeline as *background information*,
without importing "core.neko" (avoiding circular imports). "Neko" passes its
own "_judgeNeedsSearch" bound method in as "judgeFn".
"""

from typing import Any, Awaitable, Callable, Dict, Optional

from loguru import logger

from core.knowledge import KnowledgeBase
from core.search import SearchProvider

#: Judge callback signature: (request) -> {"needs_search": bool, "query": str}.
JudgeFn = Callable[[str], Awaitable[Dict[str, Any]]]


class SearchEnhancer:
    """Orchestrates optional search and RAG retrieval before answering."""

    def __init__(
        self,
        searchProvider: Optional[SearchProvider] = None,
        knowledgeBase: Optional[KnowledgeBase] = None,
        judgeFn: Optional[JudgeFn] = None,
    ) -> None:
        """Wire the optional search provider, RAG base, and judge callback.

        Args:
            searchProvider: Search backend implementing "SearchProvider";
                "None" disables web search.
            knowledgeBase: RAG backend; "None" disables knowledge retrieval.
            judgeFn: Async judge callback deciding whether to search.
        """
        self.logger = logger.bind(module="enhancer")
        self.searchProvider = searchProvider
        self.knowledgeBase = knowledgeBase
        self.judgeFn = judgeFn

    async def search(self, request: str) -> str:
        """Run the two-pass search and return a formatted search block (or "").

        Failure at any step degrades to an empty block so the persona answer is
        never blocked by the search path.
        """
        if not self.searchProvider or not self.judgeFn:
            return ""
        try:
            verdict = await self.judgeFn(request)
        except Exception as exc:
            self.logger.warning(f"Search judge failed, skipping search: {exc}")
            return ""
        if not verdict or not verdict.get("needs_search", False):
            self.logger.info("搜索判需：不需要搜索")
            return ""
        query = str(verdict.get("query", "")).strip()
        if not query:
            self.logger.info("搜索判需：query 为空，跳过搜索")
            return ""
        self.logger.info(f"搜索判需：需要搜索 → query={query!r}")
        try:
            results = await self.searchProvider.search(query)
        except Exception as exc:
            self.logger.warning(f"Search provider failed: {exc}")
            return ""
        self.logger.info(f"联网搜索完成：{len(results)} 条结果")
        return self.searchProvider.format(results)

    def retrieve(self, request: str) -> str:
        """Run RAG retrieval and return a formatted knowledge block (or "")."""
        if not self.knowledgeBase:
            return ""
        try:
            results = self.knowledgeBase.retrieve(request)
        except Exception as exc:
            self.logger.warning(f"RAG retrieval failed: {exc}")
            return ""
        if results:
            self.logger.info(f"RAG 检索命中：{len(results)} 条")
        return self.knowledgeBase.format(results)
