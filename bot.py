from yaml import safe_load as yamlSafeLoad
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

with open('./config.yaml', 'r') as yamlConfig:
    botConfig = yamlSafeLoad(yamlConfig)['TelegramBot']
    
if botConfig['DefaultLanguage'] == 'CN':
    with open('./replyTemplate_CN.yaml', 'r') as yamlReplyTemplate:
        botReplyTemplate = yamlSafeLoad(yamlReplyTemplate)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id,text=botReplyTemplate['start'])

start_handler = CommandHandler('start', start)

application = ApplicationBuilder().token(botConfig['Token']).build()
application.add_handler(start_handler)
application.run_polling()
