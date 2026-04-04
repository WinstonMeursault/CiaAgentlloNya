"""
Telegram bot application module for the CiaAgentlloNya nekomimi assistant.

This module defines the main Bot class which handles Telegram updates,
manages user configuration, and interacts with the Neko LLM client
and ChatHistory database.
"""

import asyncio
from time import time
from os import path as osPath

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

from neko import Neko
from chatHistory import ChatHistory

currentDir = osPath.dirname(osPath.realpath(__file__))

logger.add(
    currentDir + "/logs/log_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="7 days",
    compression="gz",
    encoding="utf-8",
    enqueue=True,
    format="{time:YYYY-MM-DD at HH:mm:ss:SSS, UTC Z} | {level} | Logging Function: {extra[module]}::{function} | {message}",
)


MAX_SEND_RETRIES = 3


class Bot:
    """Telegram bot for Nekomimi cat-girl assistant interactions.

    This class manages the Telegram bot lifecycle, handles user commands
    and messages, and coordinates with the LLM client for responses.

    Attributes:
        debugMode: Flag indicating whether debug mode is enabled.
        fullConfig: Complete configuration dictionary loaded from config.yaml.
        botConfig: TelegramBot section of the configuration.
        botReplyTemplate: Reply templates loaded from the language-specific YAML file.
        chatHistory: Chat history storage instance.
        neko: Nekomimi LLM client instance.
        application: Telegram bot application instance.
    """

    def __init__(self) -> None:
        """Initialize the Telegram bot.

        Loads configuration files, initializes chat history storage,
        and creates the Nekomimi LLM client.

        Raises:
            FileNotFoundError: If configuration files are missing.
            KeyError: If required configuration keys are not found.
            ValueError: If an unsupported language is configured.
            Exception: If configuration loading fails for any other reason.
        """
        self.logger = logger.bind(module="bot")
        self.debugMode = False

        self.logger.info("Bot Start.")

        try:
            with open(currentDir + "/config/config.yaml", "r") as yamlConfig:
                self.fullConfig = yamlSafeLoad(yamlConfig)
            self.botConfig = self.fullConfig["TelegramBot"]

            if self.botConfig["Language"] == "CN":
                with open(
                    currentDir + "/config/replyTemplate_CN.yaml", "r"
                ) as yamlReplyTemplate:
                    self.botReplyTemplate = yamlSafeLoad(yamlReplyTemplate)
            elif self.botConfig["Language"] == "EN":
                with open(
                    currentDir + "/config/replyTemplate_EN.yaml", "r"
                ) as yamlReplyTemplate:
                    self.botReplyTemplate = yamlSafeLoad(yamlReplyTemplate)
            else:
                raise ValueError(
                    f"Unsupported language: {self.botConfig['Language']}. "
                    "Supported values are 'CN' and 'EN'."
                )

            self.logger.info("Configuration loaded successfully.")
        except Exception as e:
            self.logger.error("Failed to load configuration: " + str(e))
            raise

        self.chatHistory = ChatHistory()
        self.neko = Neko(chatHistory=self.chatHistory)

    async def __sendMessage(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        chatId: int,
        text: str,
        _isErrorReply: bool = False,
    ) -> None:
        """Send a message to a Telegram chat with retry logic.

        Handles rate limiting by waiting and retrying, and catches common
        Telegram API errors. On failure, sends an error message to the user
        unless this message is itself an error reply (to prevent recursion).

        Args:
            context: Telegram bot context for API calls.
            chatId: Target chat identifier.
            text: Message content to send.
            _isErrorReply: If True, suppresses further error notifications
                to prevent infinite recursion.
        """
        for attempt in range(1, MAX_SEND_RETRIES + 1):
            try:
                await context.bot.send_message(chat_id=chatId, text=text)
                self.logger.info("Message sent successfully. Message: " + text)
                return
            except RetryAfter as e:
                self.logger.warning(
                    f"Rate limit exceeded. Retrying after {e.retry_after} seconds."
                )
                self.logger.warning("Chat ID: " + str(chatId) + ", Message: " + text)
                await asyncio.sleep(e.retry_after)
            except TimedOut:
                self.logger.warning(
                    f"Request timed out (attempt {attempt}/{MAX_SEND_RETRIES})."
                )
                self.logger.warning("Chat ID: " + str(chatId) + ", Message: " + text)
            except BadRequest as e:
                self.logger.error("Bad request error: " + str(e))
                self.logger.error("Chat ID: " + str(chatId) + ", Message: " + text)
                if not _isErrorReply:
                    asyncio.create_task(
                        self.__sendMessage(
                            context,
                            chatId,
                            self.botReplyTemplate["BadRequest"],
                            _isErrorReply=True,
                        )
                    )
                return
            except Exception as e:
                self.logger.error("Unexpected error: " + str(e))
                self.logger.error("Chat ID: " + str(chatId) + ", Message: " + text)
                if not _isErrorReply:
                    asyncio.create_task(
                        self.__sendMessage(
                            context,
                            chatId,
                            self.botReplyTemplate["BadRequest"],
                            _isErrorReply=True,
                        )
                    )
                return

        self.logger.error(
            f"Failed to send message after {MAX_SEND_RETRIES} attempts. "
            + "Chat ID: "
            + str(chatId)
        )

    async def __sendStreamingMessage(
        self, context: ContextTypes.DEFAULT_TYPE, chatId: int, draftId: int, text: str
    ) -> None:
        """Send a streaming message draft to a Telegram chat.

        Used for real-time message updates during streaming responses.
        Handles rate limiting and common Telegram API errors.

        Args:
            context: Telegram bot context for API calls.
            chatId: Target chat identifier.
            draftId: Unique identifier for the message draft.
            text: Current accumulated message content.
        """
        for attempt in range(1, MAX_SEND_RETRIES + 1):
            try:
                await context.bot.send_message_draft(
                    chat_id=chatId, draft_id=draftId, text=text
                )
                self.logger.info(
                    "Streaming message sent successfully. Message: " + text
                )
                return
            except RetryAfter as e:
                self.logger.warning(
                    f"Rate limit exceeded. Retrying after {e.retry_after} seconds."
                )
                self.logger.warning("Chat ID: " + str(chatId) + ", Message: " + text)
                await asyncio.sleep(e.retry_after)
            except TimedOut:
                self.logger.warning(
                    f"Streaming request timed out (attempt {attempt}/{MAX_SEND_RETRIES})."
                )
                self.logger.warning("Chat ID: " + str(chatId) + ", Message: " + text)
            except BadRequest as e:
                self.logger.error("Bad request error: " + str(e))
                self.logger.error("Chat ID: " + str(chatId) + ", Message: " + text)
                asyncio.create_task(
                    self.__sendMessage(
                        context,
                        chatId,
                        self.botReplyTemplate["BadRequest"],
                        _isErrorReply=True,
                    )
                )
                return
            except Exception as e:
                self.logger.error("Unexpected error: " + str(e))
                self.logger.error("Chat ID: " + str(chatId) + ", Message: " + text)
                asyncio.create_task(
                    self.__sendMessage(
                        context,
                        chatId,
                        self.botReplyTemplate["BadRequest"],
                        _isErrorReply=True,
                    )
                )
                return

        self.logger.error(
            f"Failed to send streaming message after {MAX_SEND_RETRIES} attempts. "
            + "Chat ID: "
            + str(chatId)
        )

    async def __start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /start command.

        Sends a welcome message to the user.

        Args:
            update: Incoming Telegram update containing the command.
            context: Telegram bot context for API calls.
        """
        asyncio.create_task(
            self.__sendMessage(
                context, update.effective_chat.id, self.botReplyTemplate["start"]
            )
        )
        self.logger.info(
            "Handled /start command. Chat ID: " + str(update.effective_chat.id)
        )

    async def __help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /help command.

        Sends help information and available commands to the user.

        Args:
            update: Incoming Telegram update containing the command.
            context: Telegram bot context for API calls.
        """
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
        """Handle the /setting command.

        Sends available settings and configuration options to the user.

        Args:
            update: Incoming Telegram update containing the command.
            context: Telegram bot context for API calls.
        """
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
        """Handle the /settingStreamingResponse_ON command.

        Enables streaming response mode and persists the setting to config.

        Args:
            update: Incoming Telegram update containing the command.
            context: Telegram bot context for API calls.
        """
        try:
            self.botConfig["StreamingResponse"] = True

            asyncio.create_task(
                self.__sendMessage(
                    context,
                    update.effective_chat.id,
                    self.botReplyTemplate["settingStreamingResponseON"],
                )
            )

            with open(currentDir + "/config/config.yaml", "w", encoding="utf-8") as f:
                yamlDump(
                    self.fullConfig, f, default_flow_style=False, allow_unicode=True
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
        """Handle the /settingStreamingResponse_OFF command.

        Disables streaming response mode and persists the setting to config.

        Args:
            update: Incoming Telegram update containing the command.
            context: Telegram bot context for API calls.
        """
        try:
            self.botConfig["StreamingResponse"] = False

            asyncio.create_task(
                self.__sendMessage(
                    context,
                    update.effective_chat.id,
                    self.botReplyTemplate["settingStreamingResponseOFF"],
                )
            )

            with open(currentDir + "/config/config.yaml", "w", encoding="utf-8") as f:
                yamlDump(
                    self.fullConfig, f, default_flow_style=False, allow_unicode=True
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
        """Handle the /settingDebugMode_ON command.

        Enables debug mode for detailed response testing.

        Args:
            update: Incoming Telegram update containing the command.
            context: Telegram bot context for API calls.
        """
        try:
            self.debugMode = True

            asyncio.create_task(
                self.__sendMessage(
                    context,
                    update.effective_chat.id,
                    self.botReplyTemplate["settingDebugModeON"],
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
        """Handle the /settingDebugMode_OFF command.

        Disables debug mode and returns to normal response mode.

        Args:
            update: Incoming Telegram update containing the command.
            context: Telegram bot context for API calls.
        """
        try:
            self.debugMode = False

            asyncio.create_task(
                self.__sendMessage(
                    context,
                    update.effective_chat.id,
                    self.botReplyTemplate["settingDebugModeOFF"],
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
        """Handle a chat message with non-streaming LLM response.

        Sends the user message to the LLM, receives the complete response,
        and stores both messages in chat history.

        Args:
            update: Incoming Telegram update containing the message.
            context: Telegram bot context for API calls.
        """
        try:
            response = await self.neko.askNeko(
                update.effective_user.full_name, update.message.text
            )
        except Exception as e:
            self.logger.error(f"Failed to get LLM response: {e}")
            asyncio.create_task(
                self.__sendMessage(
                    context,
                    update.effective_chat.id,
                    self.botReplyTemplate["UnexpectedError"],
                    _isErrorReply=True,
                )
            )
            return

        asyncio.create_task(
            self.__sendMessage(context, update.effective_chat.id, response)
        )

        self.logger.info(
            "Handled chat message. Chat ID: "
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
            message=response,
            chatId=update.effective_chat.id,
        )

    async def __chatStream(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle a chat message with streaming LLM response.

        Sends the user message to the LLM, receives streaming response deltas,
        updates the message in real-time, and stores both messages in chat history.

        Uses buffering to reduce message update frequency and improve performance.

        Args:
            update: Incoming Telegram update containing the message.
            context: Telegram bot context for API calls.
        """
        streamId = int(round(time() * 1000))
        accumulatedText = ""
        buffer = ""
        flushInterval = 0.3
        bufferMaxSize = 50
        lastFlush = asyncio.get_running_loop().time()

        try:
            async for delta in self.neko.askNekoStream(
                update.effective_user.full_name, update.message.text
            ):
                buffer += delta
                now = asyncio.get_running_loop().time()

                if now - lastFlush >= flushInterval or len(buffer) > bufferMaxSize:
                    accumulatedText += buffer

                    asyncio.create_task(
                        self.__sendStreamingMessage(
                            context, update.effective_chat.id, streamId, accumulatedText
                        )
                    )

                    buffer = ""
                    lastFlush = now
        except Exception as e:
            self.logger.error(f"Failed during streaming LLM response: {e}")
            asyncio.create_task(
                self.__sendMessage(
                    context,
                    update.effective_chat.id,
                    self.botReplyTemplate["UnexpectedError"],
                    _isErrorReply=True,
                )
            )
            return

        if buffer:
            accumulatedText += buffer
            asyncio.create_task(
                self.__sendStreamingMessage(
                    context, update.effective_chat.id, streamId, accumulatedText
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
        """Handle a chat message in debug mode.

        Tests both synchronous and streaming response modes, displaying
        labeled outputs for comparison and debugging purposes.

        Args:
            update: Incoming Telegram update containing the message.
            context: Telegram bot context for API calls.
        """
        await self.__sendMessage(
            context,
            update.effective_chat.id,
            "Debug Mode\nInput: " + update.message.text + "\n\naskNekoOutput:",
        )
        await self.__chat(update, context)

        await self.__sendMessage(
            context,
            update.effective_chat.id,
            "askNekoStream Output:",
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
        """Route chat messages to the appropriate handler.

        Dispatches to debug, streaming, or synchronous chat handlers
        based on current configuration settings.

        Args:
            update: Incoming Telegram update containing the message.
            context: Telegram bot context for API calls.
        """
        if not update.message or not update.message.text:
            self.logger.warning(
                "Received update without message text. Chat ID: "
                + str(update.effective_chat.id)
            )
            return

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
        """Start the Telegram bot and begin polling for updates.

        Initializes the Telegram application, registers all command and
        message handlers, and starts the polling loop.

        Raises:
            TimedOut: If connection to Telegram servers times out.
            Exception: If bot startup fails for any other reason.
        """
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

        except TimedOut as e:
            self.logger.error("Failed to start bot due to timeout: " + str(e))
        except Exception as e:
            self.logger.error("Failed to start bot due to unexpected error: " + str(e))
            raise


if __name__ == "__main__":
    telegramBot = Bot()
    telegramBot.run()
