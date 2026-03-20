from yaml import safe_load as yamlSafeLoad

import requests

with open('./config/config.yaml', 'r') as yamlConfig:
    nekomimiConfig = yamlSafeLoad(yamlConfig)['Nekomimi']
    
with open('./config/inf.yaml', 'r') as yamlInf:
    inf = yamlSafeLoad(yamlInf)
    
if nekomimiConfig['DefaultLanguage'] == 'CN':
    with open('./config/prompt_CN.yaml', 'r') as yamlPrompt:
        nekomimiPrompt = yamlSafeLoad(yamlPrompt)

def extractText(resp):
    texts = []
    for item in resp.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    texts.append(content.get("text"))
    return "\n".join(texts)

def askNeko(request: str) -> str:
    url = inf['API Provider URL'][nekomimiConfig['API Provider']]
    headers = {
    "Authorization": "Bearer " + nekomimiConfig['Token'],
    "Content-Type": "application/json"
    }
    data = {
    "model": nekomimiConfig['Model'],
    "input": nekomimiPrompt['askNeko'] + request
    }
    res = requests.post(url, json=data, headers=headers)
    return extractText(res.json())
