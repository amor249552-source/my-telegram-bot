import os
import logging
import anthropic
import requests
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, CommandHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")
YOUR_TELEGRAM_ID = int(os.environ.get("YOUR_TELEGRAM_ID", "0"))

SYSTEM_PROMPT = """Ти — особистий AI-асистент для підприємця у сфері бізнесу та продажів.
Твої задачі: допомагати з продажами, скриптами, переговорами, діловими листами, аналізом клієнтів, стратегією бізнесу.
Говори українською. Будь конкретним і практичним."""

conversation_history = {}
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def is_authorized(user_id):
    return True

def get_claude_response(user_id, message):
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    conversation_history[user_id].append({"role": "user", "content": message})
    if len(conversation_history[user_id]) > 20:
        conversation_history[user_id] = conversation_history[user_id][-20:]
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=conversation_history[user_id],
    )
    assistant_message = response.content[0].text
    conversation_history[user_id].append({"role": "assistant", "content": assistant_message})
    return assistant_message

async def handle_start(update, context):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Доступ заборонено.")
        return
    await update.message.reply_text("👋 Привіт! Я твій AI-асистент для бізнесу. Пиши!")

async def handle_text(update, context):
    if not is_authorized(update.effective_user.id):
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    response = get_claude_response(update.effective_user.id, update.message.text)
    await update.message.reply_text(response)

async def handle_voice(update, context):
    if not is_authorized(update.effective_user.id):
        return

    await update.message.reply_text("🎤 Голосові повідомлення скоро будуть доступні.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    logger.info("Бот запущено!")
    app.run_polling()

if __name__ == "__main__":
    main()
