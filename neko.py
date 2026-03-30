"""Nekomimi LLM API client module."""

from os import path as osPath
from typing import Optional, AsyncGenerator
from json import loads as jsonLoads, JSONDecodeError

from time import time, localtime, asctime
from aiohttp import ClientSession as aioHttpClientSession
from loguru import logger
from yaml import safe_load as yamlSafeLoad
from requests import post as requestsPost

from chatHistory import ChatHistory


class neko:
    """Nekomimi LLM API client for chat interactions.

    This class handles communication with the LLM API provider to generate
    cat-girl persona responses. It supports both synchronous and streaming
    response modes.

    Attributes:
        chatHistory: Reference to the chat history storage instance.
        userName: Current user's name for personalized interactions.
        nekomimiConfig: Configuration settings loaded from config.yaml.
        nekomimiPrompt: Prompt templates loaded from prompt_CN.yaml.
        postURL: API endpoint URL for the configured provider.
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
            Exception: If configuration loading fails for any other reason.
        """
        self.currentDir = osPath.dirname(osPath.realpath(__file__))
        self.logger = logger.bind(module="neko")
        self.chatHistory = chatHistory

        try:
            with open(self.currentDir + "/config/config.yaml", "r") as yamlConfig:
                self.nekomimiConfig = yamlSafeLoad(yamlConfig)["Nekomimi"]

            with open(self.currentDir + "/config/inf.yaml", "r") as yamlInf:
                self.inf = yamlSafeLoad(yamlInf)

            if self.nekomimiConfig["Language"] == "CN":
                with open(self.currentDir + "/config/prompt_CN.yaml", "r") as yamlPrompt:
                    self.nekomimiPrompt = yamlSafeLoad(yamlPrompt)
            elif self.nekomimiConfig["Language"] == "EN":
                with open(self.currentDir + "/config/prompt_EN.yaml", "r") as yamlPrompt:
                    self.nekomimiPrompt = yamlSafeLoad(yamlPrompt)

            self.logger.info("Configuration loaded successfully.")
        except Exception as e:
            self.logger.error("Failed to load configuration: " + str(e))
            raise e

        self.userName = self.nekomimiConfig["UserName"]
        self.logger.info(f"Initial user name: {self.userName}")
        self.postURL = self.inf["API Provider URL"][self.nekomimiConfig["API Provider"]]
        self.postHeaders = {
            "Authorization": "Bearer " + self.nekomimiConfig["Token"],
            "Content-Type": "application/json",
        }

    def __generatePrompt(self, request: str) -> str:
        """Generate the complete prompt with context and user request.

        Combines the persona setup prompt, chat history context, current time,
        and the user's request into a single prompt string.

        Args:
            request: The user's message to respond to.

        Returns:
            The complete prompt string ready for LLM submission.
        """
        self.logger.info("Generating prompt...")

        setNekoPrompt = self.nekomimiPrompt["setNeko"]
        setNekoPrompt = setNekoPrompt.replace(
            "{chatHistory}", str(self.chatHistory.getRecentMessages(self.userName, 20))
        )
        setNekoPrompt = setNekoPrompt.replace("{time}", asctime(localtime(time())))

        return setNekoPrompt + self.nekomimiPrompt["askNeko"] + request

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

    def __parseTextSteam(self, line: str) -> Optional[str]:
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

    def askNeko(self, request: str) -> str:
        """Send a synchronous request to the LLM and return the response.

        Makes a blocking HTTP POST request to the LLM API and waits for
        the complete response.

        Args:
            request: The user's message to send to the LLM.

        Returns:
            The complete text response from the LLM.

        Raises:
            requests.RequestException: If the HTTP request fails.
        """
        self.logger.info("Asking Neko...")

        data = {
            "model": self.nekomimiConfig["Model"],
            "input": self.__generatePrompt(request),
        }

        res = requestsPost(self.postURL, json=data, headers=self.postHeaders)
        return self.__parseText(res.json())

    async def askNekoStream(self, request: str) -> AsyncGenerator[str, None]:
        """Send an async streaming request to the LLM.

        Makes an asynchronous HTTP POST request with streaming enabled and
        yields text deltas as they arrive.

        Args:
            request: The user's message to send to the LLM.

        Yields:
            Text deltas as they are received from the streaming response.

        Raises:
            aiohttp.ClientError: If the HTTP request fails.
        """
        self.logger.info("Asking Neko with streaming response...")

        data = {
            "model": self.nekomimiConfig["Model"],
            "input": self.__generatePrompt(request),
            "stream": True,
        }

        async with aioHttpClientSession() as session:
            async with session.post(
                self.postURL, json=data, headers=self.postHeaders
            ) as resp:
                async for raw_line in resp.content:
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue

                    delta = self.__parseTextSteam(line)

                    if delta:
                        yield delta
