import os
import json
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
)

CHOOSE_TOPIC, ASK_QUESTION = range(2)

# Загружаем вопросы из JSON
with open("questions.json", "r", encoding="utf-8") as f:
    questions_data = json.load(f)

# Хранилище данных
user_data = {}


# Интерпретация результата
def interpret_result(score: int) -> str:
    if score >= 25:
        return "🏆 *Осознанный архитектор своей жизни*\nВы — пример для подражания. Ваши сильные стороны: самоорганизация, стратегическое мышление и устойчивость к неудачам."
    elif score >= 18:
        return "📈 *Развивающийся практик*\nВы на правильном пути, но вам не хватает последовательности. Совет: сфокусируйтесь на 1-2 ключевых привычках."
    else:
        return "🌱 *Стихийный мечтатель*\nПока что тема саморазвития дается вам сложно. Совет: начните с самой маленькой и конкретной цели на эту неделю."


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_data:
        del user_data[user_id]

    keyboard = [
        [InlineKeyboardButton(data["title"], callback_data=f"topic|{key}")]
        for key, data in questions_data.items()
    ]
    markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(
            "🧠 *Выберите тему теста:*", reply_markup=markup, parse_mode="Markdown"
        )
    elif update.callback_query:
        await context.bot.send_message(
            chat_id=update.callback_query.from_user.id,
            text="🧠 *Выберите тему теста:*",
            reply_markup=markup,
            parse_mode="Markdown",
        )

    return CHOOSE_TOPIC


# Обработка выбора темы
async def choose_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, topic_key = query.data.split("|")
    topic_data = questions_data[topic_key]

    user_data[query.from_user.id] = {
        "topic": topic_data["title"],
        "questions": topic_data["questions"],
        "current": 0,
        "score": 0,
    }

    return await ask_question(query, context)


# Следующий вопрос или результат
async def ask_question(source, context: ContextTypes.DEFAULT_TYPE):
    user_id = source.from_user.id
    user = user_data[user_id]
    index = user["current"]
    questions = user["questions"]

    if index >= len(questions):
        score = user["score"]
        result_text = interpret_result(score)

        try:
            keyboard = [[InlineKeyboardButton("🔁 Пройти заново", callback_data="restart")]]
            markup = InlineKeyboardMarkup(keyboard)

            with open("result.png", "rb") as photo_file:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=photo_file,
                    caption=(
                        "🧾 *Ваш результат визуально*\n\n"
                        f"🎉 *Тест завершён!*\n\n"
                        f"🎯 *Ваши баллы:* `{score}` из `{len(questions) * 3}`\n\n"
                        f"{result_text}"
                    ),
                    reply_markup=markup,
                    parse_mode="Markdown",
                )
        except Exception as e:
            print("❌ Ошибка при отправке результата:", e)

        return ConversationHandler.END

    question = questions[index]
    keyboard = [
        [InlineKeyboardButton(opt["text"], callback_data=f"answer|{opt['score']}")]
        for opt in question["options"]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    try:
        await source.message.edit_text(
            f"🧠 *Вопрос {index + 1} из {len(questions)}:*\n\n{question['question']}",
            reply_markup=markup,
            parse_mode="Markdown",
        )
    except Exception:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🧠 *Вопрос {index + 1} из {len(questions)}:*\n\n{question['question']}",
            reply_markup=markup,
            parse_mode="Markdown",
        )

    return ASK_QUESTION


# Обработка ответа
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, score_str = query.data.split("|")
    score = int(score_str)

    user = user_data.get(query.from_user.id)
    if user:
        user["score"] += score
        user["current"] += 1
        return await ask_question(query, context)
    else:
        await query.message.reply_text("⚠️ Ошибка. Попробуйте /start заново.")
        return ConversationHandler.END


# Обработка "Пройти заново"
async def start_over(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id in user_data:
        del user_data[query.from_user.id]

    return await start(update, context)


# Команда /cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Тест отменён.")
    return ConversationHandler.END


# Запуск бота
def main():
    import os

    # ✅ Берём токен из переменной окружения, если есть
    token = os.getenv("BOT_TOKEN")

    # ✅ Если переменной нет, используем токен прямо из кода
    if not token:
        token = "8407448825:AAH3-75Wnra_LetBwx8E9i10VoZMqNWjbvc"

    app = ApplicationBuilder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_TOPIC: [CallbackQueryHandler(choose_topic, pattern="^topic\\|")],
            ASK_QUESTION: [CallbackQueryHandler(handle_answer, pattern="^answer\\|")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(start_over, pattern="^restart$"))

    print("✅ Бот запущен. Ожидание команд...")
    app.run_polling()


if __name__ == "__main__":
    main()

