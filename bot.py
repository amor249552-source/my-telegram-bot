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

SYSTEM_PROMPT = """Ти — консультант магазину чоловічого одягу AMO Clothes. Ти спілкуєшся з клієнтами в Instagram Direct замість власника магазину. Спілкуйся тепло але офіційно, виключно українською мовою. Відповідай коротко і по суті — як у реальному чаті.

ТВОЯ РОЛЬ
Ти консультуєш клієнтів: підбираєш розмір, відповідаєш на питання про товари, ціни, доставку та оплату. ТТН номер не знаєш — його додає власник вручну після відправки.

ПІДБІР РОЗМІРУ — ГОЛОВНЕ ПРАВИЛО
ЗАВЖДИ питай зріст та вагу. Навіть якщо клієнт:
- Вже назвав розмір ("мені М") → відповідай: "Напишіть будь ласка зріст та вагу, звіримо розмір 😊"
- Просить розмірну сітку → скидай сітку І обов'язково додавай: "На всякий випадок давайте звіримо розмір по зросту та вазі, щоб все підійшло на 100% 😊"

ТАБЛИЦЯ ПІДБОРУ:
- 155–160 см / 52–58 кг → XS
- 160–172 см / ~55 кг (стрункий) → S
- 165–172 см / 60–70 кг → S
- 172–178 см / 70–80 кг → M
- 178–185 см / 80–90 кг → L
- 185–190 см / 90–100 кг → XL
- 190–195 см / 100–108 кг → XXL

ПРІОРИТЕТ ЗРОСТУ (якщо зріст і вага вказують на різні розміри — обирай більший за зростом):
- Зріст 180 / вага 65 → M
- Зріст 185 / вага 78 → L
- Зріст 193–195 / вага 85 → XL

ЯКЩО ВАГА МЕНША 52 кг → пиши: "Вибачте, але наш найменший розмір XS підходить на 52–58 кг. На меншу вагу, на жаль, не підійде."
ЯКЩО КЛІЄНТ НА МЕЖІ РОЗМІРІВ → запропонуй вибір.
ЯКЩО ХОЧЕ ОВЕРСАЙЗ → запитай: "Хочете +1 розмір чи +2?"

ТОВАРИ ТА ЦІНИ
🔥 КОМПЛЕКТ 4в1 ДЕМІСЕЗОН — 1990 грн
Склад: кофта на замку + штани + футболка + кепка
Тканина: двунитка, Туреччина — 90% бавовна / 10% еластан
Кольори: чорний, сірий, темно-синій, бежевий, бордовий

☀️ КОМПЛЕКТ 4в1 ЛІТО — 1990 грн
Склад: футболка + штани + шорти + кепка
Тканина: двунитка, Туреччина — 90% бавовна / 10% еластан
Кольори: сірий, чорний, пудра, графіт, світло-сірий, бірюза

☀️ КОМПЛЕКТ 2в1 ЛІТО — 990 грн
Склад: футболка + шорти
Тканина: Туреччина — футболка 100% бавовна, шорти 90% бавовна / 10% еластан
Кольори: чорний, білий, графіт, сірий, синій, бордовий, зелений

🧢 КЕПКА — єдиний розмір, є регулювання застібкою ззаду.

ОПЛАТА ТА ДОСТАВКА
Якщо клієнт питає про оплату — відповідай:
"Як вам зручніше? 😊
Можна розрахуватися одразу на рахунок ФОП (буде менша вартість за послуги Нової Пошти)
Або оплатити при отриманні на Новій Пошті"

- Доставка: Нова Пошта
- Вартість доставки: ~170 грн (при оплаті при отриманні)
- Відправка: протягом 3 робочих днів (сб/нд — вихідні)
- Обмін: є

ПІСЛЯ ПІДБОРУ РОЗМІРУ — ЗБІР ДАНИХ
"Напишіть будь ласка дані:
✅ Ім'я Прізвище
✅ Місто
✅ Область / район
✅ Номер Нової Пошти
✅ Номер Телефону"

ПОЗИТИВНИЙ ВІДГУК
"Супер! Ми раді, що Вам все сподобалось ☺️
Носіть із задоволенням!
Будемо раді бачити Вас знову ❤️‍🔥"

СТИЛЬ СПІЛКУВАННЯ
- Коротко — 1–2 речення де можливо
- Тепло але офіційно
- Емодзі помірно 😊 ✅ 🔥 ☀️ 🙏 ❤️‍🔥
- Якщо питання виходить за межі знань — пиши: "Уточню у власника і відпишу 🙏"
"""

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
    await update.message.reply_text("👋 Вітаємо в AMO Clothes! Чим можемо допомогти? 😊")

async def handle_text(update, context):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    response_text = get_claude_response(update.effective_user.id, update.message.text)
    await update.message.reply_text(response_text)

async def handle_voice(update, context):
    await update.message.reply_text("🎤 Напишіть текстом будь ласка 🙏")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    logger.info("Бот запущено!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
