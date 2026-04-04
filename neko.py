"""
Nekomimi LLM API client module.

This module provides the Neko class, which handles communication with
LLM providers to generate cat-girl persona responses based on
user input and conversation history.
"""

from os import path as osPath
from typing import Optional, AsyncGenerator
from json import loads as jsonLoads, JSONDecodeError

from time import time, localtime, asctime
from aiohttp import ClientSession as aioHttpClientSession
from loguru import logger
from yaml import safe_load as yamlSafeLoad

from chatHistory import ChatHistory

currentDir = osPath.dirname(osPath.realpath(__file__))


class Neko:
    """Nekomimi LLM API client for chat interactions.

    This class handles communication with the LLM API provider to generate
    cat-girl persona responses. It supports both synchronous and streaming
    response modes.

    Attributes:
        chatHistory: Reference to the chat history storage instance.
        nekomimiConfig: Configuration settings loaded from config.yaml.
        nekomimiPrompt: Prompt templates loaded from the language-specific YAML file.
        postUrl: API endpoint URL for the configured provider.
        postHeaders: HTTP headers including authorization token.
    """

    def __init__(self, chatHistory: ChatHistory) -> None:
        """Initialize the Nekomimi LLM client.

        Loads configuration files and sets up the API connection parameters.

        Args:
            chatHistory: Chat history storage instance for context retrieval.

        Raises:
            FileNotFoundError: If configuration files are missing.
            KeyError: If required configuration keys are not found.
            ValueError: If an unsupported language is configured.
            Exception: If configuration loading fails for any other reason.
        """
        self.logger = logger.bind(module="neko")
        self.chatHistory = chatHistory

        try:
            with open(currentDir + "/config/config.yaml", "r") as yamlConfig:
                self.nekomimiConfig = yamlSafeLoad(yamlConfig)["Nekomimi"]

            with open(currentDir + "/config/inf.yaml", "r") as yamlInf:
                self.inf = yamlSafeLoad(yamlInf)

            if self.nekomimiConfig["Language"] == "CN":
                with open(currentDir + "/config/prompt_CN.yaml", "r") as yamlPrompt:
                    self.nekomimiPrompt = yamlSafeLoad(yamlPrompt)
            elif self.nekomimiConfig["Language"] == "EN":
                with open(currentDir + "/config/prompt_EN.yaml", "r") as yamlPrompt:
                    self.nekomimiPrompt = yamlSafeLoad(yamlPrompt)
            else:
                raise ValueError(
                    f"Unsupported language: {self.nekomimiConfig['Language']}. "
                    "Supported values are 'CN' and 'EN'."
                )

            self.logger.info("Configuration loaded successfully.")
        except Exception as e:
            self.logger.error("Failed to load configuration: " + str(e))
            raise

        self.postUrl = self.inf["API Provider URL"][self.nekomimiConfig["API Provider"]]
        self.postHeaders = {
            "Authorization": "Bearer " + self.nekomimiConfig["Token"],
            "Content-Type": "application/json",
        }

    def __generatePrompt(self, userName: str, request: str) -> str:
        """Generate the complete prompt with context and user request.

        Combines the persona setup prompt, chat history context, current time,
        and the user's request into a single prompt string.

        Args:
            userName: The name of the user asking the question.
            request: The user's message to respond to.

        Returns:
            The complete prompt string ready for LLM submission.
        """
        self.logger.info("Generating prompt...")

        setNekoPrompt = self.nekomimiPrompt["setNeko"]
        setNekoPrompt = setNekoPrompt.replace(
            "{chatHistory}", str(self.chatHistory.getRecentMessages(userName, 20))
        )
        setNekoPrompt = setNekoPrompt.replace("{time}", asctime(localtime(time())))

        nekoPrompt = setNekoPrompt + self.nekomimiPrompt["askNeko"] + request
        self.logger.debug("Generated prompt: " + nekoPrompt)

        return nekoPrompt

    def __parseText(self, resp: dict) -> str:
        """Parse the LLM response to extract text content.

        Extracts all output_text content from the API response structure.

        Args:
            resp: The JSON response dictionary from the LLM API.

        Returns:
            The concatenated text content joined by newlines.
        """
        texts = []

        for item in resp.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        texts.append(content.get("text"))

        return "\n".join(texts)

    def __parseTextStream(self, line: str) -> Optional[str]:
        """Parse a single line from the streaming response.

        Processes Server-Sent Events (SSE) format data lines and extracts
        text deltas from the streaming LLM response.

        Args:
            line: A single line from the streaming response.

        Returns:
            The text delta if present, or None if the line doesn't contain
            text content (e.g., metadata, completion signal, or invalid data).
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
            self.logger.error("Failed to parse JSON: " + payload)
            return None

        if obj.get("type") == "response.output_text.delta":
            return obj.get("delta")

        return None

    async def askNeko(self, userName: str, request: str) -> str:
        """Send an async request to the LLM and return the response.

        Makes an asynchronous HTTP POST request to the LLM API and waits
        for the complete response.

        Args:
            userName: The name of the user asking the question.
            request: The user's message to send to the LLM.

        Returns:
            The complete text response from the LLM, or an empty string
            if the request fails.

        Raises:
            aiohttp.ClientError: If the HTTP request fails.
        """
        self.logger.info("Asking Neko...")

        data = {
            "model": self.nekomimiConfig["Model"],
            "input": self.__generatePrompt(userName, request),
        }

        async with aioHttpClientSession() as session:
            async with session.post(
                self.postUrl, json=data, headers=self.postHeaders
            ) as res:
                if res.status != 200:
                    body = await res.text()
                    self.logger.error(f"LLM API returned status {res.status}: {body}")
                    return ""
                return self.__parseText(await res.json())

    async def askNekoStream(
        self, userName: str, request: str
    ) -> AsyncGenerator[str, None]:
        """Send an async streaming request to the LLM.

        Makes an asynchronous HTTP POST request with streaming enabled and
        yields text deltas as they arrive.

        Args:
            userName: The name of the user asking the question.
            request: The user's message to send to the LLM.

        Yields:
            Text deltas as they are received from the streaming response.

        Raises:
            aiohttp.ClientError: If the HTTP request fails.
        """
        self.logger.info("Asking Neko with streaming response...")

        data = {
            "model": self.nekomimiConfig["Model"],
            "input": self.__generatePrompt(userName, request),
            "stream": True,
        }

        try:
            async with aioHttpClientSession() as session:
                async with session.post(
                    self.postUrl, json=data, headers=self.postHeaders
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        self.logger.error(
                            f"LLM API returned status {resp.status}: {body}"
                        )
                        return

                    async for raw_line in resp.content:
                        line = raw_line.decode("utf-8").strip()
                        if not line:
                            continue

                        delta = self.__parseTextStream(line)

                        if delta:
                            yield delta
        except Exception as e:
            self.logger.error(f"Streaming request failed: {e}")
            return
