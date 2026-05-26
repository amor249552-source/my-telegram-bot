import os
import logging
import anthropic
import requests
import json
import hmac
import hashlib
from flask import Flask, request, jsonify
from telegram.ext import Application
import threading
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
INSTAGRAM_TOKEN = os.environ.get("INSTAGRAM_TOKEN")
FACEBOOK_TOKEN = os.environ.get("FACEBOOK_TOKEN")       # Page Access Token для Messenger
INSTAGRAM_APP_SECRET = os.environ.get("INSTAGRAM_APP_SECRET")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
YOUR_TELEGRAM_ID = int(os.environ.get("YOUR_TELEGRAM_ID", "411960109"))

app = Flask(__name__)

SYSTEM_PROMPT = """Ти — консультант магазину чоловічого одягу AMO Clothes. Спілкуйся тепло але офіційно, виключно українською мовою. Відповідай коротко і по суті — як у реальному чаті. Якщо клієнт просить фото — скидай посилання на фото відповідного товару.

ПІДБІР РОЗМІРУ — ГОЛОВНЕ ПРАВИЛО
ЗАВЖДИ питай зріст та вагу. Навіть якщо клієнт вже назвав розмір → "Напишіть будь ласка зріст та вагу, звіримо розмір 😊"

ТАБЛИЦЯ ПІДБОРУ:
- 155–160 см / 52–58 кг → XS
- 160–172 см / 55–70 кг → S
- 172–178 см / 70–80 кг → M
- 178–185 см / 80–90 кг → L
- 185–190 см / 90–100 кг → XL
- 190–195 см / 100–108 кг → XXL

ПРІОРИТЕТ ЗРОСТУ:
- Зріст 180 / вага 65 → M
- Зріст 185 / вага 78 → L
- Зріст 193–195 / вага 85 → XL

ЯКЩО ВАГА МЕНША 52 кг → "Вибачте, але наш найменший розмір XS підходить на 52–58 кг. На меншу вагу, на жаль, не підійде."
ЯКЩО НА МЕЖІ → "На [вага] кг — [менший] буде по фігурі, [більший] — більш вільний. Як більше подобається?"
ЯКЩО ХОЧЕ ОВЕРСАЙЗ → "Хочете +1 розмір чи +2?"

ВАЖЛИВО ПРО КОЛЬОРИ:
Є кілька відтінків сірого — завжди уточнюй який саме.
Бежевий = кофейний = коричневий. Бірюзовий = м'ятний. Хакі = зелений. Бордовий = червоний.

ТОВАРИ ТА ФОТО

КОМПЛЕКТ 2в1 ЛІТО — 890 грн (Футболка + Шорти):
- Синій / Електрик: https://photos.app.goo.gl/3Q52swQPk2EYwu1A6
- Темно-сірий / Графіт: https://photos.app.goo.gl/4yMEwjRXgcQstYz17
- Бордовий / Червоний: https://photos.app.goo.gl/ZqbkbWj4rqUy61aNA
- Чорний: https://photos.app.goo.gl/xN4fakAT9aGZsgC48
- Хакі / Зелений: https://photos.app.goo.gl/9RGbrurTJkPb9Rab8
- Білий: https://photos.app.goo.gl/sj6hnK1fejnF4YPG6

КОМПЛЕКТ 3в1 ЛІТО — 990 грн (Футболка + Шорти + Кепка):
- Хакі / Зелений: https://photos.app.goo.gl/E25PHPBRPUM7ZnaG9
- Чорний: https://photos.app.goo.gl/b53qw4NCrhrTHYjeA
- Бордовий: https://photos.app.goo.gl/FWcdRmCKAhFFKNnu9
- Білий: https://photos.app.goo.gl/7kZmnJGBtz5rBjeB8
- М'ята / Бірюзовий: https://photos.app.goo.gl/TDfMxEZH4A1Efomh6
- Електрик / Синій: https://photos.app.goo.gl/7LxxnFox2zisAfmR9
- Жовтий: https://photos.app.goo.gl/HeEqrpUDETHddSmY8
- Світло-сірий: https://photos.app.goo.gl/KgTBXDQZg97VqBNz8

КОМПЛЕКТ 4в1 ДЕМІСЕЗОН — 1990 грн (Кофта + Штани + Футболка + Кепка):
- Бежевий / Кофейний: https://photos.app.goo.gl/yUH2BQRtHNATe5h19
- Чорний: https://photos.app.goo.gl/bmXpQLKYzozDxpi1A
- Бордовий: https://photos.app.goo.gl/fBonYo8jie6dh1zt5
- Темно-синій: https://photos.app.goo.gl/756qQMUHZM8JnEd28
- Світло-сірий: https://photos.app.goo.gl/ZCo3ZdpT7vwBgyEn6

КОМПЛЕКТ 4в1 ЛІТО — 1990 грн (Футболка + Шорти + Штани + Кепка):
- Темно-сірий / Графіт: https://photos.app.goo.gl/rFcqAWQsUZmSikEA8
- Світло-сірий: https://photos.app.goo.gl/sqYxUdCHv5vUpVa4A
- Бірюзовий: https://photos.app.goo.gl/mA5pbZ8DmyYeHvjH7
- Бежевий: https://photos.app.goo.gl/pruYxK5jz3yTi1S17
- Чорний: https://photos.app.goo.gl/UsXMriuexTe9TBYJ9
- Графіт: https://photos.app.goo.gl/mz4wrVnb85jBrqEF9

ОПЛАТА ТА ДОСТАВКА
"Як вам зручніше? 😊
Можна розрахуватися одразу на рахунок ФОП або оплатити при отриманні на Новій Пошті"
- Доставка ~170 грн, відправка 3 робочих дні, обмін є.

ПІСЛЯ ПІДБОРУ — ЗБІР ДАНИХ
"Напишіть будь ласка:
✅ Ім'я Прізвище
✅ Місто та область
✅ Номер Нової Пошти
✅ Номер Телефону"

ПОЗИТИВНИЙ ВІДГУК
"Супер! Ми раді, що Вам все сподобалось ☺️ Носіть із задоволенням! Будемо раді бачити Вас знову ❤️‍🔥"

ОБМІН/ПОВЕРНЕННЯ/ПЕРЕДОПЛАТА → "Зачекайте будь ласка, уточню у власника і відпишу 🙏"

СТИЛЬ: коротко, тепло, емодзі помірно. Незнайоме → "Уточню у власника і відпишу 🙏"
"""

conversation_history = {}
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
telegram_app = None


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


def send_instagram_message(recipient_id, message):
    """Відправка повідомлення в Instagram DM"""
    url = "https://graph.instagram.com/v21.0/me/messages"
    headers = {"Content-Type": "application/json"}
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message},
        "messaging_type": "RESPONSE"
    }
    params = {"access_token": INSTAGRAM_TOKEN}
    response = requests.post(url, headers=headers, json=data, params=params)
    logger.info(f"Instagram send response: {response.status_code} {response.text}")
    return response


def send_facebook_message(recipient_id, message):
    """Відправка повідомлення в Facebook Messenger"""
    url = "https://graph.facebook.com/v21.0/me/messages"
    headers = {"Content-Type": "application/json"}
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message},
        "messaging_type": "RESPONSE"
    }
    params = {"access_token": FACEBOOK_TOKEN}
    response = requests.post(url, headers=headers, json=data, params=params)
    logger.info(f"Facebook send response: {response.status_code} {response.text}")
    return response


def notify_owner(message, tg_app):
    async def send():
        await tg_app.bot.send_message(chat_id=YOUR_TELEGRAM_ID, text=message)
    asyncio.run(send())


def check_order_keywords(text):
    keywords = ["нова пошта", "відділення", "область", "телефон", "прізвище"]
    return any(kw in text.lower() for kw in keywords)


# ──────────────────────────────────────────────
# WEBHOOK — верифікація (GET)
# ──────────────────────────────────────────────
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook verified successfully!")
        return challenge, 200
    logger.warning("Webhook verification failed!")
    return "Forbidden", 403


# ──────────────────────────────────────────────
# WEBHOOK — отримання повідомлень (POST)
# ──────────────────────────────────────────────
@app.route("/webhook", methods=["POST"])
def handle_webhook():
    data = request.json
    logger.info(f"Webhook received: {json.dumps(data)}")

    try:
        object_type = data.get("object", "")

        # ── INSTAGRAM DM ──────────────────────────────
        if object_type == "instagram":
            for entry in data.get("entry", []):

                # Формат 1: через "changes" (Instagram Webhooks API)
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    for msg in messages:
                        sender_id = msg.get("from", {}).get("id")
                        text = msg.get("text", {}).get("body", "") if isinstance(msg.get("text"), dict) else msg.get("text", "")
                        if text and sender_id:
                            logger.info(f"Instagram DM (changes) from {sender_id}: {text}")
                            response_text = get_claude_response(f"ig_{sender_id}", text)
                            send_instagram_message(sender_id, response_text)
                            if check_order_keywords(text) and telegram_app:
                                notify_msg = f"📦 НОВЕ ЗАМОВЛЕННЯ (Instagram)!\n\nКлієнт ID: {sender_id}\nДані:\n{text}"
                                threading.Thread(target=notify_owner, args=(notify_msg, telegram_app)).start()

                # Формат 2: через "messaging" (старий формат)
                for messaging in entry.get("messaging", []):
                    sender_id = messaging.get("sender", {}).get("id")
                    message = messaging.get("message", {})
                    text = message.get("text", "")
                    if text and sender_id:
                        logger.info(f"Instagram DM (messaging) from {sender_id}: {text}")
                        response_text = get_claude_response(f"ig_{sender_id}", text)
                        send_instagram_message(sender_id, response_text)
                        if check_order_keywords(text) and telegram_app:
                            notify_msg = f"📦 НОВЕ ЗАМОВЛЕННЯ (Instagram)!\n\nКлієнт ID: {sender_id}\nДані:\n{text}"
                            threading.Thread(target=notify_owner, args=(notify_msg, telegram_app)).start()

        # ── FACEBOOK MESSENGER ────────────────────────
        elif object_type == "page":
            for entry in data.get("entry", []):
                for messaging in entry.get("messaging", []):
                    sender_id = messaging.get("sender", {}).get("id")
                    message = messaging.get("message", {})
                    text = message.get("text", "")
                    # Ігноруємо echo (повідомлення від самої сторінки)
                    if message.get("is_echo"):
                        continue
                    if text and sender_id:
                        logger.info(f"Facebook Messenger from {sender_id}: {text}")
                        response_text = get_claude_response(f"fb_{sender_id}", text)
                        send_facebook_message(sender_id, response_text)
                        if check_order_keywords(text) and telegram_app:
                            notify_msg = f"📦 НОВЕ ЗАМОВЛЕННЯ (Facebook)!\n\nКлієнт ID: {sender_id}\nДані:\n{text}"
                            threading.Thread(target=notify_owner, args=(notify_msg, telegram_app)).start()

        else:
            logger.warning(f"Unknown object type: {object_type}")

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)

    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def health():
    return "AMO Clothes Bot is running! ✅", 200


# ──────────────────────────────────────────────
# TELEGRAM
# ──────────────────────────────────────────────
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


async def run_telegram():
    global telegram_app
    telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()

    from telegram.ext import MessageHandler, filters, CommandHandler

    async def handle_start(update, context):
        await update.message.reply_text("👋 Вітаємо в AMO Clothes! Чим можу допомогти? 😊")

    async def handle_text(update, context):
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        response = get_claude_response(f"tg_{update.effective_user.id}", update.message.text)
        await update.message.reply_text(response)

    telegram_app.add_handler(CommandHandler("start", handle_start))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.updater.start_polling(drop_pending_updates=True)
    logger.info("Telegram bot started!")


def main():
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    asyncio.run(run_telegram())


if __name__ == "__main__":
    main()
