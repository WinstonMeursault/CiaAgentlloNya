from typing import Optional, AsyncGenerator
from json import loads as jsonLoads, JSONDecodeError

import aiohttp
from yaml import safe_load as yamlSafeLoad
from requests import post as requestsPost

with open('./config/config.yaml', 'r') as yamlConfig:
    nekomimiConfig = yamlSafeLoad(yamlConfig)['Nekomimi']
    
with open('./config/inf.yaml', 'r') as yamlInf:
    inf = yamlSafeLoad(yamlInf)
    
if nekomimiConfig['DefaultLanguage'] == 'CN':
    with open('./config/prompt_CN.yaml', 'r') as yamlPrompt:
        nekomimiPrompt = yamlSafeLoad(yamlPrompt)
        
postURL = inf['API Provider URL'][nekomimiConfig['API Provider']]
postHeaders = {
    "Authorization": "Bearer " + nekomimiConfig['Token'],
    "Content-Type": "application/json"
}

def generatePrompt(request: str) -> str:
    return nekomimiPrompt['askNeko'] + request

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
        return None

    if obj.get("type") == "response.output_text.delta":
        return obj.get("delta")

    return None

def askNeko(request: str) -> str:
    data = {
    "model": nekomimiConfig['Model'],
    "input": generatePrompt(request)
    }
    
    res = requestsPost(postURL, json=data, headers=postHeaders)
    return parseText(res.json())

async def askNekoStream(request: str) -> AsyncGenerator[str, None]:
    data = {
        "model": nekomimiConfig['Model'],
        "input": generatePrompt(request),
        "stream": True
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
                    