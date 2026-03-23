# CiaAgentlloNya

🌐 Languages: [![English](https://img.shields.io/badge/README-English-green)](README.md) [![中文](https://img.shields.io/badge/README-%E4%B8%AD%E6%96%87-blue)](README_CN.md)

This is a **personal Telegram nekomimi** Agent bot. Cia Agent llo~ (∠·ω< )⌒★ Nya~~~

## Configuration

Before attempting to run this bot, you should first configure config.yaml.

You may modify ./config/configExample.yaml as needed, and then rename it to ./config/config.yaml to complete the configuration.

```yaml
Nekomimi:
    API Provider: xxxxxx
    Model: xxxxxx
    Token: xx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    Language: xx

TelegramBot:
    Token: xxxxxxxxxx:xxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxx
    Language: xx
    StreamingResponse: False
```

### Nekomimi

#### API Provider

Please specify the name of the online LLM API provider here. Currently supported providers include:

- Opencode Zen

#### Model

Please specify the name of the online LLM model to be used. The exact name may require consulting the API provider’s documentation.

#### Token (API Provider)

Please enter the API provider’s token here.

#### Language (API Provider)

Please specify the language used when calling the online LLM. Currently supported:

- CN    (Simplified) Chinese

### TelegramBot

#### Token (TelegramBot)

Please enter your Telegram Bot token (HTTP API) here.

If you have not yet registered a bot on Telegram, you can use the @BotFather bot to create one. After sending /start, run /newbot and follow the instructions to set the bot name and username, after which you will receive the token.

#### Language (TelegramBot)

Please specify the language for the bot. Currently supported:

- CN    (Simplified) Chinese

#### StreamingResponse

The configuration for the bot's response type is as follows, Single Complete Response or Streamed Response.

Currently, the bot may support both types, but streamed responses seem to have some bugs. Users may receive two identical responses simultaneously, and one of the messages may disappear after some time or under certain undefined conditions.

Since the response content for this bot is generally not very long, it is recommended to set this to False, meaning the bot will default to sending a single complete response.

This setting should be a boolean value. Please set it to True or False.

## Running

This project is currently under development. If you would like to try running it, you can execute ./bot.py to test the bot.
