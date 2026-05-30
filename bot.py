import os
import logging
import anthropic
import requests
import json
import re
from flask import Flask, request, jsonify
import threading
import asyncio
from telegram.ext import Application, MessageHandler, filters, CommandHandler
from telegram import Bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
INSTAGRAM_TOKEN = os.environ.get("INSTAGRAM_TOKEN")
FACEBOOK_TOKEN = os.environ.get("FACEBOOK_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
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

ВАЖЛИВО: Коли клієнт надає дані для відправки (ім'я, місто, телефон, відділення), обов'язково підтвердь замовлення і в кінці своєї відповіді додай спеціальний блок у форматі:
##ЗАМОВЛЕННЯ##
Імʼя: [імʼя клієнта]
Телефон: [телефон]
Місто: [місто та область]
Нова Пошта: [номер відділення]
Товар: [назва товару, колір, розмір]
Фото: [посилання на фото товару]
##КІНЕЦЬ##
"""

conversation_history = {}
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
_telegram_bot = None


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


def parse_order(text):
    """Витягує дані замовлення з відповіді Claude"""
    match = re.search(r'##ЗАМОВЛЕННЯ##(.*?)##КІНЕЦЬ##', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def clean_response(text):
    """Прибирає блок замовлення з відповіді для клієнта"""
    return re.sub(r'##ЗАМОВЛЕННЯ##.*?##КІНЕЦЬ##', '', text, flags=re.DOTALL).strip()


def notify_owner_order(order_text, channel):
    """Надсилає замовлення власнику в Telegram"""
    def send():
        try:
            bot = Bot(token=TELEGRAM_TOKEN)
            # Витягуємо посилання на фото
            photo_match = re.search(r'Фото:\s*(https?://\S+)', order_text)
            photo_url = photo_match.group(1) if photo_match else None

            message = f"🛍 НОВЕ ЗАМОВЛЕННЯ ({channel})!\n\n{order_text}"

            async def _send():
                await bot.send_message(
                    chat_id=YOUR_TELEGRAM_ID,
                    text=message
                )
                if photo_url:
                    await bot.send_message(
                        chat_id=YOUR_TELEGRAM_ID,
                        text=f"📸 Фото товару:\n{photo_url}"
                    )

            asyncio.run(_send())
            logger.info("Order notification sent to owner!")
        except Exception as e:
            logger.error(f"Failed to notify owner: {e}")

    threading.Thread(target=send, daemon=True).start()


def send_instagram_message(recipient_id, message):
    url = "https://graph.instagram.com/v21.0/me/messages"
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message},
        "messaging_type": "RESPONSE"
    }
    response = requests.post(url, json=data, params={"access_token": INSTAGRAM_TOKEN})
    logger.info(f"Instagram send: {response.status_code} {response.text}")


def send_facebook_message(recipient_id, message):
    url = "https://graph.facebook.com/v21.0/me/messages"
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message},
        "messaging_type": "RESPONSE"
    }
    response = requests.post(url, json=data, params={"access_token": FACEBOOK_TOKEN})
    logger.info(f"Facebook send: {response.status_code} {response.text}")


def process_message(user_id, text, send_func, channel):
    """Обробляє повідомлення і перевіряє чи є замовлення"""
    reply = get_claude_response(user_id, text)
    order = parse_order(reply)
    clean_reply = clean_response(reply)

    if order:
        notify_owner_order(order, channel)

    send_func(clean_reply)
    return clean_reply


@app.route("/", methods=["GET"])
def health():
    return "AMO Clothes Bot is running! ✅", 200


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook verified!")
        return challenge, 200
    return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def handle_webhook():
    data = request.json
    logger.info(f"Webhook data: {json.dumps(data)}")
    try:
        object_type = data.get("object", "")

        if object_type == "instagram":
            for entry in data.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    for msg in value.get("messages", []):
                        sender_id = msg.get("from", {}).get("id")
                        text = msg.get("text", {}).get("body", "") if isinstance(msg.get("text"), dict) else msg.get("text", "")
                        if text and sender_id:
                            logger.info(f"Instagram DM from {sender_id}: {text}")
                            process_message(
                                f"ig_{sender_id}", text,
                                lambda reply: send_instagram_message(sender_id, reply),
                                "Instagram"
                            )

                for messaging in entry.get("messaging", []):
                    sender_id = messaging.get("sender", {}).get("id")
                    text = messaging.get("message", {}).get("text", "")
                    if text and sender_id:
                        process_message(
                            f"ig_{sender_id}", text,
                            lambda reply: send_instagram_message(sender_id, reply),
                            "Instagram"
                        )

        elif object_type == "page":
            for entry in data.get("entry", []):
                for messaging in entry.get("messaging", []):
                    if messaging.get("message", {}).get("is_echo"):
                        continue
                    sender_id = messaging.get("sender", {}).get("id")
                    text = messaging.get("message", {}).get("text", "")
                    if text and sender_id:
                        process_message(
                            f"fb_{sender_id}", text,
                            lambda reply: send_facebook_message(sender_id, reply),
                            "Facebook"
                        )

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)

    return jsonify({"status": "ok"}), 200


# ── TELEGRAM ──────────────────────────────────
def _run_telegram():
    async def main():
        tg_app = Application.builder().token(TELEGRAM_TOKEN).build()

        async def handle_start(update, context):
            await update.message.reply_text("👋 Вітаємо в AMO Clothes! Чим можу допомогти? 😊")

        async def handle_text(update, context):
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            user_id = f"tg_{update.effective_user.id}"
            text = update.message.text

            reply = get_claude_response(user_id, text)
            order = parse_order(reply)
            clean_reply = clean_response(reply)

            if order:
                notify_owner_order(order, "Telegram")

            await update.message.reply_text(clean_reply)

        tg_app.add_handler(CommandHandler("start", handle_start))
        tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

        async with tg_app:
            await tg_app.start()
            await tg_app.updater.start_polling(drop_pending_updates=True)
            logger.info("Telegram bot started!")
            await asyncio.sleep(float('inf'))

    asyncio.run(main())


_telegram_thread = threading.Thread(target=_run_telegram, daemon=True)
_telegram_thread.start()
logger.info("Telegram thread launched")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
