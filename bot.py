import asyncio
from time import time

from yaml import safe_load as yamlSafeLoad, dump as yamlDump
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.error import RetryAfter, BadRequest, TimedOut

from neko import askNeko, askNekoStream

with open('./config/config.yaml', 'r') as yamlConfig:
    botConfig = yamlSafeLoad(yamlConfig)['TelegramBot']
    
if botConfig['Language'] == 'CN':
    with open('./config/replyTemplate_CN.yaml', 'r') as yamlReplyTemplate:
        botReplyTemplate = yamlSafeLoad(yamlReplyTemplate)

debugMode = False

async def sendMessage(context: ContextTypes.DEFAULT_TYPE, chatID: int, text: str) -> None:
    while True:
        try:
            await context.bot.send_message(chat_id=chatID, text=text)
            break
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after)
        except TimedOut as e:
            pass
        except BadRequest as e:
            asyncio.create_task(sendMessage(context, chatID, botReplyTemplate['BadRequest']))
            break
        except Exception as e:
            asyncio.create_task(sendMessage(context, chatID, botReplyTemplate['BadRequest']))
            break

async def sendStreamingMessage(context: ContextTypes.DEFAULT_TYPE, chatID: int, draftID: int, text: str) -> None:
    while True:
        try:
            await context.bot.send_message_draft(chat_id=chatID, draft_id=draftID, text=text)
            break
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after)
        except TimedOut as e:
            pass
        except BadRequest as e:
            asyncio.create_task(sendMessage(context, chatID, botReplyTemplate['BadRequest']))
            break
        except Exception as e:
            asyncio.create_task(sendMessage(context, chatID, botReplyTemplate['BadRequest']))
            break

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    asyncio.create_task(sendMessage(context, update.effective_chat.id, botReplyTemplate['start']))

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    asyncio.create_task(sendMessage(context, update.effective_chat.id, botReplyTemplate['help']))
    
async def setting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    asyncio.create_task(sendMessage(context, update.effective_chat.id, botReplyTemplate['setting']))
    
async def settingStreamingResponse_ON(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    botConfig['StreamingResponse'] = True
    asyncio.create_task(sendMessage(context, update.effective_chat.id, "流式回复已开启喵~~"))
    with open('./config/config.yaml', 'w', encoding='utf-8') as f:
        yamlDump(botConfig, f, default_flow_style=False, allow_unicode=True)

async def settingStreamingResponse_OFF(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    botConfig['StreamingResponse'] = False
    asyncio.create_task(sendMessage(context, update.effective_chat.id, "流式回复已关闭喵~~"))
    with open('./config/config.yaml', 'w', encoding='utf-8') as f:
        yamlDump(botConfig, f, default_flow_style=False, allow_unicode=True)

async def settingDebugMode_ON(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global debugMode
    debugMode = True
    asyncio.create_task(sendMessage(context, update.effective_chat.id, "调试模式已开启喵~~"))
    
async def settingDebugMode_OFF(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global debugMode
    debugMode = False
    asyncio.create_task(sendMessage(context, update.effective_chat.id, "调试模式已关闭喵~~"))

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    asyncio.create_task(sendMessage(context, update.effective_chat.id, askNeko(update.message.text)))
    
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
            
            asyncio.create_task(sendStreamingMessage(context, update.effective_chat.id, steamID, accumulatedText))

            buffer = ""
            lastFlush = now

    if buffer:
        accumulatedText += buffer
        asyncio.create_task(sendStreamingMessage(context, update.effective_chat.id, steamID, accumulatedText))
    
    asyncio.create_task(sendMessage(context, update.effective_chat.id, accumulatedText))

async def chatDebug(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.bot.send_message(update.effective_chat.id, "Debug Mode\nInput: " + update.message.text + "\n\naskNekoOutput:")
    await chat(update, context)
    context.bot.send_message(update.effective_chat.id, "askNekoStream Output:")
    await chatStream(update, context)
    
async def chatResponse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if debugMode:
        await chatDebug(update, context)
    else:
        if botConfig['StreamingResponse']:
            await chatStream(update, context)
        else:
            await chat(update, context)    
    
    
def main() -> None:
    application = Application.builder().token(botConfig['Token']).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    
    application.add_handler(CommandHandler("setting", setting))
    application.add_handler(CommandHandler("settingStreamingResponse_ON", settingStreamingResponse_ON))
    application.add_handler(CommandHandler("settingStreamingResponse_OFF", settingStreamingResponse_OFF))
    application.add_handler(CommandHandler("settingDebugMode_ON", settingDebugMode_ON))
    application.add_handler(CommandHandler("settingDebugMode_OFF", settingDebugMode_OFF))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chatResponse))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
