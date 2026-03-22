import asyncio
from time import time

from loguru import logger as botLogger
from yaml import safe_load as yamlSafeLoad, dump as yamlDump
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.error import RetryAfter, BadRequest, TimedOut

from neko import askNeko, askNekoStream

botLogger.add(
    "./logs/log_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="7 days",
    compression="gz",
    encoding="utf-8",
    enqueue=True,
    format="{time:YYYY-MM-DD at HH:mm:ss:SSS, UTC Z} | Logging Function: bot::{function} | {level} | {message}",
)

botLogger.info("Bot Start.")

try:
    with open("./config/config.yaml", "r") as yamlConfig:
        botConfig = yamlSafeLoad(yamlConfig)["TelegramBot"]

    if botConfig["Language"] == "CN":
        with open("./config/replyTemplate_CN.yaml", "r") as yamlReplyTemplate:
            botReplyTemplate = yamlSafeLoad(yamlReplyTemplate)

    botLogger.info("Configuration loaded successfully.")
except Exception as e:
    botLogger.error("Failed to load configuration: " + str(e))
    raise e

debugMode = False


async def sendMessage(
    context: ContextTypes.DEFAULT_TYPE, chatID: int, text: str
) -> None:
    while True:
        try:
            await context.bot.send_message(chat_id=chatID, text=text)
            botLogger.info("Message sent successfully. Message: " + text)
            break
        except RetryAfter as e:
            botLogger.warning(
                f"Rate limit exceeded. Retrying after {e.retry_after} seconds."
            )
            botLogger.warning("Chat ID: " + str(chatID) + ", Message: " + text)
            await asyncio.sleep(e.retry_after)
        except TimedOut as e:
            botLogger.warning("Request timed out.")
            botLogger.warning("Chat ID: " + str(chatID) + ", Message: " + text)
        except BadRequest as e:
            asyncio.create_task(
                sendMessage(context, chatID, botReplyTemplate["BadRequest"])
            )
            botLogger.error("Bad request error: " + str(e))
            botLogger.error("Chat ID: " + str(chatID) + ", Message: " + text)
            break
        except Exception as e:
            asyncio.create_task(
                sendMessage(context, chatID, botReplyTemplate["BadRequest"])
            )
            botLogger.error("Unexpected error: " + str(e))
            botLogger.error("Chat ID: " + str(chatID) + ", Message: " + text)
            break


async def sendStreamingMessage(
    context: ContextTypes.DEFAULT_TYPE, chatID: int, draftID: int, text: str
) -> None:
    while True:
        try:
            await context.bot.send_message_draft(
                chat_id=chatID, draft_id=draftID, text=text
            )
            botLogger.info("Streaming message sent successfully. Message: " + text)
            break
        except RetryAfter as e:
            botLogger.warning(
                f"Rate limit exceeded. Retrying after {e.retry_after} seconds."
            )
            botLogger.warning("Chat ID: " + str(chatID) + ", Message: " + text)
            await asyncio.sleep(e.retry_after)
        except TimedOut as e:
            botLogger.warning("Request timed out.")
            botLogger.warning("Chat ID: " + str(chatID) + ", Message: " + text)
        except BadRequest as e:
            asyncio.create_task(
                sendMessage(context, chatID, botReplyTemplate["BadRequest"])
            )
            botLogger.error("Bad request error: " + str(e))
            botLogger.error("Chat ID: " + str(chatID) + ", Message: " + text)
            break
        except Exception as e:
            asyncio.create_task(
                sendMessage(context, chatID, botReplyTemplate["BadRequest"])
            )
            botLogger.error("Unexpected error: " + str(e))
            botLogger.error("Chat ID: " + str(chatID) + ", Message: " + text)
            break


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    asyncio.create_task(
        sendMessage(context, update.effective_chat.id, botReplyTemplate["start"])
    )
    botLogger.info("Handled /start command. Chat ID: " + str(update.effective_chat.id))


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    asyncio.create_task(
        sendMessage(context, update.effective_chat.id, botReplyTemplate["help"])
    )
    botLogger.info("Handled /help command. Chat ID: " + str(update.effective_chat.id))


async def setting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    asyncio.create_task(
        sendMessage(context, update.effective_chat.id, botReplyTemplate["setting"])
    )
    botLogger.info(
        "Handled /setting command. Chat ID: " + str(update.effective_chat.id)
    )


async def settingStreamingResponse_ON(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    try:
        botConfig["StreamingResponse"] = True

        asyncio.create_task(
            sendMessage(context, update.effective_chat.id, "流式回复已开启喵~~")
        )

        with open("./config/config.yaml", "w", encoding="utf-8") as f:
            yamlDump(botConfig, f, default_flow_style=False, allow_unicode=True)

        botLogger.info(
            "Streaming response enabled. Chat ID: " + str(update.effective_chat.id)
        )
    except Exception as e:
        botLogger.error("Failed to enable streaming response: " + str(e))
        asyncio.create_task(
            sendMessage(
                context, update.effective_chat.id, botReplyTemplate["UnexpectedError"]
            )
        )


async def settingStreamingResponse_OFF(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    try:
        botConfig["StreamingResponse"] = False

        asyncio.create_task(
            sendMessage(context, update.effective_chat.id, "流式回复已关闭喵~~")
        )

        with open("./config/config.yaml", "w", encoding="utf-8") as f:
            yamlDump(botConfig, f, default_flow_style=False, allow_unicode=True)

        botLogger.info(
            "Streaming response disabled. Chat ID: " + str(update.effective_chat.id)
        )
    except Exception as e:
        botLogger.error("Failed to disable streaming response: " + str(e))
        asyncio.create_task(
            sendMessage(
                context, update.effective_chat.id, botReplyTemplate["UnexpectedError"]
            )
        )


async def settingDebugMode_ON(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    try:
        global debugMode
        debugMode = True

        asyncio.create_task(
            sendMessage(context, update.effective_chat.id, "调试模式已开启喵~~")
        )

        botLogger.info("Debug mode enabled. Chat ID: " + str(update.effective_chat.id))
    except Exception as e:
        botLogger.error("Failed to enable debug mode: " + str(e))
        asyncio.create_task(
            sendMessage(
                context, update.effective_chat.id, botReplyTemplate["UnexpectedError"]
            )
        )


async def settingDebugMode_OFF(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    try:
        global debugMode
        debugMode = False

        asyncio.create_task(
            sendMessage(context, update.effective_chat.id, "调试模式已关闭喵~~")
        )

        botLogger.info("Debug mode disabled. Chat ID: " + str(update.effective_chat.id))
    except Exception as e:
        botLogger.error("Failed to disable debug mode: " + str(e))
        asyncio.create_task(
            sendMessage(
                context, update.effective_chat.id, botReplyTemplate["UnexpectedError"]
            )
        )


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    response = askNeko(update.message.text)
    asyncio.create_task(sendMessage(context, update.effective_chat.id, response))
    botLogger.info(
        "Handled chat message. Chat ID: "
        + str(update.effective_chat.id)
        + ", Message: "
        + update.message.text
    )


async def chatStream(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    steamID = int(round(time() * 1000))
    accumulatedText = ""
    buffer = ""
    flushInterval = 0.3
    bufferMaxSize = 50
    lastFlush = asyncio.get_event_loop().time()

    async for delta in askNekoStream(update.message.text):
        buffer += delta
        now = asyncio.get_event_loop().time()

        if now - lastFlush >= flushInterval or len(buffer) > bufferMaxSize:
            accumulatedText += buffer

            asyncio.create_task(
                sendStreamingMessage(
                    context, update.effective_chat.id, steamID, accumulatedText
                )
            )

            buffer = ""
            lastFlush = now

    if buffer:
        accumulatedText += buffer
        asyncio.create_task(
            sendStreamingMessage(
                context, update.effective_chat.id, steamID, accumulatedText
            )
        )

    asyncio.create_task(sendMessage(context, update.effective_chat.id, accumulatedText))

    botLogger.info(
        "Handled streaming chat message. Chat ID: "
        + str(update.effective_chat.id)
        + ", Message: "
        + update.message.text
    )


async def chatDebug(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(
        update.effective_chat.id,
        "Debug Mode\nInput: " + update.message.text + "\n\naskNekoOutput:",
    )
    await chat(update, context)

    await context.bot.send_message(update.effective_chat.id, "askNekoStream Output:")
    await chatStream(update, context)

    botLogger.info(
        "Handled chat message in debug mode. Chat ID: "
        + str(update.effective_chat.id)
        + ", Message: "
        + update.message.text
    )


async def chatResponse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    botLogger.info(
        "Preparing to respond to chat message. Chat ID: "
        + str(update.effective_chat.id)
        + ", Debug Mode: "
        + str(debugMode)
    )

    if debugMode:
        await chatDebug(update, context)
    else:
        if botConfig["StreamingResponse"]:
            await chatStream(update, context)
        else:
            await chat(update, context)


def main() -> None:
    botLogger.info("Entering main function of bot.")

    application = Application.builder().token(botConfig["Token"]).build()

    botLogger.info("Telegram bot initialized successfully.")

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))

    application.add_handler(CommandHandler("setting", setting))
    application.add_handler(
        CommandHandler("settingStreamingResponse_ON", settingStreamingResponse_ON)
    )
    application.add_handler(
        CommandHandler("settingStreamingResponse_OFF", settingStreamingResponse_OFF)
    )
    application.add_handler(CommandHandler("settingDebugMode_ON", settingDebugMode_ON))
    application.add_handler(
        CommandHandler("settingDebugMode_OFF", settingDebugMode_OFF)
    )

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, chatResponse)
    )

    botLogger.info("Handlers added successfully. Starting polling...")

    application.run_polling(allowed_updates=Update.ALL_TYPES)

    botLogger.info("Polling started successfully.")


if __name__ == "__main__":
    main()
