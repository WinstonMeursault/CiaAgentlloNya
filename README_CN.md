# CiaAgentlloNya

这是一个Telrgram猫娘Agent机器人。 Cia Agent llo～(∠·ω&lt; )⌒★ Nya~~~

## 配置

在尝试运行本机器人前，您应当先配置config.yaml

您可以适当修改configExmple.yaml，然后将其重命名为config.yaml，以完成配置

```yaml
Nekomimi:

TelegramBot:
    Token: xxxxxxxxxx:xxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxx
    DefaultLanguage: CN
```

### Nekomimi

### TelegramBot

#### Token

您应当在这里填写您Telegram Bot的Token(HTTP API)，格式如同示例一般

如果您还没有在Telegram上注册Bot，请您利用Telegram中的@BotFather机器人完成注册，您可以/start后，执行/newbot，按照要求填写Bot名称和用户名后即可获得Token

#### DefaultLanguage

您应当在这里填写该Bot的默认语言，目前可选项仅为CN

本机器人使用的本地LLM对默认语言有针对性优化，对其他语言有一定的泛化能力
