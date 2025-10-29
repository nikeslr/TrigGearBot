# triggers/manager.py
import asyncio

from locallog.logger import BotLogger
from .conditions import KeywordMatch, UserTriggerCount
from .actions import SendMessage
from database.db import Session
from database.models import Category, Log, TriggerEvent
from datetime import datetime

class TriggerManager:
    async def process_message(self, message, bot):
        def db_operation():
            with Session() as session:
                chat_id = message.chat.id
                categories = session.query(Category).filter_by(chat_id=chat_id).all()
                for category in categories:
                    condition_keyword = KeywordMatch(category.keywords)
                    if condition_keyword.check(message, {}):
                        # Записываем событие триггера
                        trigger_event = TriggerEvent(
                            chat_id=chat_id,
                            user_id=message.from_user.id,
                            category_id=category.id,
                            timestamp=datetime.utcnow()
                        )
                        session.add(trigger_event)
                        session.commit()
                        # print('commit db operation')
                        return Session().merge(category)
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
                await BotLogger.trigger_fired(
                    category_name=category.name,
                    chat_id=message.chat.id,
                    user_id=message.from_user.id
                )

