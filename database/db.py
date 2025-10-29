# database/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base

# Создаём движок для SQLite
engine = create_engine("sqlite:///triggerbot.db")
# Создаём таблицы на основе моделей
Base.metadata.create_all(engine)
# Создаём фабрику сессий
Session = sessionmaker(bind=engine, expire_on_commit=True)