"""
Web search provider abstraction for the nekomimi bot.

Defines the "SearchProvider" interface and a SearXNG implementation. Public
SearXNG instances almost never expose the JSON API (they return HTML or a
browser-verification challenge), so the client reads the raw response and
falls back to parsing the HTML result markup when JSON is unavailable.
"""

import json
import re
from html import unescape
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import aiohttp
from loguru import logger

#: User-Agent sent to SearXNG instances (some gate non-browser clients).
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


class SearchProvider:
    """Minimal search-provider interface implemented by concrete backends."""

    async def search(self, query: str) -> List[Dict[str, str]]:
        """Return a list of result dicts (title/url/content/engine)."""
        raise NotImplementedError

    def format(self, results: List[Dict[str, str]]) -> str:
        """Format results into a single background-information block."""
        raise NotImplementedError


class SearXNGSearch(SearchProvider):
    """Search backend using a SearXNG instance (JSON first, HTML fallback)."""

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
        """Build the search URL for a query (pure, testable)."""
        params = {"q": query, "format": "json"}
        if self.language:
            params["language"] = self.language
        return f"{self.instanceUrl}/search?{urlencode(params)}"

    async def search(self, query: str) -> List[Dict[str, str]]:
        """Query SearXNG and return up to maxResults result dicts.

        Tries the JSON API first, then falls back to parsing the HTML result
        markup. Any HTTP/parse error degrades to an empty list so the persona
        answer is never blocked by the search path.
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
                    raw = await resp.text()
        except Exception as exc:
            self.logger.warning(f"SearXNG request failed: {exc}")
            return []

        # 1) JSON API (rarely enabled on public instances).
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            data = None
        if isinstance(data, dict):
            return self._parseJsonResults(data)

        # 2) HTML fallback (the common path for public instances).
        return self._parseHtmlResults(raw)[: self.maxResults]

    def _parseJsonResults(self, data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract result dicts from a SearXNG JSON response."""
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
    def _stripHtml(text: str) -> str:
        """Strip tags, unescape entities, and collapse whitespace."""
        text = re.sub(r"<br\s*/?>", " ", text or "")
        text = re.sub(r"<[^>]+>", "", text)
        text = unescape(text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _parseHtmlResults(htmlText: str) -> List[Dict[str, str]]:
        """Extract result dicts from SearXNG's HTML result markup."""
        results: List[Dict[str, str]] = []
        for article in re.findall(r"<article\b[^>]*>(.*?)</article>", htmlText, re.DOTALL):
            url = ""
            title = ""
            content = ""
            # Title link is usually the first link inside an <h3>.
            h3 = re.search(r"<h3[^>]*>(.*?)</h3>", article, re.DOTALL)
            block = h3.group(1) if h3 else article
            link = re.search(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
            if link:
                url = link.group(1)
                title = SearXNGSearch._stripHtml(link.group(2))
            # Content paragraph.
            contentMatch = re.search(
                r'<p\b[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</p>',
                article,
                re.DOTALL,
            )
            if contentMatch:
                content = SearXNGSearch._stripHtml(contentMatch.group(1))
            if not url and not title and not content:
                continue
            results.append(
                {"title": title, "url": url, "content": content, "engine": ""}
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
