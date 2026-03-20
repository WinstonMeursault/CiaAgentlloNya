from yaml import safe_load as yamlSafeLoad

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

with open('./config.yaml', 'r') as yamlConfig:
    botConfig = yamlSafeLoad(yamlConfig)['TelegramBot']
    
if botConfig['DefaultLanguage'] == 'CN':
    with open('./replyTemplate_CN.yaml', 'r') as yamlReplyTemplate:
        botReplyTemplate = yamlSafeLoad(yamlReplyTemplate)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(chat_id=update.effective_chat.id,text=botReplyTemplate['start'])

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(chat_id=update.effective_chat.id,text=botReplyTemplate['help'])

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # TODO: Chat Function
    
    await update.message.reply_text(update.message.text)    # echo back the message for testing


def main() -> None:
    application = Application.builder().token(botConfig['Token']).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
