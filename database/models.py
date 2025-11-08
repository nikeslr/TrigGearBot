# database/models.py
from sqlalchemy import JSON, Column, Integer, String, ForeignKey, DateTime, BigInteger, CheckConstraint
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime)
    level = Column(String)
    event_type = Column(String)
    trace_id = Column(String)
    message = Column(String)
    payload = Column(JSON)
    chat_id = Column(BigInteger, nullable=True)
    user_id = Column(BigInteger, nullable=True)


class ChatGroup(Base):
    __tablename__ = "chat_groups"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)  # Название группы
    owner_id = Column(BigInteger, nullable=False)  # Владелец группы (изоляция)


class Chat(Base):
    __tablename__ = "chats"
    id = Column(BigInteger, primary_key=True)
    group_id = Column(Integer, ForeignKey("chat_groups.id"), nullable=True)


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)  # Может повторяться (локально/группово)
    keywords = Column(String)  # Через запятую
    response = Column(String)
    chat_id = Column(BigInteger, ForeignKey("chats.id"), nullable=True)  # Локальная
    group_id = Column(Integer, ForeignKey("chat_groups.id"), nullable=True)  # Групповая
    owner_id = Column(BigInteger)  # Кто создал (аудит, опционально)

    __table_args__ = (
        CheckConstraint(
            "(chat_id IS NULL AND group_id IS NOT NULL) OR (chat_id IS NOT NULL AND group_id IS NULL)",
            name="one_level_only"
        ),
    )


class TriggerEvent(Base):
    __tablename__ = "trigger_events"
    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, ForeignKey("chats.id"))
    user_id = Column(BigInteger)  # ID пользователя, вызвавшего триггер
    category_id = Column(Integer, ForeignKey("categories.id"))  # ID категории
    timestamp = Column(DateTime, default=datetime.utcnow)  # Время срабатывания