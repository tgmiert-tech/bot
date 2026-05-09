
import sqlite3
import logging
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
from telegram.constants import ParseMode
import asyncio


BOT_TOKEN = "8226025643:AAHyrVkbV8wFum7tLbAxvhtRq5Sh_-VkH-M"
OWNER_IDS = [287265398, 7396843811]
ADMIN_IDS = [287265398, 7396843811]
CHANNEL_ID = -1003911175144
CHANNEL_LINK = "https://t.me/famIist"
SITE_LINK = "https://релиза пока не было"  
CHECK_SUBSCRIPTION = True


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


(APP_AVATAR, APP_NICKNAME, APP_PROJECT, APP_CHAT, APP_KM_YEAR, 
 APP_PARTICIPATED, APP_REASON, APP_FAME_METHOD, APP_ACQUAINTANCES) = range(9)

(COMPLAINT_USER, COMPLAINT_REASON, COMPLAINT_EVIDENCE) = range(9, 12)

(ADD_NOTE, REJECT_REASON, BROADCAST_MESSAGE, TICKET_QUESTION, ANSWER_TICKET, ANSWER_COMPLAINT) = range(12, 18)

class Database:
    def __init__(self, db_file="bot_data.db"):
        self.db_file = db_file
        self.conn = None
        self.init_db()
    
    def get_connection(self):
        """Получить соединение с БД"""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_file, timeout=10, check_same_thread=False)
        return self.conn
    
    def init_db(self):
        """Инициализация базы данных"""
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
        
        conn.commit()
        logger.info("База данных инициализирована")
    
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
        users = [row[0] for row in cursor.fetchall()]
        return users
    
    def get_user_applications_count(self, user_id):
        """Проверить количество активных заявок пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM applications WHERE user_id = ? AND status = "pending"', (user_id,))
        count = cursor.fetchone()[0]
        return count
    
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
        apps = cursor.fetchall()
        return apps
    
    def get_application_by_id(self, app_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM applications WHERE id = ?', (app_id,))
        app = cursor.fetchone()
        return app
    
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
        history = cursor.fetchall()
        return history
    
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
                         FROM complaints 
                         WHERE status = "pending" 
                         ORDER BY created_at DESC''')
        complaints = cursor.fetchall()
        return complaints
    
    def get_complaint_by_id(self, complaint_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM complaints WHERE id = ?', (complaint_id,))
        complaint = cursor.fetchone()
        return complaint
    
    def update_complaint_status(self, complaint_id, status, admin_response=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''UPDATE complaints 
                         SET status = ?, admin_response = ? 
                         WHERE id = ?''',
                      (status, admin_response, complaint_id))
        conn.commit()
    
    def add_ticket(self, user_id, username, question):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO tickets (user_id, username, question) 
                         VALUES (?, ?, ?)''',
                      (user_id, username, question))
        ticket_id = cursor.lastrowid
        conn.commit()
        return ticket_id
    
    def get_open_tickets(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''SELECT id, user_id, username, question, 
                         status, created_at 
                         FROM tickets 
                         WHERE status = "open" 
                         ORDER BY created_at DESC''')
        tickets = cursor.fetchall()
        return tickets
    
    def get_ticket_by_id(self, ticket_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,))
        ticket = cursor.fetchone()
        return ticket
    
    def update_ticket_status(self, ticket_id, status, admin_response=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''UPDATE tickets 
                         SET status = ?, admin_response = ? 
                         WHERE id = ?''',
                      (status, admin_response, ticket_id))
        conn.commit()


db = Database()

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
        ["🎫 Тикеты"]
    ], resize_keyboard=True)

def get_app_view_keyboard(app_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ ПРИНЯТЬ", callback_data=f"accept_{app_id}"),
         InlineKeyboardButton("❌ ОТКЛОНИТЬ", callback_data=f"reject_{app_id}")],
        [InlineKeyboardButton("📝 ЗАМЕТКА", callback_data=f"note_{app_id}")]
    ])

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
        keyboard.append([
            InlineKeyboardButton(
                f"⚠️ От @{complaint[2]} | #{complaint[0]}", 
                callback_data=f"view_complaint_{complaint[0]}"
            )
        ])
    return InlineKeyboardMarkup(keyboard)

def get_tickets_list_keyboard(tickets):
    if not tickets:
        return None
    keyboard = []
    for ticket in tickets:
        keyboard.append([
            InlineKeyboardButton(
                f"🎫 От @{ticket[2]} | #{ticket[0]}", 
                callback_data=f"view_ticket_{ticket[0]}"
            )
        ])
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

async def check_subscription(bot, user_id):
    if not CHECK_SUBSCRIPTION:
        return True
    try:
        chat_member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
        return False

def is_admin(user_id):
    return user_id in ADMIN_IDS

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

👤 <b>От пользователя:</b> @{complaint[2] or 'нет'} (ID: <code>{complaint[1]}</code>)
👥 <b>Нарушитель:</b> {complaint[3]}
📝 <b>Причина:</b> {complaint[4]}

📎 <b>Доказательства:</b>
{complaint[5] or 'Не предоставлены'}

📊 <b>Статус:</b> {complaint[6]}
⏰ <b>Создана:</b> {complaint[7]}
"""

def format_ticket(ticket):
    if not ticket:
        return "Тикет не найден"
    
    return f"""
🎫 <b>ТИКЕТ #{ticket[0]}</b>

👤 <b>От пользователя:</b> @{ticket[2] or 'нет'} (ID: <code>{ticket[1]}</code>)

❓ <b>Вопрос:</b>
{ticket[3]}

💬 <b>Ответ:</b> {ticket[5] or 'Нет ответа'}

📊 <b>Статус:</b> {ticket[4]}
⏰ <b>Создан:</b> {ticket[6]}
"""


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка при обработке обновления: {context.error}", exc_info=True)
    
    try:
        if update and update.effective_message:
            context.user_data.clear()
            
            user_id = update.effective_user.id
            kb = get_admin_keyboard() if is_admin(user_id) else get_user_keyboard()
            
            await update.effective_message.reply_text(
                "❌ Произошла ошибка. Попробуйте снова.",
                reply_markup=kb
            )
    except Exception as e:
        logger.error(f"Ошибка в обработчике ошибок: {e}")

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
            parse_mode=ParseMode.HTML, 
            disable_web_page_preview=True
        )
        return
    
    if is_admin(user_id):
        await update.message.reply_text(
            "🛡️ Админ-панель активирована!", 
            reply_markup=get_admin_keyboard()
        )
    else:
        await update.message.reply_text(
            "✨ Добро пожаловать в Aricto Fame!", 
            reply_markup=get_user_keyboard()
        )

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


async def start_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user_id = update.effective_user.id
    
    if db.get_user_applications_count(user_id) > 0:
        await update.message.reply_text("❌ У вас уже есть активная заявка! Дождитесь решения.")
        return ConversationHandler.END
    
    await update.message.reply_text("📸 Отправьте аватарку, которую хотите видеть на сайте:")
    return APP_AVATAR

async def app_avatar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Отправьте именно фото (аватарку)!")
        return APP_AVATAR
    
    context.user_data['avatar'] = update.message.photo[-1].file_id
    await update.message.reply_text("✏️ Введите ваш никнейм:")
    return APP_NICKNAME

async def app_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['nickname'] = update.message.text
    await update.message.reply_text("🔗 Введите ссылку на ваш проект:")
    return APP_PROJECT

async def app_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['project'] = update.message.text
    await update.message.reply_text("💬 Введите ссылку на ваш чат (или напишите '-' если нет):")
    return APP_CHAT

async def app_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data['chat_link'] = None if text == '-' else text
    await update.message.reply_text("📅 С какого года вы в КМ?")
    return APP_KM_YEAR

async def app_km_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['km_year'] = update.message.text
    await update.message.reply_text("🎯 Участвовали ли в ВК или ДС КМ? (да/нет/подробнее)")
    return APP_PARTICIPATED

async def app_participated(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['participated'] = update.message.text
    await update.message.reply_text("💭 Почему хотите попасть к нам? (или '-' если не хотите указывать):")
    return APP_REASON

async def app_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data['reason'] = None if text == '-' else text
    await update.message.reply_text("📈 Как вы поднимали фейм?")
    return APP_FAME_METHOD

async def app_fame_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['fame_method'] = update.message.text
    await update.message.reply_text("👥 С кем знакомы и кто может подтвердить?")
    return APP_ACQUAINTANCES

async def app_acquaintances(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = context.user_data
    
    app_id = db.add_application(
        user.id, user.username, data['nickname'], data['avatar'],
        data['project'], data.get('chat_link'), data['km_year'],
        data['participated'], data.get('reason'), data['fame_method'],
        update.message.text
    )
    
    kb = get_admin_keyboard() if is_admin(user.id) else get_user_keyboard()
    
    await update.message.reply_text(
        f"✅ <b>Заявка #{app_id} успешно отправлена!</b>\n\n"
        f"Ожидайте рассмотрения администрацией.",
        parse_mode=ParseMode.HTML, reply_markup=kb
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"🔔 <b>Новая заявка #{app_id}</b>\n"
                f"👤 От: {data['nickname']}\n"
                f"📁 Проект: {data['project']}",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить админа {admin_id}: {e}")
    
    context.user_data.clear()
    return ConversationHandler.END


async def show_complaints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать все жалобы"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав!")
        return
    
    complaints = db.get_pending_complaints()
    if not complaints:
        await update.message.reply_text("📭 Нет активных жалоб.")
        return
    
    kb = get_complaints_list_keyboard(complaints)
    if kb:
        await update.message.reply_text(
            "📋 <b>Активные жалобы:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb
        )

async def view_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр конкретной жалобы"""
    query = update.callback_query
    await query.answer()
    
    try:
        complaint_id = int(query.data.split("_")[2])
        complaint = db.get_complaint_by_id(complaint_id)
        
        if not complaint:
            await query.message.reply_text("❌ Жалоба не найдена!")
            return
        
        text = format_complaint(complaint)
        
        await query.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_complaint_view_keyboard(complaint_id)
        )
    except Exception as e:
        logger.error(f"Ошибка при просмотре жалобы: {e}")
        await query.message.reply_text("❌ Произошла ошибка при загрузке жалобы")
    
    try:
        await query.message.delete()
    except:
        pass

async def close_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Закрыть жалобу"""
    query = update.callback_query
    await query.answer()
    
    admin_id = query.from_user.id
    if not is_admin(admin_id):
        return
    
    try:
        complaint_id = int(query.data.split("_")[2])
        complaint = db.get_complaint_by_id(complaint_id)
        
        if not complaint:
            await query.message.reply_text("❌ Жалоба не найдена!")
            return
        
        db.update_complaint_status(complaint_id, 'closed')
        
      
        try:
            await context.bot.send_message(
                complaint[1],
                f"📋 <b>Ваша жалоба #{complaint_id} обработана</b>\n\n"
                f"Жалоба была рассмотрена администрацией.",
                parse_mode=ParseMode.HTML
            )
        except:
            pass
        
        await query.message.reply_text(f"✅ Жалоба #{complaint_id} закрыта!")
    except Exception as e:
        logger.error(f"Ошибка при закрытии жалобы: {e}")
        await query.message.reply_text("❌ Произошла ошибка")
    
    try:
        await query.message.delete()
    except:
        pass

async def answer_complaint_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало ответа на жалобу"""
    query = update.callback_query
    await query.answer()
    
    admin_id = query.from_user.id
    if not is_admin(admin_id):
        return ConversationHandler.END
    
    try:
        complaint_id = int(query.data.split("_")[2])
        context.user_data['answer_complaint_id'] = complaint_id
        
        await query.message.reply_text("✏️ Введите ответ на жалобу:")
        return ANSWER_COMPLAINT
    except:
        await query.message.reply_text("❌ Ошибка при обработке запроса")
        return ConversationHandler.END

async def answer_complaint_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение ответа на жалобу"""
    response = update.message.text
    admin = update.effective_user
    complaint_id = context.user_data.get('answer_complaint_id')
    
    if not complaint_id:
        await update.message.reply_text(
            "❌ Ошибка: нет ID жалобы",
            reply_markup=get_admin_keyboard()
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    complaint = db.get_complaint_by_id(complaint_id)
    if complaint:
        db.update_complaint_status(complaint_id, 'closed', response)
        
    
        try:
            await context.bot.send_message(
                complaint[1],
                f"📋 <b>Ответ на вашу жалобу #{complaint_id}</b>\n\n"
                f"📝 {response}\n\n"
                f"👤 Ответил: @{admin.username or 'admin'}",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Не удалось отправить ответ пользователю: {e}")
    
    await update.message.reply_text(
        f"✅ Ответ на жалобу #{complaint_id} отправлен!",
        reply_markup=get_admin_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END

# Админские функции для тикетов
async def show_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать все тикеты"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав!")
        return
    
    tickets = db.get_open_tickets()
    if not tickets:
        await update.message.reply_text("📭 Нет открытых тикетов.")
        return
    
    kb = get_tickets_list_keyboard(tickets)
    if kb:
        await update.message.reply_text(
            "🎫 <b>Открытые тикеты:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb
        )

async def view_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр конкретного тикета"""
    query = update.callback_query
    await query.answer()
    
    try:
        ticket_id = int(query.data.split("_")[2])
        ticket = db.get_ticket_by_id(ticket_id)
        
        if not ticket:
            await query.message.reply_text("❌ Тикет не найден!")
            return
        
        text = format_ticket(ticket)
        
        await query.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_ticket_view_keyboard(ticket_id)
        )
    except Exception as e:
        logger.error(f"Ошибка при просмотре тикета: {e}")
        await query.message.reply_text("❌ Произошла ошибка при загрузке тикета")
    
    try:
        await query.message.delete()
    except:
        pass

async def close_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Закрыть тикет"""
    query = update.callback_query
    await query.answer()
    
    admin_id = query.from_user.id
    if not is_admin(admin_id):
        return
    
    try:
        ticket_id = int(query.data.split("_")[2])
        ticket = db.get_ticket_by_id(ticket_id)
        
        if not ticket:
            await query.message.reply_text("❌ Тикет не найден!")
            return
        
        db.update_ticket_status(ticket_id, 'closed')
        

        try:
            await context.bot.send_message(
                ticket[1],
                f"🎫 <b>Ваш тикет #{ticket_id} закрыт</b>\n\n"
                f"Администрация рассмотрела ваш вопрос.",
                parse_mode=ParseMode.HTML
            )
        except:
            pass
        
        await query.message.reply_text(f"✅ Тикет #{ticket_id} закрыт!")
    except Exception as e:
        logger.error(f"Ошибка при закрытии тикета: {e}")
        await query.message.reply_text("❌ Произошла ошибка")
    
    try:
        await query.message.delete()
    except:
        pass

async def answer_ticket_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало ответа на тикет"""
    query = update.callback_query
    await query.answer()
    
    admin_id = query.from_user.id
    if not is_admin(admin_id):
        return ConversationHandler.END
    
    try:
        ticket_id = int(query.data.split("_")[2])
        context.user_data['answer_ticket_id'] = ticket_id
        
        await query.message.reply_text("✏️ Введите ответ на тикет:")
        return ANSWER_TICKET
    except:
        await query.message.reply_text("❌ Ошибка при обработке запроса")
        return ConversationHandler.END

async def answer_ticket_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение ответа на тикет"""
    response = update.message.text
    admin = update.effective_user
    ticket_id = context.user_data.get('answer_ticket_id')
    
    if not ticket_id:
        await update.message.reply_text(
            "❌ Ошибка: нет ID тикета",
            reply_markup=get_admin_keyboard()
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    ticket = db.get_ticket_by_id(ticket_id)
    if ticket:
        db.update_ticket_status(ticket_id, 'closed', response)
        
      
        try:
            await context.bot.send_message(
                ticket[1],
                f"🎫 <b>Ответ на ваш тикет #{ticket_id}</b>\n\n"
                f"📝 {response}\n\n"
                f"👤 Ответил: @{admin.username or 'admin'}",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Не удалось отправить ответ пользователю: {e}")
    
    await update.message.reply_text(
        f"✅ Ответ на тикет #{ticket_id} отправлен!",
        reply_markup=get_admin_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END

async def show_applications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав!")
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
    
    try:
        app_id = int(query.data.split("_")[1])
        app = db.get_application_by_id(app_id)
        
        if not app:
            await query.message.reply_text("❌ Заявка не найдена!")
            return
        
        text = format_application(app)
        
        if len(app) > 4 and app[4]:
            await query.message.reply_photo(
                photo=app[4],
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=get_app_view_keyboard(app_id)
            )
        else:
            await query.message.reply_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=get_app_view_keyboard(app_id)
            )
    except Exception as e:
        logger.error(f"Ошибка при просмотре заявки: {e}")
        await query.message.reply_text("❌ Произошла ошибка при загрузке заявки")
    
    try:
        await query.message.delete()
    except:
        pass

async def accept_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    admin_id = query.from_user.id
    if not is_admin(admin_id):
        return
    
    try:
        app_id = int(query.data.split("_")[1])
        app = db.get_application_by_id(app_id)
        
        if not app:
            await query.message.reply_text("❌ Заявка не найдена!")
            return
        
        db.update_application_status(app_id, 'accepted', admin_id)
        
        try:
            await context.bot.send_message(
                app[1],
                f"✅ <b>Ваша заявка #{app_id} ПРИНЯТА!</b>\n\n"
                f"Добро пожаловать в Aricto Fame!",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя {app[1]}: {e}")
        
        await query.message.reply_text(f"✅ Заявка #{app_id} принята!")
    except Exception as e:
        logger.error(f"Ошибка при принятии заявки: {e}")
        await query.message.reply_text("❌ Произошла ошибка")
    
    try:
        await query.message.delete()
    except:
        pass

async def reject_app_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    admin_id = query.from_user.id
    if not is_admin(admin_id):
        return ConversationHandler.END
    
    try:
        app_id = int(query.data.split("_")[1])
        context.user_data['reject_app_id'] = app_id
        
        await query.message.reply_text("❌ Введите причину отклонения заявки:")
        return REJECT_REASON
    except:
        await query.message.reply_text("❌ Ошибка при обработке запроса")
        return ConversationHandler.END

async def reject_app_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text
    admin_id = update.effective_user.id
    app_id = context.user_data.get('reject_app_id')
    
    if not app_id:
        await update.message.reply_text("❌ Ошибка: нет ID заявки", reply_markup=get_admin_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    
    app = db.get_application_by_id(app_id)
    if app:
        db.update_application_status(app_id, 'rejected', admin_id, reason)
        
        try:
            await context.bot.send_message(
                app[1],
                f"❌ <b>Ваша заявка #{app_id} ОТКЛОНЕНА</b>\n\n"
                f"📝 Причина: {reason}",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя: {e}")
    
    await update.message.reply_text(f"❌ Заявка #{app_id} отклонена.\nПричина: {reason}", 
                                   reply_markup=get_admin_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

async def add_note_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        app_id = int(query.data.split("_")[1])
        context.user_data['note_app_id'] = app_id
        
        await query.message.reply_text("📝 Введите текст заметки:")
        return ADD_NOTE
    except:
        await query.message.reply_text("❌ Ошибка при обработке запроса")
        return ConversationHandler.END

async def add_note_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note_text = update.message.text
    admin = update.effective_user
    app_id = context.user_data.get('note_app_id')
    
    if app_id:
        db.add_admin_note(app_id, admin.id, admin.username or "Без username", note_text)
        await update.message.reply_text(f"✅ Заметка добавлена к заявке #{app_id}", reply_markup=get_admin_keyboard())
    
    context.user_data.clear()
    return ConversationHandler.END

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    
    history = db.get_history(30)
    if not history:
        await update.message.reply_text("📭 История пуста.")
        return
    
    text = "📜 <b>ИСТОРИЯ ЗАЯВОК (последние 30):</b>\n\n"
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
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав!")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📨 <b>РАССЫЛКА СООБЩЕНИЙ</b>\n\n"
        "Введите текст, который хотите отправить всем пользователям бота\n"
        "Для отмены: /cancel",
        parse_mode=ParseMode.HTML
    )
    return BROADCAST_MESSAGE

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    
    if message_text == '/cancel':
        context.user_data.clear()
        await update.message.reply_text("❌ Рассылка отменена", reply_markup=get_admin_keyboard())
        return ConversationHandler.END
    
    users = db.get_all_users()
    
    if not users:
        await update.message.reply_text("❌ Нет пользователей для рассылки", reply_markup=get_admin_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    
    await update.message.reply_text(f"📨 Начинаю рассылку на {len(users)} пользователей...")
    
    success = 0
    failed = 0
    
    for user_id in users:
        try:
            await context.bot.send_message(
                user_id,
                f"📢 <b>Сообщение от администрации:</b>\n\n{message_text}",
                parse_mode=ParseMode.HTML
            )
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
            failed += 1
    
    await update.message.reply_text(
        f"📊 <b>Рассылка завершена!</b>\n\n"
        f"✅ Успешно: {success}\n"
        f"❌ Не удалось: {failed}",
        parse_mode=ParseMode.HTML,
        reply_markup=get_admin_keyboard()
    )
    
    context.user_data.clear()
    return ConversationHandler.END

async def complaint_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("⚠️ Укажите username или ссылку на нарушителя:")
    return COMPLAINT_USER

async def complaint_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['complaint_on'] = update.message.text
    await update.message.reply_text("📝 Опишите причину жалобы:")
    return COMPLAINT_REASON

async def complaint_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['complaint_reason'] = update.message.text
    await update.message.reply_text("📎 Прикрепите доказательства (текст, фото или видео):")
    return COMPLAINT_EVIDENCE

async def complaint_evidence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    if 'complaint_on' not in context.user_data or 'complaint_reason' not in context.user_data:
        await update.message.reply_text("❌ Ошибка: данные жалобы потеряны. Начните заново.", 
                                       reply_markup=get_user_keyboard())
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
        complaint_id = db.add_complaint(
            user_id,
            username,
            context.user_data['complaint_on'],
            context.user_data['complaint_reason'],
            evidence
        )
        
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"⚠️ <b>НОВАЯ ЖАЛОБА #{complaint_id}</b>\n"
                    f"👤 От: @{username or 'нет'} (ID: {user_id})\n"
                    f"👥 Нарушитель: {context.user_data['complaint_on']}\n"
                    f"📝 Причина: {context.user_data['complaint_reason']}\n"
                    f"📎 Доказательства: {evidence[:100]}...",
                    parse_mode=ParseMode.HTML
                )
            except:
                pass
        
        kb = get_admin_keyboard() if is_admin(user_id) else get_user_keyboard()
        await update.message.reply_text(f"✅ Жалоба #{complaint_id} отправлена администрации!", reply_markup=kb)
    
    except Exception as e:
        logger.error(f"Ошибка при сохранении жалобы: {e}")
        kb = get_admin_keyboard() if is_admin(user_id) else get_user_keyboard()
        await update.message.reply_text("❌ Произошла ошибка при отправке жалобы", reply_markup=kb)
    
    context.user_data.clear()
    return ConversationHandler.END

async def ticket_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🎫 Задайте ваш вопрос администрации:")
    return TICKET_QUESTION

async def ticket_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = update.message.text
    user = update.effective_user
    
    ticket_id = db.add_ticket(user.id, user.username, question)
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"🎫 <b>НОВЫЙ ТИКЕТ #{ticket_id}</b>\n"
                f"👤 От: @{user.username or 'нет'} (ID: {user.id})\n"
                f"❓ Вопрос: {question}",
                parse_mode=ParseMode.HTML
            )
        except:
            pass
    
    kb = get_admin_keyboard() if is_admin(user.id) else get_user_keyboard()
    await update.message.reply_text(f"✅ Ваш тикет #{ticket_id} отправлен! Администрация скоро ответит.", reply_markup=kb)
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.clear()
    
    kb = get_admin_keyboard() if is_admin(user_id) else get_user_keyboard()
    await update.message.reply_text("❌ Действие отменено.", reply_markup=kb)
    return ConversationHandler.END

def main():
    print("🚀 БОТ ЗАПУСКАЕТСЯ...")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_error_handler(error_handler)
    

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel))
    

    application.add_handler(MessageHandler(filters.Regex('^🌐 Перейти на сайт$'), site_link))
    application.add_handler(MessageHandler(filters.Regex('^🎯 ArictoSession$'), aricto_session))
    application.add_handler(MessageHandler(filters.Regex('^📋 Правила$'), rules))
    application.add_handler(MessageHandler(filters.Regex('^📊 Заявки$'), show_applications))
    application.add_handler(MessageHandler(filters.Regex('^📜 История$'), show_history))
    application.add_handler(MessageHandler(filters.Regex('^📋 Жалобы$'), show_complaints))
    application.add_handler(MessageHandler(filters.Regex('^🎫 Тикеты$'), show_tickets))
    
  
    app_conversation = ConversationHandler(
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
    )
    application.add_handler(app_conversation)
    
 
    complaint_conversation = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^⚠️ Пожаловаться$'), complaint_start)],
        states={
            COMPLAINT_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_user)],
            COMPLAINT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_reason)],
            COMPLAINT_EVIDENCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_evidence),
                MessageHandler(filters.PHOTO, complaint_evidence),
                MessageHandler(filters.VIDEO, complaint_evidence),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(complaint_conversation)
    
 
    ticket_conversation = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^🎫 Тикет$'), ticket_start)],
        states={
            TICKET_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ticket_finish)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(ticket_conversation)
    
    
    note_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_note_start, pattern="^note_")],
        states={
            ADD_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_note_finish)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(note_conversation)
    
   
    reject_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(reject_app_start, pattern="^reject_")],
        states={
            REJECT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, reject_app_finish)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(reject_conversation)
    

    answer_complaint_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(answer_complaint_start, pattern="^answer_complaint_")],
        states={
            ANSWER_COMPLAINT: [MessageHandler(filters.TEXT & ~filters.COMMAND, answer_complaint_finish)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(answer_complaint_conversation)
    
  
    answer_ticket_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(answer_ticket_start, pattern="^answer_ticket_")],
        states={
            ANSWER_TICKET: [MessageHandler(filters.TEXT & ~filters.COMMAND, answer_ticket_finish)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(answer_ticket_conversation)
    

    broadcast_conversation = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^📨 Рассылка$'), broadcast_start)],
        states={
            BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(broadcast_conversation)
    
  
    application.add_handler(CallbackQueryHandler(view_application, pattern="^view_[0-9]+$"))
    application.add_handler(CallbackQueryHandler(accept_app, pattern="^accept_"))
    

    application.add_handler(CallbackQueryHandler(view_complaint, pattern="^view_complaint_"))
    application.add_handler(CallbackQueryHandler(close_complaint, pattern="^close_complaint_"))
    

    application.add_handler(CallbackQueryHandler(view_ticket, pattern="^view_ticket_"))
    application.add_handler(CallbackQueryHandler(close_ticket, pattern="^close_ticket_"))
    

    if os.environ.get('RAILWAY_ENVIRONMENT'):
        PORT = int(os.environ.get('PORT', 8080))
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=f"https://{os.environ.get('RAILWAY_PUBLIC_DOMAIN')}"
        )
        print(f"✅ Бот запущен на Railway")
    else:
        print("✅ Бот запущен локально")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
