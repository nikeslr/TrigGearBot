# bot.py
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from config import TOKEN
from locallog.logger import BotLogger
from triggers.manager import TriggerManager
from database.db import Session
from database.models import Chat, Category
from telegram import ChatMember



# Что делает: Проверяет статус пользователя в чате. Возвращает True, если пользователь — администратор или создатель, иначе False.
# Обработка ошибок: Если Telegram API вернёт ошибку (например, бот не имеет доступа), функция вернёт False.
async def is_admin(bot, chat_id, user_id):
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except Exception as e:
        print(f"Ошибка проверки прав администратора: {e}")
        return False




async def add_category(update: Update, context):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    if not await is_admin(context.bot, chat_id, user_id):
        await update.message.reply_text("Только администраторы могут добавлять категории.")
        return

    args = context.args
    if len(args) < 3:
        await update.message.reply_text("Использование: /add_category <название> <ключевые_слова> <ответ>")
        return

    name, keywords, *response = args
    response = " ".join(response)

    with Session() as session:
        category = Category(chat_id=chat_id, name=name, keywords=keywords, response=response)
        session.add(category)
        session.commit()

        await BotLogger.category_added(
            category_name=name,
            admin_id=user_id,
            chat_id=chat_id
        )

    await update.message.reply_text(f"Категория '{name}' добавлена!")

async def remove_category(update: Update, context):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    if not await is_admin(context.bot, chat_id, user_id):
        await update.message.reply_text("Только администраторы могут удалять категории.")
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Использование: /remove_category <название>")
        return

    name = args[0]

    with Session() as session:
        category = session.query(Category).filter_by(chat_id=chat_id, name=name).first()
        if not category:
            await update.message.reply_text(f"Категория '{name}' не найдена.")
            return
        session.delete(category)
        session.commit()
        await BotLogger.category_removed(
            category_name=name,
            admin_id=user_id,
            chat_id=chat_id
        )

    await update.message.reply_text(f"Категория '{name}' удалена!")

async def list_categories(update: Update, context):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    if not await is_admin(context.bot, chat_id, user_id):
        await update.message.reply_text("Только администраторы могут просматривать категории.")
        return

    with Session() as session:
        categories = session.query(Category).filter_by(chat_id=chat_id).all()
        if not categories:
            await update.message.reply_text("В этом чате нет категорий.")
            return
        response = "Список категорий:\n" + "\n".join(
            f"- {cat.name} (ключевые слова: {cat.keywords}, ответ: {cat.response})"
            for cat in categories
        )
        await update.message.reply_text(response)

async def start(update: Update, context):
    await update.message.reply_text(
        "Привет! Я триггер-бот. Используй /add_category, /remove_category или /list_categories для управления.")

async def handle_message(update: Update, context):
    manager = TriggerManager()
    await manager.process_message(update.message, context.bot)

async def setup_test_data():
    # Создаём сессию для добавления тестовых данных
    session = Session()
    chat = Chat(id=-4734439984)  # Замените на реальный ID вашего тестового чата
    session.add(chat)
    session.commit()

    categories = [
        Category(chat_id=chat.id, name="Религия", keywords="бог, церковь", response="У нас есть отдельный чат для обсуждения религии"),
        Category(chat_id=chat.id, name="Игры", keywords="игра, гейминг", response="У нас есть отдельный чат для обсуждения игр"),
        Category(chat_id=chat.id, name="Политика", keywords="выборы, президент", response="У нас есть отдельный чат для обсуждения политики"),
    ]
    session.add_all(categories)
    session.commit()
    session.close()  # Закрываем сессию после использования

def main():
    # Создаём приложение
    application = Application.builder().token(TOKEN).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))

    application.add_handler(CommandHandler("add_category", add_category))
    application.add_handler(CommandHandler("remove_category", remove_category))
    application.add_handler(CommandHandler("list_categories", list_categories))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Настраиваем тестовые данные (выполните один раз)
    # asyncio.run(setup_test_data())

    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
# asyncio.run(main())