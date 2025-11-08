# bot.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ChatMemberHandler, MessageHandler, filters, ContextTypes
from config import TOKEN
from locallog.adapters import get_log_for_update
from locallog.context import get_log
from language.lang import t
from triggers.manager import TriggerManager
from database.db import Session
from database.models import Chat, ChatGroup, Category
import asyncio



log = get_log_for_update  # Для простоты

async def handle_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log = get_log_for_update(update, "my_chat_member")
    new_status = update.my_chat_member.new_chat_member.status
    chat_id = update.my_chat_member.chat.id

    if new_status == "administrator":
        # Бот добавлен в чат
        await ensure_chat_exists(chat_id)
        log.info("Бот добавлен в чат", extra={"payload": {"chat_id": chat_id}})
    elif new_status in ["left", "kicked"]:
        # Бот удалён
        with Session() as session:
            chat = session.get(Chat,chat_id)
            if chat:
                session.delete(chat)
                session.commit()
        log.info("Бот удалён из чата", extra={"payload": {"chat_id": chat_id}})



# === ПРАВА ===
async def get_user_role(bot, chat_id: int, user_id: int):
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status
    except Exception as e:
        log_error = get_log_for_update(None, "get_user_role")
        log_error.exception(f"Ошибка get_chat_member: {e}")
        return None

async def ensure_chat_exists(chat_id: int):
    with Session() as session:
        chat = session.get(Chat,chat_id)
        if not chat:
            chat = Chat(id=chat_id)
            session.add(chat)
            session.commit()
        return chat

# === /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log = get_log_for_update(update, "start")
    log.info("Пользователь открыл бота", extra={"payload": {"user_id": update.effective_user.id}})
    await update.message.reply_text(t(update.effective_user.id, "welcome"))

# === /my_chats ===
async def my_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log = get_log_for_update(update, "my_chats")
    user_id = update.effective_user.id
    log.info("Запрос списка чатов", extra={"payload": {"user_id": user_id}})

    text, markup = await build_my_chats_reply(user_id, context.bot)
    await update.message.reply_text(text, reply_markup=markup)
    log.info("Показан список чатов")

async def build_my_chats_reply(user_id: int, bot):
    log = get_log()  # или контекст
    max_len = 28
    len_name = 2*round(max_len/3)
    len_group = round(max_len/3)
    with Session() as session:
        chats = session.query(Chat).all()
        keyboard = []
        for chat in chats:
            role = await get_user_role(bot, chat.id, user_id)
            if role in [ChatMember.OWNER, ChatMember.ADMINISTRATOR]:
                try:
                    tg_chat = await bot.get_chat(chat.id)
                    chat_title = tg_chat.title or f"Чат {chat.id}"
                except:
                    chat_title = f"Чат {chat.id} (недоступен)"


                display_title = (chat_title[:len_name] + "…") if len(chat_title) > len_name else chat_title

                if chat.group_id:
                    group = session.get(ChatGroup, chat.group_id)
                    if group:
                        display_group = (group.name[:len_group] + "…") if len(group.name) > len_group else group.name
                        display_title += f" ({display_group})"
                role_icon = "👑" if role == ChatMember.OWNER else "🛠️"
                role_text = "OWN" if role == ChatMember.OWNER else "ADM"
                display_title += f" {role_icon}{role_text}"
                button_text = f"⠀{display_title}⠀"  # невидимые пробелы для ширины
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f"chat_settings|{chat.id}")])


        if keyboard:
            keyboard.append([InlineKeyboardButton(t(user_id, "my_groups_button"), callback_data="my_groups_from_menu")])

        if not keyboard:
            text = t(user_id, "no_chats")
            markup = None
        else:
            text = t(user_id, "your_chats")
            markup = InlineKeyboardMarkup(keyboard)


        return text, markup


def get_user_groups(user_id: int):
    with Session() as session:
        return session.query(ChatGroup).filter_by(owner_id=user_id).all()

# === /my_groups ===
async def my_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log = get_log_for_update(update, "my_groups")
    user_id = update.effective_user.id
    log.info("Запрос списка групп", extra={"payload": {"user_id": user_id}})

    groups = get_user_groups(user_id)

    if not groups:
        await update.message.reply_text(t(user_id, "no_groups"))
        log.info("Группы не найдены", extra={"payload": {"user_id": user_id}})
        return

    keyboard = [
        [InlineKeyboardButton(group.name, callback_data=f"view_group|{group.id}")]
        for group in groups
    ]

    keyboard.append([InlineKeyboardButton(t(user_id, "back"), callback_data="back_to_my_chats")])

    markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(t(user_id, "your_groups"), reply_markup=markup)
    log.info("Показан список групп", extra={"payload": {"group_count": len(groups)}})


# === my_groups_from_menu ===
async def my_groups_from_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    log = get_log_for_update(update, "my_groups_from_menu")
    user_id = query.from_user.id
    log.info("Переход к списку групп из меню")
    # Вызываем ту же логику, что и команда /my_groups
    class DummyMessage:
        """Имитация объекта message, чтобы переиспользовать my_groups"""
        def __init__(self, from_user,chat):
            self.from_user = from_user
            self.chat = chat
        async def reply_text(self, text, reply_markup=None):
            await query.edit_message_text(text, reply_markup=reply_markup)

    chat = getattr(query.message, "chat", None)
    dummy_update = Update(update.update_id, message=DummyMessage(query.from_user,chat))
    await my_groups(dummy_update, context)


# === back_to_my_groups ===
async def back_to_my_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    log = get_log_for_update(update, "back_to_my_groups")
    user_id = query.from_user.id

    with Session() as session:
        groups = session.query(ChatGroup).filter_by(owner_id=user_id).all()

    if not groups:
        await query.edit_message_text(t(user_id, "no_groups"))
        return

    keyboard = [
        [InlineKeyboardButton(group.name, callback_data=f"view_group|{group.id}")]
        for group in groups
    ]
    markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(t(user_id, "your_groups"), reply_markup=markup)
    log.info("Возврат к списку групп", extra={"payload": {"user_id": user_id}})



# === view_group_callback ===
async def view_group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    log = get_log_for_update(update, "view_group")
    user_id = query.from_user.id
    group_id = int(query.data.split("|")[1])

    with Session() as session:
        group = session.get(ChatGroup, group_id)
        if not group:
            await query.edit_message_text(t(user_id, "group_not_found"))
            return

        if group.owner_id != user_id:
            await query.edit_message_text(t(user_id, "group_no_access"))
            log.warning("Попытка просмотра чужой группы", extra={"payload": {"user_id": user_id, "group_id": group_id}})
            return

        chats = session.query(Chat).filter_by(group_id=group_id).all()
        text = t(user_id, "group_chats_list", name=group.name)
        if not chats:
            text += "\n" + t(user_id, "group_chats_empty")
        else:
            for chat in chats:
                text += f"\n• {chat.id}"

        keyboard = [[InlineKeyboardButton(t(user_id, "back"), callback_data="back_to_my_groups")]]
        markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=markup)
        log.info("Просмотр содержимого группы", extra={"payload": {"group_id": group_id, "chat_count": len(chats)}})



# === chat_settings ===
async def chat_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    log = get_log_for_update(update, "chat_settings")
    user_id = query.from_user.id
    chat_id = int(query.data.split("|")[1])
    bot = context.bot


    role = await get_user_role(bot, chat_id, user_id)
    if role not in [ChatMember.OWNER, ChatMember.ADMINISTRATOR]:
        await query.edit_message_text(t(user_id, "no_access"))
        log.warning("Попытка доступа без прав", extra={"payload": {"chat_id": chat_id, "user_id": user_id}})
        return

    chat_title = context.user_data.get("chat_title")
    if chat_title is None:
        try:
            tg_chat = await bot.get_chat(chat_id)
            chat_title = tg_chat.title or f"Чат {chat_id}"
        except:
            chat_title = f"Чат {chat_id} (недоступен)"
    else:
        await back_to_my_chats(update,context)
        return

    await ensure_chat_exists(chat_id)
    keyboard = []

    role_text = "OWNER" if role == ChatMember.OWNER else "ADMIN"

    if role == ChatMember.OWNER:
        keyboard.append([InlineKeyboardButton(t(user_id, "create_group"), callback_data=f"create_group|{chat_id}")])
        keyboard.append([InlineKeyboardButton(t(user_id, "assign_group"), callback_data=f"1|{chat_id}")])
        keyboard.append([InlineKeyboardButton(t(user_id, "group_categories"), callback_data=f"group_cats|{chat_id}")])

    keyboard.append([InlineKeyboardButton(t(user_id, "local_categories"), callback_data=f"local_cats|{chat_id}")])
    keyboard.append([InlineKeyboardButton(t(user_id, "back"), callback_data="back_to_my_chats")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        t(user_id, "chat_settings_title", chat_id=chat_title, role=role_text),
        reply_markup=reply_markup
    )
    log.info("Открыты настройки чата", extra={"payload": {"chat_id": chat_id,"chat_title": chat_title,"role": role_text}})

# === assign_group_callback ===
async def assign_group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    log = get_log_for_update(update, "assign_group")
    user_id = query.from_user.id
    chat_id = int(query.data.split("|")[1])

    if await get_user_role(context.bot, chat_id, user_id) != ChatMember.OWNER:
        await query.edit_message_text(t(user_id, "only_owner"))
        log.warning("Попытка привязки группы без прав", extra={"payload": {"user_id": user_id, "chat_id": chat_id}})
        return

    with Session() as session:
        chat =  session.query(chat_id)
        groups = session.query(ChatGroup).filter_by(owner_id=user_id).all()
        if not groups:
            await query.edit_message_text(t(user_id, "no_groups_for_assign"))
            return
        keyboard = []
        for group in groups:
            marker = "✅ " if chat.group_id == group.id else ""
            keyboard.append([InlineKeyboardButton(f"{marker}{group.name}",
                                                  callback_data=f"assign_group_confirm|{chat_id}|{group.id}")])

        keyboard.append([InlineKeyboardButton(t(user_id, "back"), callback_data=f"chat_settings|{chat_id}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(t(user_id, "choose_group_to_assign"), reply_markup=reply_markup)
        log.info("Выбор группы для привязки", extra={"payload": {"chat_id": chat_id}})


# === assign_group_confirm_callback ===
async def assign_group_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    log = get_log_for_update(update, "assign_group_confirm")
    _, chat_id, group_id = query.data.split("|")
    chat_id = int(chat_id)
    group_id = int(group_id)
    user_id = query.from_user.id
    group_name = ""
    if await get_user_role(context.bot, chat_id, user_id) != ChatMember.OWNER:
        await query.edit_message_text(t(user_id, "only_owner"))
        return

    with Session() as session:
        chat = session.get(Chat, chat_id)
        group = session.get(ChatGroup, group_id)
        if not chat or not group:
            await query.edit_message_text(t(user_id, "assign_error_not_found"))
            return

        chat.group_id = group_id
        group_name = group.name
        session.commit()

    keyboard=[]
    keyboard.append([InlineKeyboardButton(t(user_id, "back"), callback_data=f"chat_settings|{chat_id}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(t(user_id, "chat_assigned_to_group", name=group_name), reply_markup=reply_markup)
    log.info("Чат привязан к группе", extra={"payload": {"chat_id": chat_id, "group_id": group_id}})



# === create_group ===
async def create_group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    log = get_log_for_update(update, "create_group")
    user_id = query.from_user.id
    chat_id = int(query.data.split("|")[1])

    if await get_user_role(context.bot, chat_id, user_id) != ChatMember.OWNER:
        await query.edit_message_text(t(user_id, "only_owner"))
        log.warning("Попытка создать группу без прав", extra={"payload": {"user_id": user_id, "chat_id": chat_id}})
        return

    await query.edit_message_text(t(user_id, "enter_group_name"))
    context.user_data["awaiting_group_name"] = chat_id
    log.info("Ожидание названия группы", extra={"payload": {"chat_id": chat_id}})

# === handle_text (ввод названия) ===
async def handle_text_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("awaiting_category")
    if state:
        await handle_category_input(update, context, state)
        return

    if "awaiting_group_name" not in context.user_data:
        return

    chat_id = context.user_data.pop("awaiting_group_name")
    name = update.message.text.strip()
    user_id = update.message.from_user.id
    log = get_log_for_update(update, "handle_group_name")

    if not name:
        await update.message.reply_text(t(user_id, "empty_group_name"))
        return

    if await get_user_role(context.bot, chat_id, user_id) != ChatMember.OWNER:
        await update.message.reply_text(t(user_id, "no_access"))
        log.warning("Попытка создать группу без прав", extra={"payload": {"user_id": user_id}})
        return

    keyboard = []
    keyboard.append([InlineKeyboardButton(t(user_id, "back"), callback_data=f"chat_settings|{chat_id}")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        with Session() as session:
            group = ChatGroup(name=name, owner_id=user_id)
            session.add(group)
            session.commit()
            chat = session.get(Chat,chat_id)
            chat.group_id = group.id
            session.commit()
            log.info("Группа создана", extra={"payload": {"name": name, "group_id": group.id, "chat_id": chat_id}})
            await update.message.reply_text(t(user_id, "group_created", name=name),reply_markup=reply_markup)

    except Exception as e:
        await update.message.reply_text(t(user_id, "error_creating_group"),reply_markup=reply_markup)
        log.exception("Ошибка создания группы", extra={"payload": {"error": str(e)}})


# === back_to_my_chats ===
async def back_to_my_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log = get_log_for_update(update, "back_to_my_chats")
    user_id = update.effective_user.id

    try:
        from_chat_title = context.user_data.pop("chat_title")
    except:
        from_chat_title = None

    log.info("Запрос списка чатов", extra={"payload": {"user_id": user_id,"return_from": from_chat_title}})

    query = update.callback_query
    await query.answer()
    text, markup = await build_my_chats_reply(query.from_user.id, context.bot)

    if not markup:
        await query.edit_message_text(t(user_id, "no_chats"))
        return
    else:
        await query.edit_message_text(text, reply_markup=markup)
    log.info("Показан список чатов")


# === Категории: общая функция ===
async def build_categories_reply(chat_id: int, user_id: int, bot, is_group: bool = False):
    log = get_log()

    with Session() as session:
        categories = []
        if is_group:
            chat = session.get(Chat, chat_id)
            if chat and chat.group_id:
                categories = session.query(Category).filter(Category.group_id == chat.group_id).all()
            title_key = "group_categories_title"
            add_key = "add_group_category"
        else:
            categories = session.query(Category).filter(Category.chat_id == chat_id).all()
            title_key = "local_categories_title"
            add_key = "add_local_category"

        keyboard = []
        for cat in categories:
            keywords = cat.keywords or ""
            response = cat.response or ""
            preview = f"{cat.name} → {keywords} → {response}"
            # owner_id для аудита (опционально в preview)
            if cat.owner_id:
                preview += f" (создатель: {cat.owner_id})"

            keyboard.append([InlineKeyboardButton(preview, callback_data="noop")])

            row = []
            row.append(InlineKeyboardButton(t(user_id, "edit"), callback_data=f"{'group' if is_group else 'local'}_edit_cat|{cat.id}|{chat_id}"))
            row.append(InlineKeyboardButton(t(user_id, "delete"), callback_data=f"{'group' if is_group else 'local'}_delete_cat|{cat.id}|{chat_id}"))
            keyboard.append(row)

        # Групповые в локальных
        chat = session.get(Chat, chat_id)
        if not is_group and chat.group_id:
            group_cats = session.query(Category).filter(Category.group_id == chat.group_id).all()
            if group_cats:
                keyboard.append(
                    [InlineKeyboardButton(t(user_id, "group_categories_from_group"), callback_data="noop")])
                for cat in group_cats:
                    keywords = cat.keywords or ""
                    response = cat.response or ""
                    preview = f"{cat.name} → {keywords} → {response} (групповая)"
                    local_override = any(c.name == cat.name for c in categories)
                    if local_override:
                        preview += " [переопределена]"
                    keyboard.append([InlineKeyboardButton(preview, callback_data="noop")])

        keyboard.append([InlineKeyboardButton(t(user_id, add_key),
                                                  callback_data=f"{'group' if is_group else 'local'}_add_cat|{chat_id}")])
        keyboard.append([InlineKeyboardButton(t(user_id, "back"), callback_data=f"chat_settings|{chat_id}")])

        text = t(user_id, title_key)
        markup = InlineKeyboardMarkup(keyboard)
        return text, markup

# === Локальные категории ===
async def local_cats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    log = get_log_for_update(update, "local_cats")
    user_id = query.from_user.id
    chat_id = int(query.data.split("|")[1])

    role = await get_user_role(context.bot, chat_id, user_id)
    if role not in [ChatMember.OWNER, ChatMember.ADMINISTRATOR]:
        await query.edit_message_text(t(user_id, "no_access"))
        return

    text, markup = await build_categories_reply(chat_id, user_id, context.bot, is_group=False)
    await query.edit_message_text(text, reply_markup=markup)
    log.info("Открыты локальные категории", extra={"payload": {"chat_id": chat_id}})

# === Групповые категории ===
async def group_cats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    log = get_log_for_update(update, "group_cats")
    user_id = query.from_user.id
    chat_id = int(query.data.split("|")[1])

    if await get_user_role(context.bot, chat_id, user_id) != ChatMember.OWNER:
        await query.edit_message_text(t(user_id, "only_owner"))
        return

    text, markup = await build_categories_reply(chat_id, user_id, context.bot, is_group=True)
    await query.edit_message_text(text, reply_markup=markup)
    log.info("Открыты групповые категории", extra={"payload": {"chat_id": chat_id}})

# === Добавление категории ===
async def add_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    log = get_log_for_update(update, "add_category")
    user_id = query.from_user.id
    data = query.data.split("|")
    is_group = data[0].startswith("group")
    chat_id = int(data[1])

    role = await get_user_role(context.bot, chat_id, user_id)
    if role != ChatMember.OWNER and not is_group:
        if role not in [ChatMember.OWNER, ChatMember.ADMINISTRATOR]:
            await query.edit_message_text(t(user_id, "no_access"))
            return
    elif is_group and role != ChatMember.OWNER:
        await query.edit_message_text(t(user_id, "only_owner"))
        return

    context.user_data["awaiting_category"] = {
        "chat_id": chat_id,
        "is_group": is_group,
        "step": "name"
    }
    await query.edit_message_text(t(user_id, "enter_category_name"))
    log.info("Ожидание имени категории", extra={"payload": {"chat_id": chat_id, "is_group": is_group}})

# === Редактирование категории ===
async def edit_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log = get_log_for_update(update, "edit_category_callback")

    query = update.callback_query
    await query.answer()
    data = query.data.split("|")
    is_group = data[0].startswith("group")
    cat_id = int(data[1])
    chat_id = int(data[2])
    user_id = query.from_user.id

    role = await get_user_role(context.bot, chat_id, user_id)
    if role != ChatMember.OWNER:
        await query.edit_message_text(t(user_id, "only_owner"))
        return

    with Session() as session:
        cat = session.get(Category, cat_id)
        if not cat or (is_group and cat.group_id is None) or (not is_group and cat.chat_id != chat_id):
            await query.edit_message_text(t(user_id, "category_not_found"))
            return

        context.user_data["awaiting_category"] = {
            "cat_id": cat_id,
            "chat_id": chat_id,
            "is_group": is_group,
            "step": "name",
            "old_name": cat.name,
            "old_keywords": cat.keywords,
            "old_response": cat.response
        }

    await query.edit_message_text(t(user_id, "enter_category_name_edit", old_name=cat.name))
    log.info("Редактирование категории", extra={"payload": {"cat_id": cat_id}})

# === Удаление категории ===
async def delete_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log = get_log_for_update(update, "delete_category_callback")
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")
    is_group = data[0].startswith("group")
    cat_id = int(data[1])
    chat_id = int(data[2])
    user_id = query.from_user.id

    role = await get_user_role(context.bot, chat_id, user_id)
    if role != ChatMember.OWNER:
        await query.edit_message_text(t(user_id, "only_owner"))
        return

    with Session() as session:
        cat = session.get(Category, cat_id)
        if cat:
            session.delete(cat)
            session.commit()
    text, markup = await build_categories_reply(chat_id, user_id, context.bot, is_group=is_group)
    await query.edit_message_text(text, reply_markup=markup)
    log.info("Категория удалена", extra={"payload": {"cat_id": cat_id}})

# === Обработка ввода категории ===
async def handle_category_input(update: Update, context: ContextTypes.DEFAULT_TYPE, state: dict):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    log = get_log_for_update(update, "handle_category_input")
    step = state["step"]

    if step == "name":
        if not text:
            await update.message.reply_text(t(user_id, "empty_category_name"))
            return
        state["name"] = text
        state["step"] = "keywords"

        template = ""
        if state.get("old_keywords"):
            template = t(user_id, "old_value")+state["old_keywords"]+"\n"
        await update.message.reply_text(template+t(user_id, "enter_category_keywords"))
        return

    if step == "keywords":
        state["keywords"] = text
        state["step"] = "response"

        template = ""
        if state.get("old_response"):
            template = t(user_id, "old_value")+state["old_response"] + "\n"
        await update.message.reply_text(template+t(user_id, "enter_category_response"))
        return

    if step == "response":
        state["response"] = text
        chat_id = state["chat_id"]
        is_group = state["is_group"]

        try:
            with Session() as session:
                chat = session.get(Chat, chat_id)

                if "cat_id" in state:
                    cat = session.get(Category, state["cat_id"])
                else:
                    cat = Category()
                    session.add(cat)

                cat.name = state["name"]
                cat.keywords = state["keywords"]
                cat.response = state["response"]
                if is_group:
                    cat.group_id = chat.group_id
                    cat.chat_id = None
                else:
                    cat.chat_id = chat_id
                    cat.group_id = None
                session.commit()
            await update.message.reply_text(t(user_id, "category_saved"))
            log.info("Категория сохранена", extra={"payload": {"name": state["name"], "chat_id": chat_id, "is_group": is_group}})
        except Exception as e:
            await update.message.reply_text(t(user_id, "error_saving_category"))
            log.exception("Ошибка сохранения категории", extra={"payload": {"error": str(e)}})

        # Возврат к списку
        text, markup = await build_categories_reply(chat_id, user_id, context.bot, is_group=is_group)
        await update.message.reply_text(text, reply_markup=markup)

        context.user_data.pop("awaiting_category", None)

# === Noop (для preview) ===
async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

# === Обработка сообщений в группах ===
async def handle_trigger_message_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает входящие сообщения в группах — проверяет триггеры.
    """
    log = get_log_for_update(update, "handle_trigger_message")
    try:
        if not update.message or not update.message.text:
            return  # пропускаем не-текстовые сообщения

        # Проверяем, зарегистрирован ли чат в базе
        with Session() as session:
            chat = session.get(Chat, update.message.chat.id)
            if not chat:
                log.debug("Сообщение из неучтённого чата, пропускаем",
                          extra={"payload": {"chat_id": update.message.chat.id}})
                return

        # Обработка триггеров
        manager = TriggerManager()
        await manager.process_message(update.message, context.bot)

    except Exception as e:
        log.exception("Ошибка при обработке сообщения", extra={"payload": {"error": str(e)}})



# === main ===
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start,filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("my_chats", my_chats,filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("my_groups", my_groups,filters=filters.ChatType.PRIVATE))

    app.add_handler(CallbackQueryHandler(back_to_my_chats, pattern=r"^back_to_my_chats$"))
    app.add_handler(CallbackQueryHandler(chat_settings_callback, pattern=r"^chat_settings\|"))

    app.add_handler(CallbackQueryHandler(view_group_callback, pattern=r"^view_group\|"))
    app.add_handler(CallbackQueryHandler(back_to_my_groups, pattern=r"^back_to_my_groups$"))
    app.add_handler(CallbackQueryHandler(my_groups_from_menu, pattern=r"^my_groups_from_menu$"))

    app.add_handler(CallbackQueryHandler(create_group_callback, pattern=r"^create_group\|"))
    app.add_handler(CallbackQueryHandler(assign_group_callback, pattern=r"^1\|"))  # старое поведение assign_group
    app.add_handler(CallbackQueryHandler(assign_group_confirm_callback, pattern=r"^assign_group_confirm\|"))

    app.add_handler(CallbackQueryHandler(local_cats_callback, pattern=r"^local_cats\|"))
    app.add_handler(CallbackQueryHandler(group_cats_callback, pattern=r"^group_cats\|"))
    app.add_handler(CallbackQueryHandler(add_category_callback, pattern=r"^(local|group)_add_cat\|"))
    app.add_handler(CallbackQueryHandler(edit_category_callback, pattern=r"^(local|group)_edit_cat\|"))
    app.add_handler(CallbackQueryHandler(delete_category_callback, pattern=r"^(local|group)_delete_cat\|"))
    app.add_handler(CallbackQueryHandler(noop_callback, pattern=r"^noop$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_trigger_message_chats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_text_private))
    app.add_handler(ChatMemberHandler(handle_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))


    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()