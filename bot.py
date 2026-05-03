import sqlite3
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
from telegram.constants import ParseMode

BOT_TOKEN = "8226025643:AAHyrVkbV8wFum7tLbAxvhtRq5Sh_-VkH-M"
OWNER_IDS = [287265398, 7396843811]
ADMIN_IDS = [287265398, 7396843811]
MODER_IDS = []  # Добавлять ID модераторов сюда
CHANNEL_ID = -1003911175144
CHANNEL_LINK = "https://t.me/mirokfame"
SITE_LINK = "https://example.com"
CHECK_SUBSCRIPTION = True

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_file="bot_data.db"):
        self.db_file = db_file
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, username TEXT, nickname TEXT, avatar_file_id TEXT,
            project TEXT, chat_link TEXT, km_year TEXT, participated_before TEXT,
            reason TEXT, fame_method TEXT, acquaintances TEXT,
            status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_by INTEGER, reviewed_at TIMESTAMP, reject_reason TEXT,
            admin_notes TEXT DEFAULT '')''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER, user_id INTEGER, username TEXT, nickname TEXT,
            action TEXT, admin_id INTEGER, reason TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user_id INTEGER, on_user_info TEXT, reason TEXT, evidence TEXT,
            status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, username TEXT, question TEXT,
            status TEXT DEFAULT 'open', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS moders (
            user_id INTEGER PRIMARY KEY)''')
        
        conn.commit()
        conn.close()
    
    def add_user(self, user_id, username):
        conn = sqlite3.connect(self.db_file)
        conn.execute('INSERT OR REPLACE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
        conn.commit()
        conn.close()
    
    def get_all_users(self):
        conn = sqlite3.connect(self.db_file)
        users = [row[0] for row in conn.execute('SELECT DISTINCT user_id FROM users')]
        conn.close()
        return users
    
    def get_statistics(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        stats = {
            'total_users': cursor.execute('SELECT COUNT(*) FROM users').fetchone()[0],
            'total_apps': cursor.execute('SELECT COUNT(*) FROM applications').fetchone()[0],
            'pending_apps': cursor.execute('SELECT COUNT(*) FROM applications WHERE status="pending"').fetchone()[0],
            'accepted_apps': cursor.execute('SELECT COUNT(*) FROM applications WHERE status="accepted"').fetchone()[0],
            'rejected_apps': cursor.execute('SELECT COUNT(*) FROM applications WHERE status="rejected"').fetchone()[0],
            'total_complaints': cursor.execute('SELECT COUNT(*) FROM complaints').fetchone()[0],
            'total_tickets': cursor.execute('SELECT COUNT(*) FROM tickets').fetchone()[0],
        }
        conn.close()
        return stats
    
    def add_application(self, user_id, username, nickname, avatar_file_id, project, chat_link, km_year, participated_before, reason, fame_method, acquaintances):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO applications 
            (user_id, username, nickname, avatar_file_id, project, chat_link, km_year, participated_before, reason, fame_method, acquaintances)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (user_id, username, nickname, avatar_file_id, project, chat_link, km_year, participated_before, reason, fame_method, acquaintances))
        app_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return app_id
    
    def get_pending_applications(self):
        conn = sqlite3.connect(self.db_file)
        apps = conn.execute('SELECT id, user_id, username, nickname, created_at FROM applications WHERE status="pending" ORDER BY created_at DESC').fetchall()
        conn.close()
        return apps
    
    def get_application_by_id(self, app_id):
        conn = sqlite3.connect(self.db_file)
        app = conn.execute('SELECT * FROM applications WHERE id=?', (app_id,)).fetchone()
        conn.close()
        return app
    
    def update_application_status(self, app_id, status, admin_id, reject_reason=None):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        now = datetime.now()
        
        if status == 'rejected' and reject_reason:
            cursor.execute('UPDATE applications SET status=?, reviewed_by=?, reviewed_at=?, reject_reason=? WHERE id=?',
                          (status, admin_id, now, reject_reason, app_id))
        else:
            cursor.execute('UPDATE applications SET status=?, reviewed_by=?, reviewed_at=? WHERE id=?',
                          (status, admin_id, now, app_id))
        
        app = self.get_application_by_id(app_id)
        if app:
            cursor.execute('INSERT INTO history (application_id, user_id, username, nickname, action, admin_id, reason) VALUES (?,?,?,?,?,?,?)',
                          (app_id, app[1], app[2], app[3], 'accepted' if status == 'accepted' else 'rejected', admin_id, reject_reason))
        conn.commit()
        conn.close()
    
    def add_admin_note(self, app_id, admin_id, admin_username, note):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        current = cursor.execute('SELECT admin_notes FROM applications WHERE id=?', (app_id,)).fetchone()
        current_notes = current[0] if current and current[0] else ""
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
        new_note = f"\n📌 {timestamp} | {admin_username} (ID: {admin_id}):\n{note}\n{'─'*30}"
        cursor.execute('UPDATE applications SET admin_notes=? WHERE id=?', (current_notes + new_note, app_id))
        conn.commit()
        conn.close()
    
    def get_history(self, limit=30):
        conn = sqlite3.connect(self.db_file)
        history = conn.execute('SELECT * FROM history ORDER BY timestamp DESC LIMIT ?', (limit,)).fetchall()
        conn.close()
        return history
    
    def add_complaint(self, from_user_id, on_user_info, reason, evidence):
        conn = sqlite3.connect(self.db_file)
        conn.execute('INSERT INTO complaints (from_user_id, on_user_info, reason, evidence) VALUES (?,?,?,?)',
                    (from_user_id, on_user_info, reason, evidence))
        conn.commit()
        conn.close()
    
    def add_ticket(self, user_id, username, question):
        conn = sqlite3.connect(self.db_file)
        conn.execute('INSERT INTO tickets (user_id, username, question) VALUES (?,?,?)', (user_id, username, question))
        conn.commit()
        conn.close()
    
    def add_moder(self, user_id):
        conn = sqlite3.connect(self.db_file)
        conn.execute('INSERT OR IGNORE INTO moders VALUES (?)', (user_id,))
        conn.commit()
        conn.close()
        if user_id not in MODER_IDS:
            MODER_IDS.append(user_id)
    
    def get_moders(self):
        conn = sqlite3.connect(self.db_file)
        moders = [row[0] for row in conn.execute('SELECT user_id FROM moders')]
        conn.close()
        return moders

db = Database()

for moder_id in db.get_moders():
    if moder_id not in MODER_IDS:
        MODER_IDS.append(moder_id)

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
        ["📨 Рассылка", "📈 Статистика"]
    ], resize_keyboard=True)

def get_owner_keyboard():
    return ReplyKeyboardMarkup([
        ["🌐 Перейти на сайт", "📝 Отправить заявку"],
        ["🎯 ArictoSession"],
        ["📋 Правила", "⚠️ Пожаловаться"],
        ["🎫 Тикет"],
        ["📊 Заявки", "📜 История"],
        ["📨 Рассылка", "📈 Статистика"],
        ["👑 Модераторы"]
    ], resize_keyboard=True)

def get_app_view_keyboard(app_id, user_id):
    if user_id in OWNER_IDS or user_id in ADMIN_IDS:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ ПРИНЯТЬ", callback_data=f"accept_{app_id}"),
             InlineKeyboardButton("❌ ОТКЛОНИТЬ", callback_data=f"reject_{app_id}")],
            [InlineKeyboardButton("📝 ЗАМЕТКА", callback_data=f"note_{app_id}")]
        ])
    elif user_id in MODER_IDS:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 ЗАМЕТКА", callback_data=f"note_{app_id}")]
        ])
    else:
        return None

def get_apps_list_keyboard(apps):
    if not apps:
        return None
    keyboard = []
    for app in apps:
        keyboard.append([InlineKeyboardButton(f"👤 {app[3]} | #{app[0]}", callback_data=f"view_{app[0]}")])
    return InlineKeyboardMarkup(keyboard)

(APP_AVATAR, APP_NICKNAME, APP_PROJECT, APP_CHAT, APP_KM_YEAR, 
 APP_PARTICIPATED, APP_REASON, APP_FAME_METHOD, APP_ACQUAINTANCES) = range(9)
(COMPLAINT_USER, COMPLAINT_REASON, COMPLAINT_EVIDENCE) = range(9, 12)
(ADD_NOTE, REJECT_REASON, BROADCAST_MESSAGE, TICKET_QUESTION, ADD_MODER) = range(12, 17)

async def check_subscription(bot, user_id):
    if not CHECK_SUBSCRIPTION:
        return True
    try:
        chat_member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except:
        return False

def is_admin(user_id):
    return user_id in ADMIN_IDS or user_id in OWNER_IDS

def is_owner(user_id):
    return user_id in OWNER_IDS

def is_moder(user_id):
    return user_id in MODER_IDS

def is_staff(user_id):
    return is_admin(user_id) or is_moder(user_id)

def format_application(app):
    if not app:
        return "Не найдена"
    notes = app[17] if len(app) > 17 and app[17] else 'Нет'
    
    return f"""
📝 <b>ЗАЯВКА #{app[0]}</b>
👤 <b>Ник:</b> {app[3] or 'Нет'}
🆔 <b>ID:</b> <code>{app[1]}</code>
📌 <b>@:</b> @{app[2] if app[2] else 'нет'}
📁 <b>Проект:</b> {app[5]}
💬 <b>Чат:</b> {app[6] or 'Нет'}
📅 <b>Год в КМ:</b> {app[7]}
🎯 <b>Участие:</b> {app[8]}
💭 <b>Причина:</b> {app[9] or 'Нет'}
📈 <b>Фейм:</b> {app[10]}
👥 <b>Знакомства:</b> {app[11]}
📝 <b>Заметки:</b> {notes}
⏰ <b>Дата:</b> {app[13]}
"""

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db.add_user(user_id, update.effective_user.username)
    
    if CHECK_SUBSCRIPTION and not await check_subscription(context.bot, user_id):
        await update.message.reply_text(
            f"❌ <b>Подпишитесь на канал!</b>\n\n👉 <a href='{CHANNEL_LINK}'>ПОДПИСАТЬСЯ</a>",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
        return
    
    if is_owner(user_id):
        await update.message.reply_text("👑 Владелец", reply_markup=get_owner_keyboard())
    elif is_admin(user_id):
        await update.message.reply_text("🛡️ Админ", reply_markup=get_admin_keyboard())
    elif is_moder(user_id):
        await update.message.reply_text("🔍 Модератор", reply_markup=get_admin_keyboard())
    else:
        await update.message.reply_text("✨ Добро пожаловать!", reply_markup=get_user_keyboard())

async def site_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🌐 Сайт: {SITE_LINK}")

async def aricto_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 Напишите владельцу: @faymovy")

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📜 <b>ПРАВИЛА:</b>\n\n1. Честность\n2. Без оскорблений\n3. Без спама\n4. За скам - бан", parse_mode=ParseMode.HTML)

async def start_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db.add_user(user_id, update.effective_user.username)
    context.user_data.clear()
    
    if CHECK_SUBSCRIPTION and not await check_subscription(context.bot, user_id):
        await update.message.reply_text(
            f"❌ <b>Подпишитесь на канал!</b>\n\n👉 <a href='{CHANNEL_LINK}'>ПОДПИСАТЬСЯ</a>",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
        return ConversationHandler.END
    
    for app in db.get_pending_applications():
        if app[1] == user_id:
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
    await update.message.reply_text("🔗 Ссылка на проект:")
    return APP_PROJECT

async def app_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['project'] = update.message.text
    await update.message.reply_text("💬 Ссылка на чат (или '-'):")
    return APP_CHAT

async def app_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['chat_link'] = None if update.message.text == '-' else update.message.text
    await update.message.reply_text("📅 Год в КМ:")
    return APP_KM_YEAR

async def app_km_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['km_year'] = update.message.text
    await update.message.reply_text("🎯 Участие в ВК/ДС КМ?")
    return APP_PARTICIPATED

async def app_participated(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['participated'] = update.message.text
    await update.message.reply_text("💭 Почему к нам? (или '-'):")
    return APP_REASON

async def app_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['reason'] = None if update.message.text == '-' else update.message.text
    await update.message.reply_text("📈 Как поднимали фейм?")
    return APP_FAME_METHOD

async def app_fame_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['fame_method'] = update.message.text
    await update.message.reply_text("👥 С кем знакомы?")
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
    
    kb = get_owner_keyboard() if is_owner(user.id) else get_admin_keyboard() if is_admin(user.id) or is_moder(user.id) else get_user_keyboard()
    
    if app_id:
        await update.message.reply_text(f"✅ <b>Заявка #{app_id} отправлена!</b>", parse_mode=ParseMode.HTML, reply_markup=kb)
        for admin_id in ADMIN_IDS + MODER_IDS:
            try:
                await context.bot.send_message(admin_id, f"🔔 Новая заявка #{app_id} от {data['nickname']}")
            except:
                pass
    
    context.user_data.clear()
    return ConversationHandler.END

async def show_applications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_staff(update.effective_user.id):
        return
    
    apps = db.get_pending_applications()
    if not apps:
        await update.message.reply_text("📭 Нет активных заявок.")
        return
    
    kb = get_apps_list_keyboard(apps)
    if kb:
        await update.message.reply_text("📊 Активные заявки:", reply_markup=kb)

async def view_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not is_staff(user_id):
        return
    
    app_id = int(query.data.split("_")[1])
    app = db.get_application_by_id(app_id)
    
    if not app:
        await query.message.reply_text("❌ Заявка не найдена!")
        return
    
    text = format_application(app)
    kb = get_app_view_keyboard(app_id, user_id)
    
    try:
        if app[4]:
            await query.message.reply_photo(photo=app[4], caption=text, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    except:
        await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

async def accept_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.message.reply_text("⛔ Только админы могут принимать заявки!")
        return
    
    app_id = int(query.data.split("_")[1])
    app = db.get_application_by_id(app_id)
    
    if not app:
        return
    
    db.update_application_status(app_id, 'accepted', query.from_user.id)
    
    try:
        await context.bot.send_message(app[1], f"✅ Заявка #{app_id} ПРИНЯТА!")
    except:
        pass
    
    await query.message.edit_text(f"✅ Заявка #{app_id} принята!")

async def reject_app_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.message.reply_text("⛔ Только админы могут отклонять заявки!")
        return ConversationHandler.END
    
    context.user_data['reject_app_id'] = int(query.data.split("_")[1])
    await query.message.reply_text("❌ Причина отклонения:")
    return REJECT_REASON

async def reject_app_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text
    app_id = context.user_data.get('reject_app_id')
    
    if not app_id:
        return ConversationHandler.END
    
    app = db.get_application_by_id(app_id)
    if app:
        db.update_application_status(app_id, 'rejected', update.effective_user.id, reason)
        try:
            await context.bot.send_message(app[1], f"❌ Заявка #{app_id} отклонена\n📝 {reason}")
        except:
            pass
    
    await update.message.reply_text(f"❌ Отклонено", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

async def add_note_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_staff(query.from_user.id):
        return ConversationHandler.END
    
    context.user_data['note_app_id'] = int(query.data.split("_")[1])
    await query.message.reply_text("📝 Текст заметки:")
    return ADD_NOTE

async def add_note_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note = update.message.text
    admin = update.effective_user
    app_id = context.user_data.get('note_app_id')
    
    if app_id:
        db.add_admin_note(app_id, admin.id, admin.username or "NoName", note)
        kb = get_owner_keyboard() if is_owner(admin.id) else get_admin_keyboard()
        await update.message.reply_text(f"✅ Заметка добавлена к #{app_id}", reply_markup=kb)
    
    return ConversationHandler.END

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_staff(update.effective_user.id):
        return
    
    history = db.get_history(30)
    if not history:
        await update.message.reply_text("📭 История пуста.")
        return
    
    text = "📜 <b>ИСТОРИЯ:</b>\n\n"
    for h in history:
        emoji = "✅" if h[5] == 'accepted' else "❌"
        text += f"{emoji} #{h[1]} | {h[4]} | {h[8]}\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_staff(update.effective_user.id):
        return
    
    s = db.get_statistics()
    text = f"""
📈 <b>СТАТИСТИКА</b>
👥 Пользователей: {s['total_users']}
📝 Заявок: {s['total_apps']} (ожидают: {s['pending_apps']})
✅ Принято: {s['accepted_apps']}
❌ Отклонено: {s['rejected_apps']}
⚠️ Жалоб: {s['total_complaints']}
🎫 Тикетов: {s['total_tickets']}
"""
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    
    await update.message.reply_text("📨 Текст рассылки (/cancel - отмена):")
    return BROADCAST_MESSAGE

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    
    if msg == '/cancel':
        await update.message.reply_text("❌ Отменено", reply_markup=get_admin_keyboard())
        return ConversationHandler.END
    
    users = db.get_all_users()
    success = 0
    
    for uid in users:
        try:
            await context.bot.send_message(uid, f"📢 {msg}")
            success += 1
        except:
            pass
    
    await update.message.reply_text(f"✅ Отправлено: {success}/{len(users)}", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

async def manage_moders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    
    moders = db.get_moders()
    text = "👑 <b>МОДЕРАТОРЫ:</b>\n\n"
    for m in moders:
        text += f"• {m}\n"
    text += "\nОтправьте ID для добавления модератора:"
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return ADD_MODER

async def add_moder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_moder = int(update.message.text)
        db.add_moder(new_moder)
        await update.message.reply_text(f"✅ Модератор {new_moder} добавлен!", reply_markup=get_owner_keyboard())
    except:
        await update.message.reply_text("❌ Неверный ID!", reply_markup=get_owner_keyboard())
    
    return ConversationHandler.END

async def complaint_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if CHECK_SUBSCRIPTION and not await check_subscription(context.bot, update.effective_user.id):
        await update.message.reply_text(f"❌ Подпишитесь на канал: {CHANNEL_LINK}")
        return ConversationHandler.END
    
    context.user_data.clear()
    await update.message.reply_text("⚠️ Username нарушителя:")
    return COMPLAINT_USER

async def complaint_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['complaint_on'] = update.message.text
    await update.message.reply_text("📝 Причина:")
    return COMPLAINT_REASON

async def complaint_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['complaint_reason'] = update.message.text
    await update.message.reply_text("📎 Доказательства:")
    return COMPLAINT_EVIDENCE

async def complaint_evidence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if 'complaint_on' not in context.user_data:
        return ConversationHandler.END
    
    evidence = "Не предоставлены"
    if update.message.text:
        evidence = update.message.text
    elif update.message.photo:
        evidence = f"Фото"
    elif update.message.video:
        evidence = f"Видео"
    
    db.add_complaint(user_id, context.user_data['complaint_on'], context.user_data['complaint_reason'], evidence)
    
    for uid in ADMIN_IDS + MODER_IDS:
        try:
            await context.bot.send_message(uid, f"⚠️ Жалоба на {context.user_data['complaint_on']}")
        except:
            pass
    
    kb = get_owner_keyboard() if is_owner(user_id) else get_admin_keyboard() if is_staff(user_id) else get_user_keyboard()
    await update.message.reply_text("✅ Жалоба отправлена!", reply_markup=kb)
    return ConversationHandler.END

async def ticket_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if CHECK_SUBSCRIPTION and not await check_subscription(context.bot, update.effective_user.id):
        await update.message.reply_text(f"❌ Подпишитесь на канал: {CHANNEL_LINK}")
        return ConversationHandler.END
    
    context.user_data.clear()
    await update.message.reply_text("🎫 Ваш вопрос:")
    return TICKET_QUESTION

async def ticket_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_ticket(user.id, user.username, update.message.text)
    
    for uid in ADMIN_IDS + MODER_IDS:
        try:
            await context.bot.send_message(uid, f"🎫 Тикет от @{user.username or user.id}")
        except:
            pass
    
    kb = get_owner_keyboard() if is_owner(user.id) else get_admin_keyboard() if is_staff(user.id) else get_user_keyboard()
    await update.message.reply_text("✅ Отправлено!", reply_markup=kb)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.clear()
    
    if is_owner(user_id):
        kb = get_owner_keyboard()
    elif is_staff(user_id):
        kb = get_admin_keyboard()
    else:
        kb = get_user_keyboard()
    
    await update.message.reply_text("❌ Отменено.", reply_markup=kb)
    return ConversationHandler.END

def main():
    print("🚀 БОТ ЗАПУСКАЕТСЯ...")
    
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_error_handler(error_handler)
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel))
    
    application.add_handler(CallbackQueryHandler(view_application, pattern="^view_"))
    application.add_handler(CallbackQueryHandler(accept_app, pattern="^accept_"))
    
    application.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(add_note_start, pattern="^note_")],
        states={ADD_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_note_finish)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    application.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(reject_app_start, pattern="^reject_")],
        states={REJECT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, reject_app_finish)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    application.add_handler(ConversationHandler(
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
    ))
    
    application.add_handler(ConversationHandler(
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
    ))
    
    application.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^🎫 Тикет$'), ticket_start)],
        states={TICKET_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ticket_finish)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    application.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^📨 Рассылка$'), broadcast_start)],
        states={BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    application.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^👑 Модераторы$'), manage_moders)],
        states={ADD_MODER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_moder)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    application.add_handler(MessageHandler(filters.Regex('^🌐 Перейти на сайт$'), site_link))
    application.add_handler(MessageHandler(filters.Regex('^🎯 ArictoSession$'), aricto_session))
    application.add_handler(MessageHandler(filters.Regex('^📋 Правила$'), rules))
    application.add_handler(MessageHandler(filters.Regex('^📊 Заявки$'), show_applications))
    application.add_handler(MessageHandler(filters.Regex('^📜 История$'), show_history))
    application.add_handler(MessageHandler(filters.Regex('^📈 Статистика$'), show_statistics))
    
    print("✅ БОТ ЗАПУЩЕН!")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
