"""
Web search provider abstraction for the nekomimi bot.

Defines the "SearchProvider" interface and a SearXNG implementation using its
public JSON API. Provider selection is config-driven (see
"core/config/configExample.yaml" -> "llm.enhance.search").
"""

from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import aiohttp
from loguru import logger

#: User-Agent sent to SearXNG instances (public instances may require one).
USER_AGENT = "CiaBotlloNya/1.0 (+https://github.com/WinstonMeursault/CiaBotlloNya)"


class SearchProvider:
    """Minimal search-provider interface implemented by concrete backends."""

    async def search(self, query: str) -> List[Dict[str, str]]:
        """Return a list of result dicts (title/url/content/engine)."""
        raise NotImplementedError

    def format(self, results: List[Dict[str, str]]) -> str:
        """Format results into a single background-information block."""
        raise NotImplementedError


class SearXNGSearch(SearchProvider):
    """Search backend using a SearXNG instance's JSON API."""

    def __init__(
        self,
        instanceUrl: str = "https://searx.be",
        language: str = "zh-CN",
        maxResults: int = 3,
        timeoutSeconds: int = 10,
    ) -> None:
        self.instanceUrl = instanceUrl.rstrip("/")
        self.language = language
        self.maxResults = maxResults
        self.timeoutSeconds = timeoutSeconds
        self.logger = logger.bind(module="search")

    def buildUrl(self, query: str) -> str:
        """Build the JSON search URL for a query (pure, testable)."""
        params = {"q": query, "format": "json"}
        if self.language:
            params["language"] = self.language
        return f"{self.instanceUrl}/search?{urlencode(params)}"

    async def search(self, query: str) -> List[Dict[str, str]]:
        """Query SearXNG and return up to maxResults result dicts.

        Any HTTP/parse error degrades to an empty list so the persona answer
        is never blocked by the search path.
        """
        url = self.buildUrl(query)
        timeout = aiohttp.ClientTimeout(total=self.timeoutSeconds)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers={"User-Agent": USER_AGENT}) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        self.logger.error(
                            f"SearXNG returned status {resp.status}: {body[:200]}"
                        )
                        return []
                    data = await resp.json()
        except Exception as exc:
            self.logger.warning(f"SearXNG request failed: {exc}")
            return []

        results: List[Dict[str, str]] = []
        for item in (data.get("results") or [])[: self.maxResults]:
            results.append(
                {
                    "title": str(item.get("title", "")).strip(),
                    "url": str(item.get("url", "")).strip(),
                    "content": str(item.get("content", "")).strip(),
                    "engine": str(item.get("engine", "")).strip(),
                }
            )
        return results

    @staticmethod
    def format(results: List[Dict[str, str]]) -> str:
        """Format results into a numbered background-information block."""
        if not results:
            return ""
        blocks: List[str] = []
        for index, result in enumerate(results, start=1):
            title = result.get("title") or result.get("url") or f"结果 {index}"
            content = result.get("content", "")
            url = result.get("url", "")
            if url:
                blocks.append(f"[{index}] {title}\n{content}\n来源: {url}")
            else:
                blocks.append(f"[{index}] {title}\n{content}")
        return "\n\n".join(blocks)


def makeSearchProvider(config: Dict[str, Any]) -> Optional[SearchProvider]:
    """Build a search provider from the "enhance.search" config dict.

    Returns None when search is disabled or the provider is unknown, so the
    search path can always degrade gracefully.
    """
    if not config or not config.get("enabled", False):
        return None
    provider = str(config.get("provider", "searxng")).lower()
    if provider == "searxng":
        return SearXNGSearch(
            instanceUrl=str(config.get("instance_url", "https://searx.be")),
            language=str(config.get("language", "zh-CN")),
            maxResults=int(config.get("max_results", 3)),
            timeoutSeconds=int(config.get("timeout_seconds", 10)),
        )
    logger.warning(f"Unknown search provider '{provider}'; search disabled.")
    return None
