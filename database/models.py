# database/models.py
from sqlalchemy import Column, Integer, String, ForeignKey, column, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    action_type = Column(String)
    details = Column(String)
    chat_id = Column(Integer, ForeignKey("chats.id"))
    user_id = Column(Integer, nullable=True)


class ChatGroup(Base):
    __tablename__ = "chat_groups"
    id = Column(Integer, primary_key=True)
    name = Column(String)  # Название группы (опционально)

class Chat(Base):
    __tablename__ = "chats"
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("chat_groups.id"), nullable=True)


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True,unique=True,autoincrement=True)
    chat_id = Column(Integer, ForeignKey("chats.id"))
    name = Column(String)
    keywords = Column(String)
    response = Column(String)


class TriggerEvent(Base):
    __tablename__ = "trigger_events"
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id"))
    user_id = Column(Integer)  # ID пользователя, вызвавшего триггер
    category_id = Column(Integer, ForeignKey("categories.id"))  # ID категории
    timestamp = Column(DateTime, default=datetime.utcnow)  # Время срабатывания