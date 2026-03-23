import asyncio
from time import time

from loguru import logger
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

from neko import neko
from chatHistory import ChatHistory

logger.add(
    "./logs/log_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="7 days",
    compression="gz",
    encoding="utf-8",
    enqueue=True,
    format="{time:YYYY-MM-DD at HH:mm:ss:SSS, UTC Z} | {level} | Logging Function: {extra[module]}::{function} | {message}",
)


class bot:
    def __init__(self):
        self.logger = logger.bind(module="bot")
        self.debugMode = False

        self.logger.info("Bot Start.")

        try:
            with open("./config/config.yaml", "r") as yamlConfig:
                self.botConfig = yamlSafeLoad(yamlConfig)["TelegramBot"]

            if self.botConfig["Language"] == "CN":
                with open("./config/replyTemplate_CN.yaml", "r") as yamlReplyTemplate:
                    self.botReplyTemplate = yamlSafeLoad(yamlReplyTemplate)

                    self.logger.info("Configuration loaded successfully.")
        except Exception as e:
            self.logger.error("Failed to load configuration: " + str(e))
            raise e

        self.chatHistory = ChatHistory()
        self.neko = neko(chatHistory=self.chatHistory)

    async def __sendMessage(
        self, context: ContextTypes.DEFAULT_TYPE, chatID: int, text: str
    ) -> None:
        while True:
            try:
                await context.bot.send_message(chat_id=chatID, text=text)
                self.logger.info("Message sent successfully. Message: " + text)
                break
            except RetryAfter as e:
                self.logger.warning(
                    f"Rate limit exceeded. Retrying after {e.retry_after} seconds."
                )
                self.logger.warning("Chat ID: " + str(chatID) + ", Message: " + text)
                await asyncio.sleep(e.retry_after)
            except TimedOut as e:
                self.logger.warning("Request timed out.")
                self.logger.warning("Chat ID: " + str(chatID) + ", Message: " + text)
            except BadRequest as e:
                asyncio.create_task(
                    self.__sendMessage(
                        context, chatID, self.botReplyTemplate["BadRequest"]
                    )
                )
                self.logger.error("Bad request error: " + str(e))
                self.logger.error("Chat ID: " + str(chatID) + ", Message: " + text)
                break
            except Exception as e:
                asyncio.create_task(
                    self.__sendMessage(
                        context, chatID, self.botReplyTemplate["BadRequest"]
                    )
                )
                self.logger.error("Unexpected error: " + str(e))
                self.logger.error("Chat ID: " + str(chatID) + ", Message: " + text)
                break

    async def __sendStreamingMessage(
        self, context: ContextTypes.DEFAULT_TYPE, chatID: int, draftID: int, text: str
    ) -> None:
        while True:
            try:
                await context.bot.send_message_draft(
                    chat_id=chatID, draft_id=draftID, text=text
                )
                self.logger.info(
                    "Streaming message sent successfully. Message: " + text
                )
                break
            except RetryAfter as e:
                self.logger.warning(
                    f"Rate limit exceeded. Retrying after {e.retry_after} seconds."
                )
                self.logger.warning("Chat ID: " + str(chatID) + ", Message: " + text)
                await asyncio.sleep(e.retry_after)
            except TimedOut as e:
                self.logger.warning("Request timed out.")
                self.logger.warning("Chat ID: " + str(chatID) + ", Message: " + text)
                break
            except BadRequest as e:
                asyncio.create_task(
                    self.__sendMessage(
                        context, chatID, self.botReplyTemplate["BadRequest"]
                    )
                )
                self.logger.error("Bad request error: " + str(e))
                self.logger.error("Chat ID: " + str(chatID) + ", Message: " + text)
                break
            except Exception as e:
                asyncio.create_task(
                    self.__sendMessage(
                        context, chatID, self.botReplyTemplate["BadRequest"]
                    )
                )
                self.logger.error("Unexpected error: " + str(e))
                self.logger.error("Chat ID: " + str(chatID) + ", Message: " + text)
                break

    async def __start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        asyncio.create_task(
            self.__sendMessage(
                context, update.effective_chat.id, self.botReplyTemplate["start"]
            )
        )
        self.logger.info(
            "Handled /start command. Chat ID: " + str(update.effective_chat.id)
        )

    async def __help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        asyncio.create_task(
            self.__sendMessage(
                context, update.effective_chat.id, self.botReplyTemplate["help"]
            )
        )
        self.logger.info(
            "Handled /help command. Chat ID: " + str(update.effective_chat.id)
        )

    async def __setting(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        asyncio.create_task(
            self.__sendMessage(
                context, update.effective_chat.id, self.botReplyTemplate["setting"]
            )
        )
        self.logger.info(
            "Handled /setting command. Chat ID: " + str(update.effective_chat.id)
        )

    async def __settingStreamingResponse_ON(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        try:
            self.botConfig["StreamingResponse"] = True

            asyncio.create_task(
                self.__sendMessage(
                    context, update.effective_chat.id, "流式回复已开启喵~~"
                )
            )

            with open("./config/config.yaml", "w", encoding="utf-8") as f:
                yamlDump(
                    self.botConfig, f, default_flow_style=False, allow_unicode=True
                )

            self.logger.info(
                "Streaming response enabled. Chat ID: " + str(update.effective_chat.id)
            )
        except Exception as e:
            self.logger.error("Failed to enable streaming response: " + str(e))
            asyncio.create_task(
                self.__sendMessage(
                    context,
                    update.effective_chat.id,
                    self.botReplyTemplate["UnexpectedError"],
                )
            )

    async def __settingStreamingResponse_OFF(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        try:
            self.botConfig["StreamingResponse"] = False

            asyncio.create_task(
                self.__sendMessage(
                    context, update.effective_chat.id, "流式回复已关闭喵~~"
                )
            )

            with open("./config/config.yaml", "w", encoding="utf-8") as f:
                yamlDump(
                    self.botConfig, f, default_flow_style=False, allow_unicode=True
                )

            self.logger.info(
                "Streaming response disabled. Chat ID: " + str(update.effective_chat.id)
            )
        except Exception as e:
            self.logger.error("Failed to disable streaming response: " + str(e))
            asyncio.create_task(
                self.__sendMessage(
                    context,
                    update.effective_chat.id,
                    self.botReplyTemplate["UnexpectedError"],
                )
            )

    async def __settingDebugMode_ON(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        try:
            self.debugMode = True

            asyncio.create_task(
                self.__sendMessage(
                    context, update.effective_chat.id, "调试模式已开启喵~~"
                )
            )

            self.logger.info(
                "Debug mode enabled. Chat ID: " + str(update.effective_chat.id)
            )
        except Exception as e:
            self.logger.error("Failed to enable debug mode: " + str(e))
            asyncio.create_task(
                self.__sendMessage(
                    context,
                    update.effective_chat.id,
                    self.botReplyTemplate["UnexpectedError"],
                )
            )

    async def __settingDebugMode_OFF(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        try:
            self.debugMode = False

            asyncio.create_task(
                self.__sendMessage(
                    context, update.effective_chat.id, "调试模式已关闭喵~~"
                )
            )

            self.logger.info(
                "Debug mode disabled. Chat ID: " + str(update.effective_chat.id)
            )
        except Exception as e:
            self.logger.error("Failed to disable debug mode: " + str(e))
            asyncio.create_task(
                self.__sendMessage(
                    context,
                    update.effective_chat.id,
                    self.botReplyTemplate["UnexpectedError"],
                )
            )

    async def __chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        response = self.neko.askNeko(update.message.text)

        asyncio.create_task(
            self.__sendMessage(context, update.effective_chat.id, response)
        )

        self.logger.info(
            "Handled chat message. Chat ID: "
            + str(update.effective_chat.id)
            + ", Message: "
            + update.message.text
        )

        print(update.effective_user.full_name)
        self.chatHistory.addMessage(
            username=update.effective_user.full_name,
            role="user",
            message=update.message.text,
            chatId=update.effective_chat.id,
        )
        self.chatHistory.addMessage(
            username=update.effective_user.full_name,
            role="bot",
            message=response,
            chatId=update.effective_chat.id,
        )

    async def __chatStream(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        steamID = int(round(time() * 1000))
        accumulatedText = ""
        buffer = ""
        flushInterval = 0.3
        bufferMaxSize = 50
        lastFlush = asyncio.get_event_loop().time()

        async for delta in self.neko.askNekoStream(update.message.text):
            buffer += delta
            now = asyncio.get_event_loop().time()

            if now - lastFlush >= flushInterval or len(buffer) > bufferMaxSize:
                accumulatedText += buffer

                asyncio.create_task(
                    self.__sendStreamingMessage(
                        context, update.effective_chat.id, steamID, accumulatedText
                    )
                )

                buffer = ""
                lastFlush = now

        if buffer:
            accumulatedText += buffer
            asyncio.create_task(
                self.__sendStreamingMessage(
                    context, update.effective_chat.id, steamID, accumulatedText
                )
            )

        asyncio.create_task(
            self.__sendMessage(context, update.effective_chat.id, accumulatedText)
        )

        self.logger.info(
            "Handled streaming chat message. Chat ID: "
            + str(update.effective_chat.id)
            + ", Message: "
            + update.message.text
        )

        self.chatHistory.addMessage(
            username=update.effective_user.full_name,
            role="user",
            message=update.message.text,
            chatId=update.effective_chat.id,
        )
        self.chatHistory.addMessage(
            username=update.effective_user.full_name,
            role="bot",
            message=accumulatedText,
            chatId=update.effective_chat.id,
        )

    async def __chatDebug(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        await context.bot.send_message(
            update.effective_chat.id,
            "Debug Mode\nInput: " + update.message.text + "\n\naskNekoOutput:",
        )
        await self.__chat(update, context)

        await context.bot.send_message(
            update.effective_chat.id, "askNekoStream Output:"
        )
        await self.__chatStream(update, context)

        self.logger.info(
            "Handled chat message in debug mode. Chat ID: "
            + str(update.effective_chat.id)
            + ", Message: "
            + update.message.text
        )

    async def __chatResponse(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        self.logger.info(
            "Preparing to respond to chat message. Chat ID: "
            + str(update.effective_chat.id)
            + ", Debug Mode: "
            + str(self.debugMode)
        )

        if self.debugMode:
            await self.__chatDebug(update, context)
        else:
            if self.botConfig["StreamingResponse"]:
                await self.__chatStream(update, context)
            else:
                await self.__chat(update, context)

    def run(self) -> None:
        try:
            self.application = (
                Application.builder().token(self.botConfig["Token"]).build()
            )

            self.logger.info("Telegram bot initialized successfully.")

            self.application.add_handler(CommandHandler("start", self.__start))
            self.application.add_handler(CommandHandler("help", self.__help))

            self.application.add_handler(CommandHandler("setting", self.__setting))
            self.application.add_handler(
                CommandHandler(
                    "settingStreamingResponse_ON", self.__settingStreamingResponse_ON
                )
            )
            self.application.add_handler(
                CommandHandler(
                    "settingStreamingResponse_OFF", self.__settingStreamingResponse_OFF
                )
            )
            self.application.add_handler(
                CommandHandler("settingDebugMode_ON", self.__settingDebugMode_ON)
            )
            self.application.add_handler(
                CommandHandler("settingDebugMode_OFF", self.__settingDebugMode_OFF)
            )

            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self.__chatResponse)
            )

            self.logger.info("Handlers added successfully. Starting polling...")

            self.application.run_polling(allowed_updates=Update.ALL_TYPES)

            self.logger.info("Polling started successfully.")
        except TimedOut as e:
            self.logger.error("Failed to start bot due to timeout: " + str(e))
        except Exception as e:
            self.logger.error("Failed to start bot due to unexpected error: " + str(e))
            raise e


if __name__ == "__main__":
    telegramBot = bot()
    telegramBot.run()
