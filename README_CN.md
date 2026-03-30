# CiaAgentlloNya

🌐 Languages: [![English](https://img.shields.io/badge/README-English-green)](README.md) [![中文](https://img.shields.io/badge/README-%E4%B8%AD%E6%96%87-blue)](README_CN.md)

这是一个**个人Telrgram猫娘**Agent机器人。 Cia Agent llo~ (∠·ω< )⌒★ Nya~~~

## 配置

在尝试运行本机器人前，您应当先配置config.yaml

您可以适当修改./config/configExmple.yaml，然后将其重命名为./config/config.yaml，以完成配置

```yaml
Nekomimi:
    API Provider: xxxxxx
    Model: xxxxxx
    Token: xx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    Language: xx

TelegramBot:
    Token: xxxxxxxxxx:xxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxx
    Language: xx
    UserName: xxxxxxx
    StreamingResponse: False
```

### Nekomimi

#### API Provider

请在这里填写在线LLM的API提供商名称，目前支持的有：

- Opencode Zen

#### Model

请在这里填写调用的在线LLM模型名称，具体名称可能需要您查阅API提供商的文档

#### Token (API Provider)

请您在这里填写API提供商的Token

#### Language (API Provider)

您应当在这里填写调用在线LLM时使用的语言，目前支持的有：

- CN    (简体)中文
- EN    英文

### TelegramBot

#### Token (TelegramBot)

您应当在这里填写您Telegram Bot的Token(HTTP API)

如果您还没有在Telegram上注册Bot，请您利用Telegram中的@BotFather机器人完成注册，您可以/start后，执行/newbot，按照要求填写Bot名称和用户名后即可获得Token

#### Language (TelegramBot)

您应当在这里填写该Bot的语言，目前支持的有：

- CN    (简体)中文
- EN    英文

#### UserName

您应当填入您Telegram的用户名

#### StreamingResponse

配置该机器人响应时是单次完整响应，还是流式响应

注意，流式响应似乎有一些bug，用户可能同时收到两条相同的响应，在一定时间后或某些没有被确定的条件后，第一条消息会消失

又考虑到本机器人响应内容一般不会太长，建议该项设定为False，即默认进行单次完整响应

本条设置为bool值，即您应当填写True/False

## 运行

目前本项目处于开发阶段，如果想尝试运行，您可以执行./bot.py来测试本机器人
