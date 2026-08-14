"""
Nekomimi LLM API client module.

This module provides the Neko class, which handles communication with
LLM providers to generate cat-girl persona responses based on user
input and conversation history.

Supported providers:

- ``DeepSeek`` (default): OpenAI-compatible ``chat/completions`` endpoint.
- ``Opencode Zen`` (legacy): OpenAI ``responses`` endpoint.

Configuration lives in ``core/config/config.yaml`` under an ``llm``
section (see ``configExample.yaml`` for the exact shape).
"""

from os import path as osPath
from typing import Optional, AsyncGenerator
from json import loads as jsonLoads, JSONDecodeError

from time import time, localtime, asctime
from aiohttp import ClientSession as aioHttpClientSession
from aiohttp import ClientTimeout as aioHttpClientTimeout
from loguru import logger
from yaml import safe_load as yamlSafeLoad

from core.chatHistory import ChatHistory

currentDir = osPath.dirname(osPath.realpath(__file__))

#: Default number of recent messages used as conversation context.
DEFAULT_HISTORY_LIMIT = 20


class Neko:
    """Nekomimi LLM API client for chat interactions.

    This class handles communication with the LLM API provider to generate
    cat-girl persona responses. It supports both synchronous and streaming
    response modes.

    Attributes:
        chatHistory: Reference to the chat history storage instance.
        llmConfig: Configuration settings loaded from config.yaml ``llm`` section.
        nekomimiPrompt: Prompt templates loaded from the language-specific YAML file.
        apiProvider: Provider name deciding which request/response format to use.
        postUrl: API endpoint URL for the configured provider.
        postHeaders: HTTP headers including authorization token.
    """

    def __init__(self, chatHistory: ChatHistory, configPath: Optional[str] = None) -> None:
        """Initialize the Nekomimi LLM client.

        Loads configuration files and sets up the API connection parameters.

        Args:
            chatHistory: Chat history storage instance for context retrieval.
            configPath: Optional path to ``config.yaml``; defaults to
                ``core/config/config.yaml``. Useful for testing.

        Raises:
            FileNotFoundError: If configuration files are missing.
            KeyError: If required configuration keys are not found.
            ValueError: If an unsupported language is configured.
            RuntimeError: If the configured ``api_key`` is missing or empty.
            Exception: If configuration loading fails for any other reason.
        """
        self.logger = logger.bind(module="neko")
        self.chatHistory = chatHistory

        if configPath is None:
            configPath = currentDir + "/config/config.yaml"

        try:
            with open(configPath, "r", encoding="utf-8") as yamlConfig:
                fullConfig = yamlSafeLoad(yamlConfig)
            self.llmConfig = fullConfig["llm"]

            language = str(self.llmConfig.get("language", "CN"))
            if language == "CN":
                promptFile = "prompt_CN.yaml"
            elif language == "EN":
                promptFile = "prompt_EN.yaml"
            else:
                raise ValueError(
                    f"Unsupported language: {language}. Supported values are 'CN' and 'EN'."
                )

            with open(currentDir + "/config/" + promptFile, "r", encoding="utf-8") as yamlPrompt:
                self.nekomimiPrompt = yamlSafeLoad(yamlPrompt)

            self.logger.info("Configuration loaded successfully.")
        except Exception as e:
            self.logger.error("Failed to load configuration: " + str(e))
            raise

        apiKey = str(self.llmConfig.get("api_key", "")).strip()
        if not apiKey:
            raise RuntimeError("未配置 LLM api_key（core/config/config.yaml 的 llm.api_key）")

        self.apiProvider = str(self.llmConfig.get("api_provider", "DeepSeek")).strip()
        if self.apiProvider == "DeepSeek":
            baseUrl = str(
                self.llmConfig.get("base_url", "https://api.deepseek.com")
            ).rstrip("/")
            self.postUrl = baseUrl + "/chat/completions"
        else:
            # Legacy Responses API path (e.g. "Opencode Zen").
            with open(currentDir + "/config/inf.yaml", "r", encoding="utf-8") as yamlInf:
                inf = yamlSafeLoad(yamlInf)
            self.postUrl = inf["API Provider URL"][self.apiProvider]

        self.postHeaders = {
            "Authorization": "Bearer " + apiKey,
            "Content-Type": "application/json",
        }

    def _timeout(self) -> aioHttpClientTimeout:
        """Build the aiohttp timeout from the configured ``timeout_seconds``."""
        return aioHttpClientTimeout(total=int(self.llmConfig.get("timeout_seconds", 60)))

    def _generateSystemPrompt(self, userName: str, historyLimit: int) -> str:
        """Generate the persona/system prompt with context and current time.

        Args:
            userName: The identity used to scope chat history lookup.
            historyLimit: Number of recent messages to inject as context.

        Returns:
            The filled ``setNeko`` prompt string.
        """
        setNekoPrompt = self.nekomimiPrompt["setNeko"]
        setNekoPrompt = setNekoPrompt.replace(
            "{chatHistory}",
            str(self.chatHistory.getRecentMessages(userName, historyLimit)),
        )
        setNekoPrompt = setNekoPrompt.replace("{time}", asctime(localtime(time())))
        return setNekoPrompt

    def _generateUserPrompt(self, request: str) -> str:
        """Generate the user message prompt from the incoming request.

        Args:
            request: The user's message to respond to.

        Returns:
            The ``askNeko`` template concatenated with the request.
        """
        return self.nekomimiPrompt["askNeko"] + request

    def _buildDeepSeekPayload(
        self, userName: str, request: str, historyLimit: int, stream: bool
    ) -> dict:
        """Build the OpenAI-compatible chat/completions payload for DeepSeek."""
        payload = {
            "model": self.llmConfig["model"],
            "messages": [
                {
                    "role": "system",
                    "content": self._generateSystemPrompt(userName, historyLimit),
                },
                {"role": "user", "content": self._generateUserPrompt(request)},
            ],
            "stream": stream,
            "max_tokens": int(self.llmConfig.get("max_tokens", 1024)),
        }
        if self.llmConfig.get("reasoning_effort"):
            payload["reasoning_effort"] = str(self.llmConfig["reasoning_effort"])
        thinking = self.llmConfig.get("thinking")
        if thinking:
            payload["thinking"] = thinking
        return payload

    def _buildResponsesPayload(
        self, userName: str, request: str, historyLimit: int, stream: bool
    ) -> dict:
        """Build the legacy Responses API payload (single-string ``input``)."""
        prompt = self._generateSystemPrompt(userName, historyLimit) + self._generateUserPrompt(request)
        return {
            "model": self.llmConfig["model"],
            "input": prompt,
            "stream": stream,
        }

    # ------------------------------------------------------------------
    # Response parsing (pure helpers kept static for testability)
    # ------------------------------------------------------------------

    @staticmethod
    def _parseChatCompletions(resp: dict) -> str:
        """Extract the assistant text from a chat/completions response.

        ``reasoning_content`` is intentionally ignored: only the visible
        ``content`` field is returned.
        """
        try:
            content = resp["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return ""
        return str(content).strip() if content else ""

    @staticmethod
    def _parseChatCompletionsStream(line: str) -> Optional[str]:
        """Parse a single SSE line from a chat/completions stream.

        Returns the text delta if present, otherwise ``None``. ``[DONE]``,
        metadata, invalid JSON, and ``reasoning_content`` all yield ``None``.
        """
        line = line.strip()
        if not line.startswith("data:"):
            return None

        payload = line[5:].strip()
        if payload == "[DONE]":
            return None

        try:
            obj = jsonLoads(payload)
        except JSONDecodeError:
            return None

        try:
            delta = obj["choices"][0]["delta"].get("content")
        except (KeyError, IndexError, TypeError):
            return None

        return delta if delta else None

    @staticmethod
    def _parseText(resp: dict) -> str:
        """Parse the legacy Responses API response to extract text content."""
        texts = []
        for item in resp.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        texts.append(content.get("text"))
        return "\n".join(texts)

    @staticmethod
    def _parseTextStream(line: str) -> Optional[str]:
        """Parse a single SSE line from a legacy Responses API stream."""
        line = line.strip()
        if not line.startswith("data:"):
            return None

        payload = line[5:].strip()
        if payload == "[DONE]":
            return None

        try:
            obj = jsonLoads(payload)
        except JSONDecodeError:
            return None

        if obj.get("type") == "response.output_text.delta":
            return obj.get("delta")
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def askNeko(
        self, userName: str, request: str, historyLimit: int = DEFAULT_HISTORY_LIMIT
    ) -> str:
        """Send an async request to the LLM and return the complete response.

        Args:
            userName: The identity used to scope chat history lookup.
            request: The user's message to send to the LLM.
            historyLimit: Number of recent messages injected as context.

        Returns:
            The complete text response from the LLM, or an empty string
            if the request fails.
        """
        self.logger.info("Asking Neko...")

        if self.apiProvider == "DeepSeek":
            data = self._buildDeepSeekPayload(userName, request, historyLimit, stream=False)
            parser = self._parseChatCompletions
        else:
            data = self._buildResponsesPayload(userName, request, historyLimit, stream=False)
            parser = self._parseText

        async with aioHttpClientSession(timeout=self._timeout()) as session:
            async with session.post(self.postUrl, json=data, headers=self.postHeaders) as res:
                if res.status != 200:
                    body = await res.text()
                    self.logger.error(f"LLM API returned status {res.status}: {body}")
                    return ""
                return parser(await res.json())

    async def askNekoStream(
        self, userName: str, request: str, historyLimit: int = DEFAULT_HISTORY_LIMIT
    ) -> AsyncGenerator[str, None]:
        """Send an async streaming request to the LLM.

        Yields text deltas as they arrive.

        Args:
            userName: The identity used to scope chat history lookup.
            request: The user's message to send to the LLM.
            historyLimit: Number of recent messages injected as context.

        Yields:
            Text deltas as they are received from the streaming response.
        """
        self.logger.info("Asking Neko with streaming response...")

        if self.apiProvider == "DeepSeek":
            data = self._buildDeepSeekPayload(userName, request, historyLimit, stream=True)
            parser = self._parseChatCompletionsStream
        else:
            data = self._buildResponsesPayload(userName, request, historyLimit, stream=True)
            parser = self._parseTextStream

        try:
            async with aioHttpClientSession(timeout=self._timeout()) as session:
                async with session.post(self.postUrl, json=data, headers=self.postHeaders) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        self.logger.error(
                            f"LLM API returned status {resp.status}: {body}"
                        )
                        return

                    async for rawLine in resp.content:
                        line = rawLine.decode("utf-8").strip()
                        if not line:
                            continue

                        delta = parser(line)
                        if delta:
                            yield delta
        except Exception as e:
            self.logger.error(f"Streaming request failed: {e}")
            return
