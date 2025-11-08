# triggers/manager.py
import asyncio

from locallog.context import get_log
from .conditions import KeywordMatch, UserTriggerCount
from .actions import SendMessage
from database.db import Session
from database.models import Category, TriggerEvent, Chat
from datetime import datetime

class TriggerManager:
    async def process_message(self, message, bot):
        log = get_log()
        def db_operation():
            with Session() as session:
                chat_id = message.chat.id
                chat = session.get(Chat, chat_id)
                if not chat:
                    return None

                # Локальные категории (chat_id)
                local_cats = {cat.name: cat for cat in session.query(Category).filter_by(chat_id=chat_id).all()}

                # Групповые категории (если в группе)
                group_cats = {}
                if chat.group_id:
                    group_cats = {cat.name: cat for cat in session.query(Category).filter_by(group_id=chat.group_id).all()}

                # Мерж: локальные переопределяют групповые
                merged_cats = {**group_cats, **local_cats}

                for cat in merged_cats.values():
                    condition_keyword = KeywordMatch(cat.keywords)
                    if condition_keyword.check(message, {}):
                        # Записываем событие триггера
                        trigger_event = TriggerEvent(
                            chat_id=chat_id,
                            user_id=message.from_user.id,
                            category_id=cat.id,
                            timestamp=datetime.utcnow()
                        )
                        session.add(trigger_event)
                        session.commit()
                        log.debug(f"Обнаружено ключевое слово категории {cat.name}", extra={"payload": {"category": cat.name}})
                        return cat
                return None

        category = await asyncio.to_thread(db_operation)

        if category:
            # Проверяем условие подсчета триггеров
            condition_count = UserTriggerCount(count=3, minutes=10)  # Например, 3 триггера за 10 минут
            context = {"category_id": category.id}
            if condition_count.check(message, context):
                action = SendMessage(category.response)
                await action.execute(message, {"bot": bot})

                # Логируем через отдельный модуль
                log.debug(f"Сработал счетчик триггеров категории {category.name}",extra={"payload": {"category": category.name}})