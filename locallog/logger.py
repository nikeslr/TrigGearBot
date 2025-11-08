# locallog/logger.py

import logging
from logging.handlers import RotatingFileHandler
import json
from datetime import datetime
from locallog.context import *
from database.db import Session
from database.models import Log


class JSONFormatter(logging.Formatter):
    """Форматирует логи в JSON."""
    def format(self, record):
        base = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "trace_id": getattr(record, "trace_id", get_trace_id()),
            "event_type": getattr(record, "event_type", None),
            "message": record.getMessage(),
            "chat_id": getattr(record, "chat_id", None),
            "user_id": getattr(record, "user_id", None),
            "payload": getattr(record, "payload", None),
            "logger": record.name,
        }
        # payload = getattr(record, "payload", None)
        # if payload:
        #     base["payload"] = payload
        if record.exc_info:
            base["exception"] = self.formatException(record.exc_info)
        return json.dumps(base, ensure_ascii=False)



# ------------------ Внутренний логгер для ошибок DBHandler ------------------
def setup_internal_logger():
    """Создаёт отдельный логгер для ошибок в DBHandler."""
    fallback_logger = logging.getLogger("TrigGearBot.DBHandlerError")

    if not fallback_logger.handlers:
        fh = logging.FileHandler("dbhandler_errors.log", encoding="utf-8")
        fh.setFormatter(JSONFormatter())
        fallback_logger.addHandler(fh)
        fallback_logger.setLevel(logging.ERROR)
        fallback_logger.propagate = False  # не отправлять вверх по иерархии

    return fallback_logger



class DBHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.fallback_logger = setup_internal_logger()

    def emit(self, record):
        try:
            with Session() as session:
                entry = Log(
                    timestamp=datetime.utcnow(),
                    level=record.levelname,
                    event_type=getattr(record, "event_type", None),
                    message=record.getMessage(),
                    trace_id=getattr(record, "trace_id", get_trace_id()),
                    chat_id=getattr(record, "chat_id", None),
                    user_id=getattr(record, "user_id", None),
                    payload=getattr(record, "payload", None),
                )
                session.add(entry)
                session.commit()

        except Exception as e:
            # fallback — чтобы не вызывать рекурсию логгера
            self.fallback_logger.error(
                f"Ошибка записи лога в БД: {e}",
                exc_info=True,
                extra={
                    "chat_id": getattr(record, "chat_id", None),
                    "user_id": getattr(record, "user_id", None),
                    "event_type": getattr(record, "event_type", None),
                    "trace_id": getattr(record, "trace_id", get_trace_id()),
                    "payload": {
                        "failed_message": record.getMessage(),
                        "trace_id": getattr(record, "trace_id", None),
                        "event_type": getattr(record, "event_type", None),
                    },
                },
            )


def setup_logger(
    name="TrigGearBot",
    to_console=True,
    to_db=False,
    to_file=False,
    log_file="bot.log",
    max_bytes=5 * 1024 * 1024,
    backup_count=3,
):
    """
      Универсальная настройка логгера.
      :param name: имя логгера
      :param to_console: вывод в stdout
      :param to_db: запись в базу
      :param to_file: запись в файл (JSON)
      :param log_file: путь к файлу логов
      """

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()  # очистим, чтобы не было дублирования

    formatter = JSONFormatter()

    if to_console:
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        logger.addHandler(sh)

    if to_db:
        dbh = DBHandler()
        logger.addHandler(dbh)

    # --- Файл ---
    if to_file:
        fh = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger

# Глобальный экземпляр
logger = setup_logger(to_console=True, to_db=True, to_file=True)