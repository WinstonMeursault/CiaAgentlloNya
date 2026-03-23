from typing import Optional, AsyncGenerator
from json import loads as jsonLoads, JSONDecodeError

import aiohttp
from loguru import logger
from yaml import safe_load as yamlSafeLoad
from requests import post as requestsPost


class neko:
    def __init__(self):
        self.logger = logger.bind(module="neko")

        try:
            with open("./config/config.yaml", "r") as yamlConfig:
                self.nekomimiConfig = yamlSafeLoad(yamlConfig)["Nekomimi"]

            with open("./config/inf.yaml", "r") as yamlInf:
                self.inf = yamlSafeLoad(yamlInf)

            if self.nekomimiConfig["Language"] == "CN":
                with open("./config/prompt_CN.yaml", "r") as yamlPrompt:
                    self.nekomimiPrompt = yamlSafeLoad(yamlPrompt)

            self.logger.info("Configuration loaded successfully.")
        except Exception as e:
            self.logger.error("Failed to load configuration: " + str(e))
            raise e

        self.postURL = self.inf["API Provider URL"][self.nekomimiConfig["API Provider"]]
        self.postHeaders = {
            "Authorization": "Bearer " + self.nekomimiConfig["Token"],
            "Content-Type": "application/json",
        }

    def __generatePrompt(self, request: str) -> str:
        self.logger.info("Generating prompt...")
        return self.nekomimiPrompt["askNeko"] + request

    def __parseText(self, resp: dict) -> str:
        texts = []

        for item in resp.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        texts.append(content.get("text"))

        return "\n".join(texts)

    def __parseTextSteam(self, line: str) -> Optional[str]:
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
        self.logger.info("Asking Neko...")

        data = {
            "model": self.nekomimiConfig["Model"],
            "input": self.__generatePrompt(request),
        }

        res = requestsPost(self.postURL, json=data, headers=self.postHeaders)
        return self.__parseText(res.json())

    async def askNekoStream(self, request: str) -> AsyncGenerator[str, None]:
        self.logger.info("Asking Neko with streaming response...")

        data = {
            "model": self.nekomimiConfig["Model"],
            "input": self.__generatePrompt(request),
            "stream": True,
        }

        async with aiohttp.ClientSession() as session:
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
