import sqlite3
import logging
import os
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
from telegram.constants import ParseMode

# Конфигурация
BOT_TOKEN = "8226025643:AAHyrVkbV8wFum7tLbAxvhtRq5Sh_-VkH-M"
OWNER_IDS = [287265398, 7396843811]
ADMIN_IDS = [287265398, 7396843811]
MODER_IDS = []
CHANNEL_ID = -1003911175144
CHANNEL_LINK = "https://t.me/mirokfame"
SITE_LINK = "https://релиза пока не было"
CHECK_SUBSCRIPTION = True

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Состояния
(APP_AVATAR, APP_NICKNAME, APP_PROJECT, APP_CHAT, APP_KM_YEAR,
 APP_PARTICIPATED, APP_REASON, APP_FAME_METHOD, APP_ACQUAINTANCES) = range(9)

(COMPLAINT_USER, COMPLAINT_REASON, COMPLAINT_EVIDENCE) = range(9, 12)

(ADD_NOTE, REJECT_REASON, BROADCAST_MESSAGE, TICKET_QUESTION, 
 ANSWER_TICKET, ANSWER_COMPLAINT, ADD_MODER) = range(12, 19)

class Database:
    def __init__(self, db_file="bot_data.db"):
        self.db_file = db_file
        self.conn = None
        self.init_db()

    def get_connection(self):
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_file, timeout=10, check_same_thread=False)
        return self.conn

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            nickname TEXT,
            avatar_file_id TEXT,
            project TEXT,
            chat_link TEXT,
            km_year TEXT,
            participated_before TEXT,
            reason TEXT,
            fame_method TEXT,
            acquaintances TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_by INTEGER,
            reviewed_at TIMESTAMP,
            reject_reason TEXT,
            admin_notes TEXT DEFAULT ''
        )''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER,
            user_id INTEGER,
            username TEXT,
            nickname TEXT,
            action TEXT,
            admin_id INTEGER,
            reason TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user_id INTEGER,
            from_username TEXT,
            on_user_info TEXT,
            reason TEXT,
            evidence TEXT,
            status TEXT DEFAULT 'pending',
            admin_response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            question TEXT,
            status TEXT DEFAULT 'open',
            admin_response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS moders (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        conn.commit()
        # Загружаем модераторов из БД
        self.load_moders()
        logger.info("База данных инициализирована")

    def load_moders(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM moders')
        for row in cursor.fetchall():
            if row[0] not in MODER_IDS:
                MODER_IDS.append(row[0])

    def add_moder(self, user_id, username, added_by):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO moders (user_id, username, added_by) VALUES (?, ?, ?)',
                      (user_id, username, added_by))
        conn.commit()
        if user_id not in MODER_IDS:
            MODER_IDS.append(user_id)

    def remove_moder(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM moders WHERE user_id = ?', (user_id,))
        conn.commit()
        if user_id in MODER_IDS:
            MODER_IDS.remove(user_id)

    def get_all_moders(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, username, added_by, added_at FROM moders')
        return cursor.fetchall()

    def add_user(self, user_id, username):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO users (user_id, username) VALUES (?, ?)',
                      (user_id, username))
        conn.commit()

    def get_all_users(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT user_id FROM users')
        return [row[0] for row in cursor.fetchall()]

    def get_user_applications_count(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM applications WHERE user_id = ? AND status = "pending"', (user_id,))
        return cursor.fetchone()[0]

    def add_application(self, user_id, username, nickname, avatar_file_id,
                        project, chat_link, km_year, participated_before,
                        reason, fame_method, acquaintances):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO applications
            (user_id, username, nickname, avatar_file_id, project, chat_link,
             km_year, participated_before, reason, fame_method, acquaintances)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (user_id, username, nickname, avatar_file_id, project, chat_link,
             km_year, participated_before, reason, fame_method, acquaintances))
        app_id = cursor.lastrowid
        conn.commit()
        return app_id

    def get_pending_applications(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, user_id, username, nickname, created_at FROM applications WHERE status = "pending" ORDER BY created_at DESC')
        return cursor.fetchall()

    def get_application_by_id(self, app_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM applications WHERE id = ?', (app_id,))
        return cursor.fetchone()

    def update_application_status(self, app_id, status, admin_id, reject_reason=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        now = datetime.now()
        if status == 'rejected' and reject_reason:
            cursor.execute('UPDATE applications SET status = ?, reviewed_by = ?, reviewed_at = ?, reject_reason = ? WHERE id = ?',
                          (status, admin_id, now, reject_reason, app_id))
        else:
            cursor.execute('UPDATE applications SET status = ?, reviewed_by = ?, reviewed_at = ? WHERE id = ?',
                          (status, admin_id, now, app_id))
        app = self.get_application_by_id(app_id)
        if app:
            action = 'accepted' if status == 'accepted' else 'rejected'
            cursor.execute('''INSERT INTO history
                (application_id, user_id, username, nickname, action, admin_id, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (app_id, app[1], app[2], app[3], action, admin_id, reject_reason))
        conn.commit()

    def add_admin_note(self, app_id, admin_id, admin_username, note):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT admin_notes FROM applications WHERE id = ?', (app_id,))
        row = cursor.fetchone()
        current_notes = row[0] if row and row[0] else ""
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
        new_note = f"\n📌 {timestamp} | {admin_username} (ID: {admin_id}):\n{note}\n{'─'*30}"
        cursor.execute('UPDATE applications SET admin_notes = ? WHERE id = ?',
                      (current_notes + new_note, app_id))
        conn.commit()

    def get_history(self, limit=30):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''SELECT id, application_id, user_id, username, nickname,
                         action, admin_id, reason, timestamp
                         FROM history ORDER BY timestamp DESC LIMIT ?''', (limit,))
        return cursor.fetchall()

    def add_complaint(self, from_user_id, from_username, on_user_info, reason, evidence):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO complaints
            (from_user_id, from_username, on_user_info, reason, evidence)
            VALUES (?, ?, ?, ?, ?)''',
            (from_user_id, from_username, on_user_info, reason, evidence))
        complaint_id = cursor.lastrowid
        conn.commit()
        return complaint_id

    def get_pending_complaints(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''SELECT id, from_user_id, from_username, on_user_info,
                         reason, evidence, status, created_at
                         FROM complaints WHERE status = "pending"
                         ORDER BY created_at DESC''')
        return cursor.fetchall()

    def get_complaint_by_id(self, complaint_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM complaints WHERE id = ?', (complaint_id,))
        return cursor.fetchone()

    def update_complaint_status(self, complaint_id, status, admin_response=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE complaints SET status = ?, admin_response = ? WHERE id = ?',
                      (status, admin_response, complaint_id))
        conn.commit()

    def add_ticket(self, user_id, username, question):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO tickets (user_id, username, question) VALUES (?, ?, ?)',
                      (user_id, username, question))
        ticket_id = cursor.lastrowid
        conn.commit()
        return ticket_id

    def get_open_tickets(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''SELECT id, user_id, username, question, status, created_at
                         FROM tickets WHERE status = "open"
                         ORDER BY created_at DESC''')
        return cursor.fetchall()

    def get_ticket_by_id(self, ticket_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,))
        return cursor.fetchone()

    def update_ticket_status(self, ticket_id, status, admin_response=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE tickets SET status = ?, admin_response = ? WHERE id = ?',
                      (status, admin_response, ticket_id))
        conn.commit()

    def get_stats(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM applications')
        total_apps = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM applications WHERE status = "pending"')
        pending_apps = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM applications WHERE status = "accepted"')
        accepted_apps = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM applications WHERE status = "rejected"')
        rejected_apps = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM complaints')
        total_complaints = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM complaints WHERE status = "pending"')
        pending_complaints = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM tickets')
        total_tickets = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM tickets WHERE status = "open"')
        open_tickets = cursor.fetchone()[0]
        return {
            'total_users': total_users,
            'total_apps': total_apps,
            'pending_apps': pending_apps,
            'accepted_apps': accepted_apps,
            'rejected_apps': rejected_apps,
            'total_complaints': total_complaints,
            'pending_complaints': pending_complaints,
            'total_tickets': total_tickets,
            'open_tickets': open_tickets
        }

db = Database()

def is_owner(user_id):
    return user_id in OWNER_IDS

def is_admin(user_id):
    return user_id in ADMIN_IDS or user_id in OWNER_IDS

def is_moder(user_id):
    return user_id in MODER_IDS

def has_access(user_id):
    return is_admin(user_id) or is_moder(user_id)

def get_user_keyboard():
    return ReplyKeyboardMarkup([
        ["🌐 Перейти на сайт", "📝 Отправить заявку"],
        ["🎯 ArictoSession"],
        ["📋 Правила", "⚠️ Пожаловаться"],
        ["🎫 Тикет"]
    ], resize_keyboard=True)

def get_admin_keyboard():
    return ReplyKeyboardMarkup([
        ["🌐 Перейти на сайт", "📝 Отправить заявку"],
        ["🎯 ArictoSession"],
        ["📋 Правила", "⚠️ Пожаловаться"],
        ["🎫 Тикет"],
        ["📊 Заявки", "📜 История"],
        ["📨 Рассылка", "📋 Жалобы"],
        ["🎫 Тикеты", "📈 Статистика"]
    ], resize_keyboard=True)

def get_owner_keyboard():
    return ReplyKeyboardMarkup([
        ["🌐 Перейти на сайт", "📝 Отправить заявку"],
        ["🎯 ArictoSession"],
        ["📋 Правила", "⚠️ Пожаловаться"],
        ["🎫 Тикет"],
        ["📊 Заявки", "📜 История"],
        ["📨 Рассылка", "📋 Жалобы"],
        ["🎫 Тикеты", "📈 Статистика"],
        ["👥 Модеры"]
    ], resize_keyboard=True)

def get_moder_keyboard():
    return ReplyKeyboardMarkup([
        ["🌐 Перейти на сайт", "📝 Отправить заявку"],
        ["🎯 ArictoSession"],
        ["📋 Правила", "⚠️ Пожаловаться"],
        ["🎫 Тикет"],
        ["📊 Заявки", "📜 История"],
        ["📋 Жалобы", "🎫 Тикеты"]
    ], resize_keyboard=True)

def get_app_view_keyboard(app_id, user_id):
    keyboard = []
    if is_admin(user_id):
        keyboard.append([
            InlineKeyboardButton("✅ ПРИНЯТЬ", callback_data=f"accept_{app_id}"),
            InlineKeyboardButton("❌ ОТКЛОНИТЬ", callback_data=f"reject_{app_id}")
        ])
    keyboard.append([InlineKeyboardButton("📝 ЗАМЕТКА", callback_data=f"note_{app_id}")])
    return InlineKeyboardMarkup(keyboard)

def get_apps_list_keyboard(apps):
    if not apps:
        return None
    keyboard = []
    for app in apps:
        keyboard.append([InlineKeyboardButton(f"👤 {app[3]} | #{app[0]}", callback_data=f"view_{app[0]}")])
    return InlineKeyboardMarkup(keyboard)

def get_complaints_list_keyboard(complaints):
    if not complaints:
        return None
    keyboard = []
    for complaint in complaints:
        keyboard.append([InlineKeyboardButton(f"⚠️ От @{complaint[2]} | #{complaint[0]}", callback_data=f"view_complaint_{complaint[0]}")])
    return InlineKeyboardMarkup(keyboard)

def get_tickets_list_keyboard(tickets):
    if not tickets:
        return None
    keyboard = []
    for ticket in tickets:
        keyboard.append([InlineKeyboardButton(f"🎫 От @{ticket[2]} | #{ticket[0]}", callback_data=f"view_ticket_{ticket[0]}")])
    return InlineKeyboardMarkup(keyboard)

def get_complaint_view_keyboard(complaint_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ ЗАКРЫТЬ", callback_data=f"close_complaint_{complaint_id}"),
         InlineKeyboardButton("✏️ ОТВЕТИТЬ", callback_data=f"answer_complaint_{complaint_id}")]
    ])

def get_ticket_view_keyboard(ticket_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ ЗАКРЫТЬ", callback_data=f"close_ticket_{ticket_id}"),
         InlineKeyboardButton("✏️ ОТВЕТИТЬ", callback_data=f"answer_ticket_{ticket_id}")]
    ])

def get_moders_keyboard():
    moders = db.get_all_moders()
    keyboard = []
    for m in moders:
        keyboard.append([InlineKeyboardButton(f"❌ Удалить @{m[1]} (ID: {m[0]})", callback_data=f"removemoder_{m[0]}")])
    return InlineKeyboardMarkup(keyboard) if keyboard else None

async def check_subscription(bot, user_id):
    if not CHECK_SUBSCRIPTION:
        return True
    try:
        chat_member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except:
        return False

def format_application(app):
    if not app:
        return "Заявка не найдена"
    notes = app[17] if len(app) > 17 and app[17] else 'Нет заметок'
    reject_reason = app[16] if len(app) > 16 and app[16] else 'Не указана'
    return f"""
📝 <b>ЗАЯВКА #{app[0]}</b>

👤 <b>Никнейм:</b> {app[3] or 'Не указан'}
🆔 <b>User ID:</b> <code>{app[1]}</code>
📌 <b>Юзернейм:</b> @{app[2] if app[2] else 'нет'}

📁 <b>Проект:</b> {app[5]}
💬 <b>Чат:</b> {app[6] or 'Не указан'}

📅 <b>Год в КМ:</b> {app[7]}
🎯 <b>Участие в ВК/ДС КМ:</b> {app[8]}

💭 <b>Почему хочет попасть:</b> {app[9] or 'Не указано'}
📈 <b>Как поднимал фейм:</b> {app[10]}
👥 <b>Знакомства:</b> {app[11]}

📝 <b>Заметки админов:</b>
{notes}

❌ <b>Причина отклонения:</b> {reject_reason}
⏰ <b>Создана:</b> {app[13]}
"""

def format_complaint(complaint):
    if not complaint:
        return "Жалоба не найдена"
    return f"""
⚠️ <b>ЖАЛОБА #{complaint[0]}</b>

👤 <b>От:</b> @{complaint[2] or 'нет'} (ID: <code>{complaint[1]}</code>)
👥 <b>Нарушитель:</b> {complaint[3]}
📝 <b>Причина:</b> {complaint[4]}
📎 <b>Доказательства:</b> {complaint[5] or 'Не предоставлены'}
📊 <b>Статус:</b> {complaint[6]}
⏰ <b>Создана:</b> {complaint[7]}
"""

def format_ticket(ticket):
    if not ticket:
        return "Тикет не найден"
    return f"""
🎫 <b>ТИКЕТ #{ticket[0]}</b>

👤 <b>От:</b> @{ticket[2] or 'нет'} (ID: <code>{ticket[1]}</code>)
❓ <b>Вопрос:</b> {ticket[3]}
💬 <b>Ответ:</b> {ticket[5] or 'Нет ответа'}
📊 <b>Статус:</b> {ticket[4]}
⏰ <b>Создан:</b> {ticket[6]}
"""

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}", exc_info=True)
    try:
        if update and update.effective_message:
            context.user_data.clear()
            user_id = update.effective_user.id
            kb = get_user_keyboard()
            if is_owner(user_id):
                kb = get_owner_keyboard()
            elif is_admin(user_id):
                kb = get_admin_keyboard()
            elif is_moder(user_id):
                kb = get_moder_keyboard()
            await update.effective_message.reply_text("❌ Произошла ошибка. Попробуйте снова.", reply_markup=kb)
    except:
        pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user_id = update.effective_user.id
    username = update.effective_user.username
    db.add_user(user_id, username)

    if not await check_subscription(context.bot, user_id):
        await update.message.reply_text(
            f"❌ <b>Для использования бота подпишитесь на канал!</b>\n\n"
            f"👉 <a href='{CHANNEL_LINK}'>ПОДПИСАТЬСЯ</a>\n\n"
            f"После подписки нажмите /start",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
        return

    if is_owner(user_id):
        await update.message.reply_text("👑 Панель владельца активирована!", reply_markup=get_owner_keyboard())
    elif is_admin(user_id):
        await update.message.reply_text("🛡️ Админ-панель активирована!", reply_markup=get_admin_keyboard())
    elif is_moder(user_id):
        await update.message.reply_text("🔧 Панель модератора активирована!", reply_markup=get_moder_keyboard())
    else:
        await update.message.reply_text("✨ Добро пожаловать в Aricto Fame!", reply_markup=get_user_keyboard())

async def site_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🌐 Наш сайт: {SITE_LINK}")

async def aricto_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 Чтобы попасть в ArictoSession, напишите владельцу: @faymovy")

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📜 <b>ПРАВИЛА:</b>\n\n"
        "1. Заполняйте анкету честно\n"
        "2. Запрещены оскорбления\n"
        "3. Запрещен спам\n"
        "4. За скам - бан\n"
        "5. Уважайте администрацию",
        parse_mode=ParseMode.HTML
    )

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not has_access(user_id):
        return
    stats = db.get_stats()
    text = f"""
📈 <b>СТАТИСТИКА БОТА</b>

👥 <b>Всего пользователей:</b> {stats['total_users']}

📝 <b>Заявки:</b>
   • Всего: {stats['total_apps']}
   • В ожидании: {stats['pending_apps']}
   • Принято: {stats['accepted_apps']}
   • Отклонено: {stats['rejected_apps']}

⚠️ <b>Жалобы:</b>
   • Всего: {stats['total_complaints']}
   • В ожидании: {stats['pending_complaints']}

🎫 <b>Тикеты:</b>
   • Всего: {stats['total_tickets']}
   • Открыто: {stats['open_tickets']}
"""
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def start_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user_id = update.effective_user.id
    if db.get_user_applications_count(user_id) > 0:
        await update.message.reply_text("❌ У вас уже есть активная заявка!")
        return ConversationHandler.END
    await update.message.reply_text("📸 Отправьте аватарку:")
    return APP_AVATAR

async def app_avatar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Отправьте фото!")
        return APP_AVATAR
    context.user_data['avatar'] = update.message.photo[-1].file_id
    await update.message.reply_text("✏️ Введите никнейм:")
    return APP_NICKNAME

async def app_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['nickname'] = update.message.text
    await update.message.reply_text("🔗 Введите ссылку на проект:")
    return APP_PROJECT

async def app_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['project'] = update.message.text
    await update.message.reply_text("💬 Введите ссылку на чат (или '-'):")
    return APP_CHAT

async def app_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data['chat_link'] = None if text == '-' else text
    await update.message.reply_text("📅 С какого года в КМ?")
    return APP_KM_YEAR

async def app_km_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['km_year'] = update.message.text
    await update.message.reply_text("🎯 Участвовали в ВК/ДС КМ? (да/нет/подробнее)")
    return APP_PARTICIPATED

async def app_participated(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['participated'] = update.message.text
    await update.message.reply_text("💭 Почему хотите к нам? (или '-'):")
    return APP_REASON

async def app_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data['reason'] = None if text == '-' else text
    await update.message.reply_text("📈 Как поднимали фейм?")
    return APP_FAME_METHOD

async def app_fame_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['fame_method'] = update.message.text
    await update.message.reply_text("👥 С кем знакомы?")
    return APP_ACQUAINTANCES

async def app_acquaintances(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = context.user_data
    app_id = db.add_application(user.id, user.username, data['nickname'], data['avatar'],
                                data['project'], data.get('chat_link'), data['km_year'],
                                data['participated'], data.get('reason'), data['fame_method'],
                                update.message.text)
    kb = get_user_keyboard()
    if is_owner(user.id):
        kb = get_owner_keyboard()
    elif is_admin(user.id):
        kb = get_admin_keyboard()
    elif is_moder(user.id):
        kb = get_moder_keyboard()
    await update.message.reply_text(f"✅ <b>Заявка #{app_id} отправлена!</b>\n\nОжидайте рассмотрения.", parse_mode=ParseMode.HTML, reply_markup=kb)
    for uid in ADMIN_IDS + MODER_IDS:
        try:
            await context.bot.send_message(uid, f"🔔 <b>Новая заявка #{app_id}</b>\n👤 От: {data['nickname']}\n📁 Проект: {data['project']}", parse_mode=ParseMode.HTML)
        except:
            pass
    context.user_data.clear()
    return ConversationHandler.END

async def show_applications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        return
    apps = db.get_pending_applications()
    if not apps:
        await update.message.reply_text("📭 Нет активных заявок.")
        return
    kb = get_apps_list_keyboard(apps)
    if kb:
        await update.message.reply_text("📊 <b>Активные заявки:</b>", parse_mode=ParseMode.HTML, reply_markup=kb)

async def view_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not has_access(user_id):
        return
    try:
        app_id = int(query.data.split("_")[1])
        app = db.get_application_by_id(app_id)
        if not app:
            await query.message.reply_text("❌ Заявка не найдена!")
            return
        text = format_application(app)
        if len(app) > 4 and app[4]:
            await query.message.reply_photo(photo=app[4], caption=text, parse_mode=ParseMode.HTML, reply_markup=get_app_view_keyboard(app_id, user_id))
        else:
            await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=get_app_view_keyboard(app_id, user_id))
    except:
        await query.message.reply_text("❌ Ошибка при загрузке заявки")
    try:
        await query.message.delete()
    except:
        pass

async def accept_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    try:
        app_id = int(query.data.split("_")[1])
        app = db.get_application_by_id(app_id)
        if not app:
            await query.message.reply_text("❌ Заявка не найдена!")
            return
        db.update_application_status(app_id, 'accepted', query.from_user.id)
        try:
            await context.bot.send_message(app[1], f"✅ <b>Заявка #{app_id} ПРИНЯТА!</b>\n\nДобро пожаловать в Aricto Fame!", parse_mode=ParseMode.HTML)
        except:
            pass
        await query.message.reply_text(f"✅ Заявка #{app_id} принята!")
    except:
        await query.message.reply_text("❌ Ошибка")
    try:
        await query.message.delete()
    except:
        pass

async def reject_app_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return ConversationHandler.END
    try:
        app_id = int(query.data.split("_")[1])
        context.user_data['reject_app_id'] = app_id
        await query.message.reply_text("❌ Введите причину отклонения:")
        return REJECT_REASON
    except:
        return ConversationHandler.END

async def reject_app_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text
    admin_id = update.effective_user.id
    app_id = context.user_data.get('reject_app_id')
    if not app_id:
        kb = get_admin_keyboard() if is_admin(admin_id) else get_moder_keyboard()
        await update.message.reply_text("❌ Ошибка", reply_markup=kb)
        context.user_data.clear()
        return ConversationHandler.END
    app = db.get_application_by_id(app_id)
    if app:
        db.update_application_status(app_id, 'rejected', admin_id, reason)
        try:
            await context.bot.send_message(app[1], f"❌ <b>Заявка #{app_id} ОТКЛОНЕНА</b>\n\n📝 Причина: {reason}", parse_mode=ParseMode.HTML)
        except:
            pass
    kb = get_admin_keyboard() if is_admin(admin_id) else get_moder_keyboard()
    await update.message.reply_text(f"❌ Заявка #{app_id} отклонена.", reply_markup=kb)
    context.user_data.clear()
    return ConversationHandler.END

async def add_note_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_access(query.from_user.id):
        return ConversationHandler.END
    try:
        app_id = int(query.data.split("_")[1])
        context.user_data['note_app_id'] = app_id
        await query.message.reply_text("📝 Введите текст заметки:")
        return ADD_NOTE
    except:
        return ConversationHandler.END

async def add_note_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note_text = update.message.text
    admin = update.effective_user
    app_id = context.user_data.get('note_app_id')
    if app_id:
        db.add_admin_note(app_id, admin.id, admin.username or "Без username", note_text)
        kb = get_admin_keyboard() if is_admin(admin.id) else get_moder_keyboard()
        await update.message.reply_text(f"✅ Заметка добавлена к заявке #{app_id}", reply_markup=kb)
    context.user_data.clear()
    return ConversationHandler.END

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        return
    history = db.get_history(30)
    if not history:
        await update.message.reply_text("📭 История пуста.")
        return
    text = "📜 <b>ИСТОРИЯ ЗАЯВОК:</b>\n\n"
    for h in history:
        action_emoji = "✅" if h[5] == 'accepted' else "❌"
        text += f"{action_emoji} <b>#{h[1]}</b> | {h[4]} | Админ ID: {h[6]}\n"
        if len(h) > 7 and h[7]:
            text += f"   📝 Причина: {h[7]}\n"
        text += f"   📅 {h[8]}\n\n"
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            await update.message.reply_text(text[i:i+4000], parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Нет прав!")
        return ConversationHandler.END
    await update.message.reply_text("📨 Введите текст рассылки (или /cancel):")
    return BROADCAST_MESSAGE

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    if message_text == '/cancel':
        context.user_data.clear()
        await update.message.reply_text("❌ Отменена", reply_markup=get_admin_keyboard())
        return ConversationHandler.END
    users = db.get_all_users()
    if not users:
        await update.message.reply_text("❌ Нет пользователей", reply_markup=get_admin_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    await update.message.reply_text(f"📨 Рассылка на {len(users)} пользователей...")
    success, failed = 0, 0
    for user_id in users:
        try:
            await context.bot.send_message(user_id, f"📢 <b>Сообщение от администрации:</b>\n\n{message_text}", parse_mode=ParseMode.HTML)
            success += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    await update.message.reply_text(f"📊 <b>Рассылка завершена!</b>\n\n✅ {success}\n❌ {failed}", parse_mode=ParseMode.HTML, reply_markup=get_admin_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

async def complaint_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("⚠️ Укажите username или ссылку на нарушителя:")
    return COMPLAINT_USER

async def complaint_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['complaint_on'] = update.message.text
    await update.message.reply_text("📝 Опишите причину:")
    return COMPLAINT_REASON

async def complaint_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['complaint_reason'] = update.message.text
    await update.message.reply_text("📎 Прикрепите доказательства (текст/фото/видео):")
    return COMPLAINT_EVIDENCE

async def complaint_evidence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    if 'complaint_on' not in context.user_data:
        kb = get_user_keyboard()
        if is_owner(user_id): kb = get_owner_keyboard()
        elif is_admin(user_id): kb = get_admin_keyboard()
        elif is_moder(user_id): kb = get_moder_keyboard()
        await update.message.reply_text("❌ Ошибка", reply_markup=kb)
        context.user_data.clear()
        return ConversationHandler.END
    evidence = "Не предоставлены"
    if update.message.text:
        evidence = update.message.text
    elif update.message.photo:
        evidence = f"Фото (file_id: {update.message.photo[-1].file_id})"
    elif update.message.video:
        evidence = f"Видео (file_id: {update.message.video.file_id})"
    try:
        complaint_id = db.add_complaint(user_id, username, context.user_data['complaint_on'], context.user_data['complaint_reason'], evidence)
        for uid in ADMIN_IDS + MODER_IDS:
            try:
                await context.bot.send_message(uid, f"⚠️ <b>НОВАЯ ЖАЛОБА #{complaint_id}</b>\n👤 От: @{username or 'нет'}\n👥 Нарушитель: {context.user_data['complaint_on']}\n📝 Причина: {context.user_data['complaint_reason']}", parse_mode=ParseMode.HTML)
            except:
                pass
        kb = get_user_keyboard()
        if is_owner(user_id): kb = get_owner_keyboard()
        elif is_admin(user_id): kb = get_admin_keyboard()
        elif is_moder(user_id): kb = get_moder_keyboard()
        await update.message.reply_text(f"✅ Жалоба #{complaint_id} отправлена!", reply_markup=kb)
    except:
        kb = get_user_keyboard()
        await update.message.reply_text("❌ Ошибка при отправке", reply_markup=kb)
    context.user_data.clear()
    return ConversationHandler.END

async def show_complaints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        return
    complaints = db.get_pending_complaints()
    if not complaints:
        await update.message.reply_text("📭 Нет активных жалоб.")
        return
    kb = get_complaints_list_keyboard(complaints)
    if kb:
        await update.message.reply_text("📋 <b>Активные жалобы:</b>", parse_mode=ParseMode.HTML, reply_markup=kb)

async def view_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_access(query.from_user.id):
        return
    try:
        complaint_id = int(query.data.split("_")[2])
        complaint = db.get_complaint_by_id(complaint_id)
        if not complaint:
            await query.message.reply_text("❌ Жалоба не найдена!")
            return
        text = format_complaint(complaint)
        await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=get_complaint_view_keyboard(complaint_id))
    except:
        await query.message.reply_text("❌ Ошибка")
    try:
        await query.message.delete()
    except:
        pass

async def close_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_access(query.from_user.id):
        return
    try:
        complaint_id = int(query.data.split("_")[2])
        complaint = db.get_complaint_by_id(complaint_id)
        if complaint:
            db.update_complaint_status(complaint_id, 'closed')
            try:
                await context.bot.send_message(complaint[1], f"📋 <b>Ваша жалоба #{complaint_id} обработана</b>\n\nЖалоба рассмотрена.", parse_mode=ParseMode.HTML)
            except:
                pass
        await query.message.reply_text(f"✅ Жалоба #{complaint_id} закрыта!")
    except:
        await query.message.reply_text("❌ Ошибка")
    try:
        await query.message.delete()
    except:
        pass

async def answer_complaint_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_access(query.from_user.id):
        return ConversationHandler.END
    try:
        complaint_id = int(query.data.split("_")[2])
        context.user_data['answer_complaint_id'] = complaint_id
        await query.message.reply_text("✏️ Введите ответ на жалобу:")
        return ANSWER_COMPLAINT
    except:
        return ConversationHandler.END

async def answer_complaint_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    response = update.message.text
    admin = update.effective_user
    complaint_id = context.user_data.get('answer_complaint_id')
    if not complaint_id:
        kb = get_admin_keyboard() if is_admin(admin.id) else get_moder_keyboard()
        await update.message.reply_text("❌ Ошибка", reply_markup=kb)
        context.user_data.clear()
        return ConversationHandler.END
    complaint = db.get_complaint_by_id(complaint_id)
    if complaint:
        db.update_complaint_status(complaint_id, 'closed', response)
        try:
            await context.bot.send_message(complaint[1], f"📋 <b>Ответ на вашу жалобу #{complaint_id}</b>\n\n📝 {response}\n\n👤 Ответил: @{admin.username or 'admin'}", parse_mode=ParseMode.HTML)
        except:
            pass
    kb = get_admin_keyboard() if is_admin(admin.id) else get_moder_keyboard()
    await update.message.reply_text(f"✅ Ответ на жалобу #{complaint_id} отправлен!", reply_markup=kb)
    context.user_data.clear()
    return ConversationHandler.END

async def ticket_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🎫 Задайте вопрос:")
    return TICKET_QUESTION

async def ticket_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = update.message.text
    user = update.effective_user
    ticket_id = db.add_ticket(user.id, user.username, question)
    for uid in ADMIN_IDS + MODER_IDS:
        try:
            await context.bot.send_message(uid, f"🎫 <b>НОВЫЙ ТИКЕТ #{ticket_id}</b>\n👤 От: @{user.username or 'нет'}\n❓ Вопрос: {question}", parse_mode=ParseMode.HTML)
        except:
            pass
    kb = get_user_keyboard()
    if is_owner(user.id): kb = get_owner_keyboard()
    elif is_admin(user.id): kb = get_admin_keyboard()
    elif is_moder(user.id): kb = get_moder_keyboard()
    await update.message.reply_text(f"✅ Тикет #{ticket_id} отправлен!", reply_markup=kb)
    context.user_data.clear()
    return ConversationHandler.END

async def show_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        return
    tickets = db.get_open_tickets()
    if not tickets:
        await update.message.reply_text("📭 Нет открытых тикетов.")
        return
    kb = get_tickets_list_keyboard(tickets)
    if kb:
        await update.message.reply_text("🎫 <b>Открытые тикеты:</b>", parse_mode=ParseMode.HTML, reply_markup=kb)

async def view_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_access(query.from_user.id):
        return
    try:
        ticket_id = int(query.data.split("_")[2])
        ticket = db.get_ticket_by_id(ticket_id)
        if not ticket:
            await query.message.reply_text("❌ Тикет не найден!")
            return
        text = format_ticket(ticket)
        await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=get_ticket_view_keyboard(ticket_id))
    except:
        await query.message.reply_text("❌ Ошибка")
    try:
        await query.message.delete()
    except:
        pass

async def close_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_access(query.from_user.id):
        return
    try:
        ticket_id = int(query.data.split("_")[2])
        ticket = db.get_ticket_by_id(ticket_id)
        if ticket:
            db.update_ticket_status(ticket_id, 'closed')
            try:
                await context.bot.send_message(ticket[1], f"🎫 <b>Ваш тикет #{ticket_id} закрыт</b>\n\nАдминистрация рассмотрела ваш вопрос.", parse_mode=ParseMode.HTML)
            except:
                pass
        await query.message.reply_text(f"✅ Тикет #{ticket_id} закрыт!")
    except:
        await query.message.reply_text("❌ Ошибка")
    try:
        await query.message.delete()
    except:
        pass

async def answer_ticket_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not has_access(query.from_user.id):
        return ConversationHandler.END
    try:
        ticket_id = int(query.data.split("_")[2])
        context.user_data['answer_ticket_id'] = ticket_id
        await query.message.reply_text("✏️ Введите ответ на тикет:")
        return ANSWER_TICKET
    except:
        return ConversationHandler.END

async def answer_ticket_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    response = update.message.text
    admin = update.effective_user
    ticket_id = context.user_data.get('answer_ticket_id')
    if not ticket_id:
        kb = get_admin_keyboard() if is_admin(admin.id) else get_moder_keyboard()
        await update.message.reply_text("❌ Ошибка", reply_markup=kb)
        context.user_data.clear()
        return ConversationHandler.END
    ticket = db.get_ticket_by_id(ticket_id)
    if ticket:
        db.update_ticket_status(ticket_id, 'closed', response)
        try:
            await context.bot.send_message(ticket[1], f"🎫 <b>Ответ на ваш тикет #{ticket_id}</b>\n\n📝 {response}\n\n👤 Ответил: @{admin.username or 'admin'}", parse_mode=ParseMode.HTML)
        except:
            pass
    kb = get_admin_keyboard() if is_admin(admin.id) else get_moder_keyboard()
    await update.message.reply_text(f"✅ Ответ на тикет #{ticket_id} отправлен!", reply_markup=kb)
    context.user_data.clear()
    return ConversationHandler.END

async def show_moders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    moders = db.get_all_moders()
    if not moders:
        await update.message.reply_text("👥 Нет модераторов.\n\nЧтобы добавить: /addmoder ID")
        return
    text = "👥 <b>СПИСОК МОДЕРАТОРОВ:</b>\n\n"
    for m in moders:
        text += f"• @{m[1]} (ID: <code>{m[0]}</code>)\n"
    kb = get_moders_keyboard()
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

async def add_moder_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    try:
        user_id = int(context.args[0])
        try:
            user = await context.bot.get_chat(user_id)
            db.add_moder(user_id, user.username or "нет", update.effective_user.id)
            await update.message.reply_text(f"✅ Модератор @{user.username or user_id} добавлен!")
        except:
            db.add_moder(user_id, str(user_id), update.effective_user.id)
            await update.message.reply_text(f"✅ Модератор {user_id} добавлен!")
    except:
        await update.message.reply_text("❌ Использование: /addmoder USER_ID")

async def remove_moder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_owner(query.from_user.id):
        return
    try:
        user_id = int(query.data.split("_")[1])
        db.remove_moder(user_id)
        await query.message.reply_text(f"✅ Модератор {user_id} удалён!")
    except:
        await query.message.reply_text("❌ Ошибка")
    try:
        await query.message.delete()
    except:
        pass

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.clear()
    if is_owner(user_id):
        kb = get_owner_keyboard()
    elif is_admin(user_id):
        kb = get_admin_keyboard()
    elif is_moder(user_id):
        kb = get_moder_keyboard()
    else:
        kb = get_user_keyboard()
    await update.message.reply_text("❌ Действие отменено.", reply_markup=kb)
    return ConversationHandler.END

def main():
    print("🚀 БОТ ЗАПУСКАЕТСЯ...")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_error_handler(error_handler)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("addmoder", add_moder_cmd))

    app.add_handler(MessageHandler(filters.Regex('^🌐 Перейти на сайт$'), site_link))
    app.add_handler(MessageHandler(filters.Regex('^🎯 ArictoSession$'), aricto_session))
    app.add_handler(MessageHandler(filters.Regex('^📋 Правила$'), rules))
    app.add_handler(MessageHandler(filters.Regex('^📊 Заявки$'), show_applications))
    app.add_handler(MessageHandler(filters.Regex('^📜 История$'), show_history))
    app.add_handler(MessageHandler(filters.Regex('^📋 Жалобы$'), show_complaints))
    app.add_handler(MessageHandler(filters.Regex('^🎫 Тикеты$'), show_tickets))
    app.add_handler(MessageHandler(filters.Regex('^📈 Статистика$'), show_stats))
    app.add_handler(MessageHandler(filters.Regex('^👥 Модеры$'), show_moders))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^📝 Отправить заявку$'), start_application)],
        states={
            APP_AVATAR: [MessageHandler(filters.PHOTO, app_avatar)],
            APP_NICKNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, app_nickname)],
            APP_PROJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, app_project)],
            APP_CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, app_chat)],
            APP_KM_YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, app_km_year)],
            APP_PARTICIPATED: [MessageHandler(filters.TEXT & ~filters.COMMAND, app_participated)],
            APP_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, app_reason)],
            APP_FAME_METHOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, app_fame_method)],
            APP_ACQUAINTANCES: [MessageHandler(filters.TEXT & ~filters.COMMAND, app_acquaintances)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        block=False
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^⚠️ Пожаловаться$'), complaint_start)],
        states={
            COMPLAINT_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_user)],
            COMPLAINT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_reason)],
            COMPLAINT_EVIDENCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_evidence),
                MessageHandler(filters.PHOTO, complaint_evidence),
                MessageHandler(filters.VIDEO, complaint_evidence)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        block=False
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^🎫 Тикет$'), ticket_start)],
        states={TICKET_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ticket_finish)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        block=False
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(reject_app_start, pattern="^reject_")],
        states={REJECT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, reject_app_finish)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        block=False
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(add_note_start, pattern="^note_")],
        states={ADD_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_note_finish)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        block=False
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(answer_complaint_start, pattern="^answer_complaint_")],
        states={ANSWER_COMPLAINT: [MessageHandler(filters.TEXT & ~filters.COMMAND, answer_complaint_finish)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        block=False
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(answer_ticket_start, pattern="^answer_ticket_")],
        states={ANSWER_TICKET: [MessageHandler(filters.TEXT & ~filters.COMMAND, answer_ticket_finish)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        block=False
    ))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^📨 Рассылка$'), broadcast_start)],
        states={BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        block=False
    ))

    app.add_handler(CallbackQueryHandler(view_application, pattern="^view_[0-9]+$"))
    app.add_handler(CallbackQueryHandler(accept_app, pattern="^accept_"))
    app.add_handler(CallbackQueryHandler(view_complaint, pattern="^view_complaint_"))
    app.add_handler(CallbackQueryHandler(close_complaint, pattern="^close_complaint_"))
    app.add_handler(CallbackQueryHandler(view_ticket, pattern="^view_ticket_"))
    app.add_handler(CallbackQueryHandler(close_ticket, pattern="^close_ticket_"))
    app.add_handler(CallbackQueryHandler(remove_moder, pattern="^removemoder_"))

    print("✅ Бот запущен")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    main()
