# triggers/conditions.py
from datetime import datetime, timedelta
from database.db import Session

from database.models import TriggerEvent


class Condition:
    def check(self, message, context):
        raise NotImplementedError

class KeywordMatch(Condition):
    def __init__(self, keywords):
        self.keywords = [kw.strip().lower() for kw in keywords.split(",")]

    def check(self, message, context):
        text = message.text.lower()
        return any(keyword in text for keyword in self.keywords)



class UserTriggerCount(Condition):
    def __init__(self, count, minutes):
        self.count = count
        self.minutes = minutes

    def check(self, message, context):
        user_id = message.from_user.id
        chat_id = message.chat.id
        category_id = context.get("category_id")  # Получаем ID категории из контекста
        if not category_id:
            return False

        with Session() as session:
            # Подсчитываем триггеры для пользователя в заданном временном окне
            now = datetime.utcnow()

            recent_triggers = session.query(TriggerEvent).filter(
                TriggerEvent.user_id == user_id,
                TriggerEvent.chat_id == chat_id,
                TriggerEvent.category_id == category_id,
                TriggerEvent.timestamp >= now - timedelta(minutes=self.minutes)
            ).count()
            return recent_triggers >= self.count