from typing import Optional, AsyncGenerator
from json import loads as jsonLoads, JSONDecodeError

import aiohttp
from loguru import nekoLogger
from yaml import safe_load as yamlSafeLoad
from requests import post as requestsPost

nekoLogger.add(
    "./logs/log_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="7 days",
    compression="gz",
    encoding="utf-8",
    enqueue=True,
    format="{time:YYYY-MM-DD at HH:mm:ss, UTC Z} | Logging Function: neko::{function} | {level} | {message}",
)

try:
    with open("./config/config.yaml", "r") as yamlConfig:
        nekomimiConfig = yamlSafeLoad(yamlConfig)["Nekomimi"]

    with open("./config/inf.yaml", "r") as yamlInf:
        inf = yamlSafeLoad(yamlInf)

    if nekomimiConfig["Language"] == "CN":
        with open("./config/prompt_CN.yaml", "r") as yamlPrompt:
            nekomimiPrompt = yamlSafeLoad(yamlPrompt)

    nekoLogger.info("Configuration loaded successfully.")
except Exception as e:
    nekoLogger.error("Failed to load configuration: " + str(e))
    raise e

postURL = inf["API Provider URL"][nekomimiConfig["API Provider"]]
postHeaders = {
    "Authorization": "Bearer " + nekomimiConfig["Token"],
    "Content-Type": "application/json",
}


def generatePrompt(request: str) -> str:
    nekoLogger.info("Generating prompt...")
    return nekomimiPrompt["askNeko"] + request


def parseText(resp: dict) -> str:
    texts = []
    for item in resp.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    texts.append(content.get("text"))
    return "\n".join(texts)


def parseTextSteam(line: str) -> Optional[str]:
    line = line.strip()

    if not line.startswith("data:"):
        return None

    payload = line[5:].strip()

    if payload == "[DONE]":
        return None

    try:
        obj = jsonLoads(payload)
    except JSONDecodeError:
        nekoLogger.error("Failed to parse JSON: " + payload)
        return None

    if obj.get("type") == "response.output_text.delta":
        return obj.get("delta")

    return None


def askNeko(request: str) -> str:
    nekoLogger.info("Asking Neko...")

    data = {"model": nekomimiConfig["Model"], "input": generatePrompt(request)}

    res = requestsPost(postURL, json=data, headers=postHeaders)
    return parseText(res.json())


async def askNekoStream(request: str) -> AsyncGenerator[str, None]:
    nekoLogger.info("Asking Neko with streaming response...")

    data = {
        "model": nekomimiConfig["Model"],
        "input": generatePrompt(request),
        "stream": True,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(postURL, json=data, headers=postHeaders) as resp:
            async for raw_line in resp.content:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue

                delta = parseTextSteam(line)

                if delta:
                    yield delta
