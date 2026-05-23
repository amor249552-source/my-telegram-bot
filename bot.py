import os
import logging
import anthropic
import requests
import tempfile
from telegram.ext import Application, MessageHandler, filters, CommandHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")

SYSTEM_PROMPT = """Ти — особистий AI-асистент для підприємця у сфері бізнесу та продажів.
Твої задачі: допомагати з продажами, скриптами, переговорами, діловими листами, аналізом клієнтів, стратегією бізнесу.
Говори українською. Будь конкретним і практичним."""

conversation_history = {}
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def get_claude_response(user_id, message):
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    conversation_history[user_id].append({"role": "user", "content": message})
    if len(conversation_history[user_id]) > 20:
        conversation_history[user_id] = conversation_history[user_id][-20:]
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=conversation_history[user_id],
    )
    assistant_message = response.content[0].text
    conversation_history[user_id].append({"role": "assistant", "content": assistant_message})
    return assistant_message

def text_to_speech(text):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": ELEVENLABS_API_KEY}
    data = {"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        return response.content
    return None

async def handle_start(update, context):
    await update.message.reply_text("👋 Привіт! Я твій AI-асистент для бізнесу. Пиши!")

async def handle_text(update, context):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    response_text = get_claude_response(update.effective_user.id, update.message.text)
    await update.message.reply_text(response_text)
    if ELEVENLABS_API_KEY:
        audio = text_to_speech(response_text[:500])
        if audio:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio)
                f.flush()
                await context.bot.send_voice(chat_id=update.effective_chat.id, voice=open(f.name, "rb"))

async def handle_voice(update, context):
    await update.message.reply_text("🎤 Напишіть текстом — розпізнавання голосу буде в наступній версії.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    logger.info("Бот запущено!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
