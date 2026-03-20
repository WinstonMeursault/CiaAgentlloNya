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
    DefaultLanguage: xx

TelegramBot:
    Token: xxxxxxxxxx:xxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxx
    DefaultLanguage: xx

```

### Nekomimi

#### API Provider

Please specify the name of the online LLM API provider here. Currently supported providers include:

- Opencode Zen

#### Model

Please specify the name of the online LLM model to be used. The exact name may require consulting the API provider’s documentation.

#### Token

Please enter the API provider’s token here.

#### DefaultLanguage

Please specify the default language used when calling the online LLM. Currently supported:

- CN    (Simplified) Chinese

### TelegramBot

#### Token

Please enter your Telegram Bot token (HTTP API) here.

If you have not yet registered a bot on Telegram, you can use the @BotFather bot to create one. After sending /start, run /newbot and follow the instructions to set the bot name and username, after which you will receive the token.

#### DefaultLanguage

Please specify the default language for the bot. Currently supported:

- CN    (Simplified) Chinese

## Running

This project is currently under development. If you would like to try running it, you can execute ./bot.py to test the bot.
