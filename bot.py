import os
import json
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

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
    MessageHandler,
    filters,
)

TEST_CHOOSE_TOPIC, TEST_ASK_QUESTION, MOOD_WAIT_RATING, MOOD_WAIT_NOTE = range(4)

# Загружаем вопросы из JSON
with open("questions.json", "r", encoding="utf-8") as f:
    questions_data = json.load(f)

# Дополнительные данные и подсказки
SELF_CARE_TIPS = [
    "Поставьте на сегодня одну маленькую достижимую цель и отметьте её в конце дня.",
    "Напомните себе о том, за что вы благодарны. Даже 3 вещи помогут переключить фокус.",
    "Выделите 10 минут на дыхательное упражнение или растяжку, чтобы вернуть себе ресурс.",
    "Попросите поддержки у близкого человека — это не признак слабости, а забота о себе.",
    "Сделайте паузу в новостях и социальных сетях на пару часов, чтобы снизить нагрузку.",
    "Проверьте, как вы дышите: глубокий вдох через нос и медленный выдох через рот помогает снизить тревогу.",
    "Составьте короткий список того, что приносит вам радость, и выберите что-то одно прямо сейчас.",
]

BREATHING_GUIDE = [
    "1. Найдите удобное положение, расправьте плечи.",
    "2. Вдохните через нос на 4 счета (1…2…3…4).",
    "3. Задержите дыхание на 2 счета.",
    "4. Медленно выдохните через рот на 6 счетов.",
    "5. Повторите цикл 5–7 раз, наблюдая за ощущениями в теле.",
]

SUPPORT_RESOURCES = [
    (
        "🌐 Ясно",  # title
        "Платформа с психологами и психотерапевтами.",
        "https://yasno.live/",
    ),
    (
        "📘 Терапия принятия и ответственности",
        "Бесплатный гайд по управлению эмоциями.",
        "https://contextualscience.org/free_guides",
    ),
    (
        "📞 Линия доверия 8-800-2000-122",
        "Круглосуточно, анонимно, бесплатно.",
        "tel:88002000122",
    ),
    (
        "🌱 Meditopia",
        "Медитации и практики осознанности на русском языке.",
        "https://meditopia.com/ru",
    ),
]


def build_main_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🧪 Пройти тест", callback_data="menu|test")],
        [
            InlineKeyboardButton("💬 Совет дня", callback_data="menu|tip"),
            InlineKeyboardButton("🧘 Дыхание", callback_data="menu|breath"),
        ],
        [InlineKeyboardButton("📝 Дневник настроения", callback_data="menu|mood")],
        [
            InlineKeyboardButton("📚 Ресурсы", callback_data="menu|resources"),
            InlineKeyboardButton("ℹ️ О боте", callback_data="menu|about"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def format_mood_history(entries: List[Dict[str, Any]]) -> str:
    if not entries:
        return (
            "Пока что записей нет. Попробуйте отметить своё настроение — это поможет отследить динамику."
        )

    avg = sum(item["rating"] for item in entries) / len(entries)
    latest = entries[-5:]
    lines = [f"Средний уровень настроения: *{avg:.1f}* из 5"]
    lines.append("")
    lines.append("Последние заметки:")
    for item in reversed(latest):
        ts = item["timestamp"].strftime("%d.%m %H:%M")
        note = item.get("note")
        note_part = f" — _{note}_" if note else ""
        lines.append(f"• {ts}: {item['rating']}⭐{note_part}")
    return "\n".join(lines)


# Интерпретация результата
def interpret_result(score: int, max_score: int) -> str:
    ratio = score / max_score if max_score else 0

    if ratio >= 0.75:
        return (
            "🏆 *Осознанный архитектор своей жизни*\n"
            "Вы внимательно относитесь к своему состоянию и умеете поддерживать внутренний баланс."
        )
    if ratio >= 0.5:
        return (
            "📈 *Развивающийся практик*\n"
            "У вас уже есть полезные стратегии, но им не хватает регулярности. Выберите одну привычку и укрепите её."
        )
    return (
        "🌱 *Стихийный мечтатель*\n"
        "Сейчас вам нелегко удерживать фокус на себе. Начните с простых ежедневных действий и поддерживайте контакт с близкими."
    )


async def send_main_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, *, text: Optional[str] = None
):
    chat_id = update.effective_chat.id
    menu_text = text or (
        "Привет! Я психологический бот-помощник. "
        "Выбирайте, что хотите сделать прямо сейчас: пройти тест, записать настроение или получить вдохновение."
    )

    markup = build_main_menu()

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        try:
            await query.message.edit_text(
                menu_text, reply_markup=markup, parse_mode="Markdown"
            )
        except Exception:
            await context.bot.send_message(
                chat_id=chat_id,
                text=menu_text,
                reply_markup=markup,
                parse_mode="Markdown",
            )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=menu_text,
            reply_markup=markup,
            parse_mode="Markdown",
        )


# Команда /start и /menu
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("test", None)
    await send_main_menu(update, context)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_main_menu(update, context)


# Обработка выбора темы
async def start_test_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton(data["title"], callback_data=f"topic|{key}")]
        for key, data in questions_data.items()
    ]
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="menu|home")])

    markup = InlineKeyboardMarkup(keyboard)

    context.user_data.pop("test", None)

    try:
        await query.message.edit_text(
            "🧠 *Выберите тему теста:*",
            reply_markup=markup,
            parse_mode="Markdown",
        )
    except Exception:
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="🧠 *Выберите тему теста:*",
            reply_markup=markup,
            parse_mode="Markdown",
        )

    return TEST_CHOOSE_TOPIC


async def choose_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, topic_key = query.data.split("|")
    topic_data = questions_data[topic_key]

    context.user_data["test"] = {
        "topic": topic_data["title"],
        "questions": topic_data["questions"],
        "current": 0,
        "score": 0,
    }

    return await ask_question(query, context)


# Следующий вопрос или результат
async def ask_question(source, context: ContextTypes.DEFAULT_TYPE):
    user_id = source.from_user.id
    user = context.user_data.get("test")

    if not user:
        await context.bot.send_message(
            chat_id=user_id,
            text="⚠️ Не удалось найти активный тест. Нажмите /start и выберите тему заново.",
        )
        return ConversationHandler.END

    index = user["current"]
    questions = user["questions"]

    if index >= len(questions):
        score = user["score"]
        max_score = len(questions) * 3
        result_text = interpret_result(score, max_score)

        try:
            keyboard = [
                [InlineKeyboardButton("🔁 Пройти ещё раз", callback_data="menu|test")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="menu|home")],
            ]
            markup = InlineKeyboardMarkup(keyboard)

            with open("result.png", "rb") as photo_file:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=photo_file,
                    caption=(
                        "🧾 *Ваш результат визуально*\n\n"
                        f"🎉 *Тест завершён!*\n\n"
                        f"📚 *Тема:* {user['topic']}\n"
                        "\n"
                        f"🎯 *Ваши баллы:* `{score}` из `{max_score}`\n\n"
                        f"{result_text}"
                    ),
                    reply_markup=markup,
                    parse_mode="Markdown",
                )
        except Exception as e:
            print("❌ Ошибка при отправке результата:", e)

        context.user_data.pop("test", None)
        return ConversationHandler.END

    question = questions[index]
    keyboard = [
        [InlineKeyboardButton(opt["text"], callback_data=f"answer|{opt['score']}")]
        for opt in question["options"]
    ]
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="menu|home")])
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

    user = context.user_data.get("test")
    if user:
        user["score"] += score
        user["current"] += 1
        return await ask_question(query, context)
    else:
        await query.message.reply_text("⚠️ Ошибка. Попробуйте /start заново.")
        return ConversationHandler.END


# Команда /cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Тест отменён.")
    return ConversationHandler.END


# Обработка ежедневных советов
async def send_daily_tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    tip = random.choice(SELF_CARE_TIPS)
    keyboard = [
        [
            InlineKeyboardButton("♻️ Ещё совет", callback_data="menu|tip"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="menu|home"),
        ]
    ]

    try:
        await query.message.edit_text(
            f"💬 *Совет по заботе о себе:*\n\n{tip}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    except Exception:
        await query.message.reply_text(
            f"💬 *Совет по заботе о себе:*\n\n{tip}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )


# Дыхательное упражнение
async def send_breathing_practice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    steps = "\n".join(BREATHING_GUIDE)
    keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="menu|home")]]

    try:
        await query.message.edit_text(
            f"🧘 *Пятиминутная практика дыхания*\n\n{steps}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    except Exception:
        await query.message.reply_text(
            f"🧘 *Пятиминутная практика дыхания*\n\n{steps}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )


# Полезные ресурсы
async def send_resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lines = ["📚 *Подборка проверенных ресурсов:*", ""]
    for title, desc, url in SUPPORT_RESOURCES:
        lines.append(f"[{title}]({url}) — {desc}")
    text = "\n".join(lines)

    keyboard = [
        [InlineKeyboardButton("🏠 Главное меню", callback_data="menu|home")]
    ]

    try:
        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    except Exception:
        await query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )


# Информация о боте
async def send_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = (
        "ℹ️ *О боте*\n\n"
        "Я помогу вам отслеживать настроение, проходить короткие психологические тесты и собирать полезные практики. "
        "Бот не заменяет профессиональную помощь, но может стать поддержкой между сессиями."
    )
    keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="menu|home")]]

    try:
        await query.message.edit_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )
    except Exception:
        await query.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )


# Меню дневника настроения
async def show_mood_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("➕ Новая запись", callback_data="mood|new")],
        [InlineKeyboardButton("📊 Моя статистика", callback_data="mood|history")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="menu|home")],
    ]

    text = (
        "📝 *Дневник настроения*\n\n"
        "Записывайте свой эмоциональный фон, чтобы замечать динамику и факторы, которые на него влияют."
    )

    try:
        await query.message.edit_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )
    except Exception:
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )


async def start_mood_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["pending_mood"] = {}

    keyboard = [
        [
            InlineKeyboardButton("1 😔", callback_data="mood|rate|1"),
            InlineKeyboardButton("2 😕", callback_data="mood|rate|2"),
            InlineKeyboardButton("3 😐", callback_data="mood|rate|3"),
        ],
        [
            InlineKeyboardButton("4 🙂", callback_data="mood|rate|4"),
            InlineKeyboardButton("5 😄", callback_data="mood|rate|5"),
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data="mood|cancel")],
    ]

    try:
        await query.message.edit_text(
            "Как вы себя чувствуете по шкале от 1 до 5?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except Exception:
        await query.message.reply_text(
            "Как вы себя чувствуете по шкале от 1 до 5?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    return MOOD_WAIT_RATING


async def handle_mood_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, _, rating_str = query.data.split("|")
    rating = int(rating_str)

    context.user_data.setdefault("pending_mood", {})
    context.user_data["pending_mood"].update(
        {"rating": rating, "timestamp": datetime.now()}
    )

    keyboard = [
        [InlineKeyboardButton("Пропустить заметку", callback_data="mood|skip")],
        [InlineKeyboardButton("❌ Отмена", callback_data="mood|cancel")],
    ]

    try:
        await query.message.edit_text(
            "Опишите, что повлияло на ваше состояние (или нажмите \"Пропустить заметку\").",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except Exception:
        await query.message.reply_text(
            "Опишите, что повлияло на ваше состояние (или нажмите \"Пропустить заметку\").",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    return MOOD_WAIT_NOTE


async def save_mood_entry(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    note: str | None,
):
    entry = context.user_data.get("pending_mood")
    if not entry:
        return

    entry["note"] = note.strip() if note else None

    entries = context.user_data.setdefault("mood_entries", [])
    entries.append(entry.copy())
    context.user_data.pop("pending_mood", None)

    summary = format_mood_history(entries)

    keyboard = [
        [InlineKeyboardButton("➕ Новая запись", callback_data="mood|new")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="menu|home")],
    ]

    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=(
            "✅ Запись сохранена! Возвращайтесь к ней, чтобы заметить, что помогает вам чувствовать себя лучше.\n\n"
            f"{summary}"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def handle_mood_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note = update.message.text
    await save_mood_entry(update, context, note=note)
    return ConversationHandler.END


async def handle_mood_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await save_mood_entry(update, context, note=None)
    return ConversationHandler.END


async def cancel_mood_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        keyboard = [
            [InlineKeyboardButton("➕ Новая запись", callback_data="mood|new")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="menu|home")],
        ]
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="Запись отменена. Вы всегда можете вернуться позже.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    elif update.message:
        await update.message.reply_text(
            "Запись отменена. Возвращайтесь, когда будете готовы.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("Открыть меню", callback_data="menu|home")],
                ]
            ),
        )

    context.user_data.pop("pending_mood", None)
    return ConversationHandler.END


async def show_mood_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    summary = format_mood_history(context.user_data.get("mood_entries", []))
    keyboard = [
        [InlineKeyboardButton("➕ Новая запись", callback_data="mood|new")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="menu|home")],
    ]

    try:
        await query.message.edit_text(
            summary,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    except Exception:
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=summary,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )


async def handle_menu_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action = query.data.split("|")[1]

    if action == "home":
        await send_main_menu(update, context, text="Вы в главном меню.")
        return ConversationHandler.END
    elif action == "tip":
        await send_daily_tip(update, context)
    elif action == "breath":
        await send_breathing_practice(update, context)
    elif action == "resources":
        await send_resources(update, context)
    elif action == "about":
        await send_about(update, context)
    elif action == "mood":
        await show_mood_menu(update, context)
    else:
        await query.answer("Функция в разработке", show_alert=True)


async def mood_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    summary = format_mood_history(context.user_data.get("mood_entries", []))
    keyboard = [
        [InlineKeyboardButton("➕ Новая запись", callback_data="mood|new")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="menu|home")],
    ]
    await update.message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_main_menu(
        update,
        context,
        text=(
            "Вот чем я могу помочь: тесты, советы, дыхательные практики и дневник настроения. "
            "Выберите раздел ниже."
        ),
    )


# Запуск бота
def main():
    # ✅ Берём токен из переменной окружения, если есть
    token = os.getenv("BOT_TOKEN")

    # ✅ Если переменной нет, используем токен прямо из кода
    if not token:
        token = "8407448825:AAH3-75Wnra_LetBwx8E9i10VoZMqNWjbvc"

    app = ApplicationBuilder().token(token).build()

    test_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_test_flow, pattern="^menu\\|test$")],
        states={
            TEST_CHOOSE_TOPIC: [
                CallbackQueryHandler(choose_topic, pattern="^topic\\|"),
                CallbackQueryHandler(handle_menu_navigation, pattern="^menu\\|home$"),
            ],
            TEST_ASK_QUESTION: [
                CallbackQueryHandler(handle_answer, pattern="^answer\\|"),
                CallbackQueryHandler(handle_menu_navigation, pattern="^menu\\|home$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(handle_menu_navigation, pattern="^menu\\|home$"),
        ],
        per_chat=True,
        per_user=True,
    )

    mood_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_mood_entry, pattern="^mood\\|new$")],
        states={
            MOOD_WAIT_RATING: [
                CallbackQueryHandler(handle_mood_rating, pattern="^mood\\|rate\\|"),
                CallbackQueryHandler(cancel_mood_entry, pattern="^mood\\|cancel$"),
                CallbackQueryHandler(handle_menu_navigation, pattern="^menu\\|home$"),
            ],
            MOOD_WAIT_NOTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mood_note),
                CallbackQueryHandler(handle_mood_skip, pattern="^mood\\|skip$"),
                CallbackQueryHandler(cancel_mood_entry, pattern="^mood\\|cancel$"),
                CallbackQueryHandler(handle_menu_navigation, pattern="^menu\\|home$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_mood_entry, pattern="^mood\\|cancel$"),
            CommandHandler("cancel", cancel_mood_entry),
            CallbackQueryHandler(handle_menu_navigation, pattern="^menu\\|home$"),
        ],
        per_chat=True,
        per_user=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("history", mood_history_command))
    app.add_handler(test_conversation)
    app.add_handler(mood_conversation)
    app.add_handler(CallbackQueryHandler(show_mood_history, pattern="^mood\\|history$"))
    app.add_handler(CallbackQueryHandler(handle_menu_navigation, pattern="^menu\\|"))

    print("✅ Бот запущен. Ожидание команд...")
    app.run_polling()


if __name__ == "__main__":
    main()

