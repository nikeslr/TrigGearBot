# locallog/logger.py
import asyncio
from datetime import datetime
from database.db import Session
from database.models import Log

class BotLogger:
    @staticmethod
    async def log(action_type: str, details: str, chat_id: int, user_id: int = None):
        """
        Асинхронно логирует действие в базу данных.
        """
        def _write_to_db():
            with Session() as session:
                log_entry = Log(
                    timestamp=datetime.utcnow(),
                    action_type=action_type,
                    details=details,
                    chat_id=chat_id,
                    user_id=user_id
                )
                session.add(log_entry)
                session.commit()

        # Выполняем в отдельном потоке, чтобы не блокировать
        await asyncio.to_thread(_write_to_db)

    @staticmethod
    async def trigger_fired(category_name: str, chat_id: int, user_id: int):
        await BotLogger.log(
            action_type="trigger_fired",
            details=f"Категория '{category_name}' сработала в чате {chat_id}",
            chat_id=chat_id,
            user_id=user_id
        )

    @staticmethod
    async def category_added(category_name: str, admin_id: int, chat_id: int):
        await BotLogger.log(
            action_type="add_category",
            details=f"Администратор {admin_id} добавил категорию '{category_name}' в чате {chat_id}",
            chat_id=chat_id,
            user_id=admin_id
        )

    @staticmethod
    async def category_removed(category_name: str, admin_id: int, chat_id: int):
        await BotLogger.log(
            action_type="remove_category",
            details=f"Администратор {admin_id} удалил категорию '{category_name}' в чате {chat_id}",
            chat_id=chat_id,
            user_id=admin_id
        )

    @staticmethod
    async def error(error_msg: str, chat_id: int = None):
        await BotLogger.log("error", error_msg, chat_id)

    @staticmethod
    async def debug(debug_msg: str):
        print(f"[DEBUG] {debug_msg}")  # или в файл