# locallog/adapters.py

import logging
from locallog.logger import logger
from locallog.context import set_trace_id, set_log

from typing import Optional
from telegram import Update, Message, Chat, User



def extract_context_data(update: Update) -> dict:
    """
    Универсально извлекает данные о пользователе, чате и тексте из любого типа update.
    Поддерживает message, edited_message, channel_post, callback_query, inline_query, chat_member и др.
    """

    msg: Optional[Message] = None
    chat: Optional[Chat] = None
    user: Optional[User] = None
    text: Optional[str] = None
    update_type: str = "unknown"

    # --- 1. Определяем тип update и извлекаем базовые объекты ---
    if update.message:
        msg = update.message
        update_type = "message"
    elif update.edited_message:
        msg = update.edited_message
        update_type = "edited_message"
    elif update.channel_post:
        msg = update.channel_post
        update_type = "channel_post"
    elif update.edited_channel_post:
        msg = update.edited_channel_post
        update_type = "edited_channel_post"
    elif update.callback_query:
        msg = update.callback_query.message
        user = update.callback_query.from_user
        text = update.callback_query.data
        update_type = "callback_query"
    elif update.inline_query:
        user = update.inline_query.from_user
        text = update.inline_query.query
        update_type = "inline_query"
    elif update.my_chat_member:
        chat = update.my_chat_member.chat
        user = update.my_chat_member.from_user
        update_type = "my_chat_member"
    elif update.chat_member:
        chat = update.chat_member.chat
        user = update.chat_member.from_user
        update_type = "chat_member"
    elif hasattr(update, "message_reaction") and update.message_reaction:
        msg = update.message_reaction.message
        user = update.message_reaction.user
        update_type = "message_reaction"

    # --- 2. Извлекаем chat и user (если их ещё нет) ---
    if msg:
        chat = msg.chat
        user = user or msg.from_user
        text = text or getattr(msg, "text", None)

    # --- 3. Извлекаем финальные данные ---
    chat_id = getattr(chat, "id", None)
    chatname = getattr(chat, "title", None) or getattr(chat, "username", None)
    user_id = getattr(user, "id", None)
    username = getattr(user, "username", None)

    # --- 4. Возвращаем универсальный контекст ---
    return {
        "text": text[:500] if text else None,
        "username": username,
        "chatname": chatname,
        "chat_id": chat_id,
        "user_id": user_id,
        "update_type": update_type,
    }



def get_log_for_update(update, event_type: str):
    # Генерируем trace_id один раз на update
    trace_id = set_trace_id()

    # Собираем полезную нагрузку из update
    ctx = extract_context_data(update)

    extra = {
        "event_type": event_type,
        "trace_id": trace_id,
        "chat_id": ctx["chat_id"],
        "user_id": ctx["user_id"],
        "payload": {
            "text": ctx["text"],
            "username": "@"+ctx["username"],
            "chatname": ctx["chatname"],
            "update_type": ctx["update_type"],
        },

    }

    log = BotLoggerAdapter(logger, extra)
    set_log(log)

    return log

class BotLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        call_extra = kwargs.get("extra", {})
        combined_extra = {**self.extra, **call_extra}

        # Сливаем payload, если есть в адаптере и в вызове
        adapter_payload = self.extra.get("payload", {})
        call_payload = call_extra.get("payload", {})
        combined_extra["payload"] = {**adapter_payload, **call_payload}

        kwargs["extra"] = combined_extra
        return msg, kwargs