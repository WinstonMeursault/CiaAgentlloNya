import asyncio
from time import time

from yaml import safe_load as yamlSafeLoad
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.error import RetryAfter

from neko import askNeko, askNekoStream

with open('./config/config.yaml', 'r') as yamlConfig:
    botConfig = yamlSafeLoad(yamlConfig)['TelegramBot']
    
if botConfig['DefaultLanguage'] == 'CN':
    with open('./config/replyTemplate_CN.yaml', 'r') as yamlReplyTemplate:
        botReplyTemplate = yamlSafeLoad(yamlReplyTemplate)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(chat_id=update.effective_chat.id,text=botReplyTemplate['start'])

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(chat_id=update.effective_chat.id,text=botReplyTemplate['help'])

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(chat_id=update.effective_chat.id, text=askNeko(update.message.text))
    
async def chatStream(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    steamID = int(round(time() * 1000))
    accumulatedText = ""
    buffer = ""
    flushInterval = 0.05
    bufferMaxSize = 30
    lastFlush = asyncio.get_event_loop().time()

    async for delta in askNekoStream(update.message.text):
        buffer += delta
        now = asyncio.get_event_loop().time()

        if now - lastFlush >= flushInterval or len(buffer) > bufferMaxSize:
            accumulatedText += buffer
            while True:
                try:
                    await context.bot.send_message_draft(chat_id=update.effective_chat.id, draft_id=steamID, text=accumulatedText)
                    break
                except RetryAfter as e:
                    await asyncio.sleep(e.retry_after)

            buffer = ""
            lastFlush = now

    if buffer:
        accumulatedText += buffer
        while True:
            try:
                await context.bot.send_message_draft(chat_id=update.effective_chat.id, draft_id=steamID, text=accumulatedText)
                break
            except RetryAfter as e:
                await asyncio.sleep(e.retry_after)
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=accumulatedText)
    
def main() -> None:
    application = Application.builder().token(botConfig['Token']).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    
    # application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chatStream))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
