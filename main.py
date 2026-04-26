import sqlite3
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
from telegram.constants import ParseMode

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = "8226025643:AAHyrVkbV8wFum7tLbAxvhtRq5Sh_-VkH-M"
OWNER_ID = 287265398
CHANNEL_ID = -1003911175144
CHANNEL_LINK = "https://t.me/mirokfame"
CHECK_SUBSCRIPTION = True
ADMINS = [287265398]
CATEGORIES = ['Медийка', 'Высокий фейм', 'Средний фейм', 'Низкий фейм', ]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== БАЗА ДАННЫХ ====================
class Database:
    def __init__(self, db_file="fame_list.db"):
        self.db_file = db_file
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            nickname TEXT,
            avatar_file_id TEXT,
            category TEXT,
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
            admin_note TEXT
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER,
            user_id INTEGER,
            username TEXT,
            nickname TEXT,
            category TEXT,
            accepted_by INTEGER,
            accepted_at TIMESTAMP
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user_id INTEGER,
            on_user_id INTEGER,
            on_username TEXT,
            reason TEXT,
            evidence TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS admins_table (
            user_id INTEGER PRIMARY KEY
        )''')
        conn.commit()
        conn.close()
        logger.info("Database initialized")
    
    def add_application(self, user_id, username, nickname, avatar_file_id, category, 
                        project, chat_link, km_year, participated_before, 
                        reason, fame_method, acquaintances):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO applications 
            (user_id, username, nickname, avatar_file_id, category, project, chat_link, 
             km_year, participated_before, reason, fame_method, acquaintances)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (user_id, username, nickname, avatar_file_id, category, project, chat_link,
             km_year, participated_before, reason, fame_method, acquaintances))
        app_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return app_id
    
    def get_pending_applications(self):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('SELECT id, user_id, username, nickname, category, created_at FROM applications WHERE status = "pending" ORDER BY created_at DESC')
        apps = cursor.fetchall()
        conn.close()
        return apps
    
    def get_application_by_id(self, app_id):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM applications WHERE id = ?', (app_id,))
        app = cursor.fetchone()
        conn.close()
        return app
    
    def update_application_status(self, app_id, status, admin_id, note=None):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('UPDATE applications SET status = ?, reviewed_by = ?, reviewed_at = ?, admin_note = ? WHERE id = ?',
                      (status, admin_id, datetime.now(), note, app_id))
        if status == 'accepted':
            app = self.get_application_by_id(app_id)
            if app:
                cursor.execute('INSERT INTO history (application_id, user_id, username, nickname, category, accepted_by, accepted_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                              (app_id, app[1], app[2], app[3], app[5], admin_id, datetime.now()))
        conn.commit()
        conn.close()
    
    def update_application_note(self, app_id, note):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('UPDATE applications SET admin_note = ? WHERE id = ?', (note, app_id))
        conn.commit()
        conn.close()
    
    def get_history_applications(self):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('SELECT id, user_id, username, nickname, category, accepted_by, accepted_at FROM history ORDER BY accepted_at DESC')
        history = cursor.fetchall()
        conn.close()
        return history
    
    def add_complaint(self, from_user_id, on_user_id, on_username, reason, evidence):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO complaints (from_user_id, on_user_id, on_username, reason, evidence) VALUES (?, ?, ?, ?, ?)',
                      (from_user_id, on_user_id, on_username, reason, evidence))
        conn.commit()
        conn.close()
    
    def add_admin(self, admin_id):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO admins_table VALUES (?)', (admin_id,))
        conn.commit()
        conn.close()
    
    def get_all_admins(self):
        conn = sqlite3.connect(self.db_file, timeout=10)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM admins_table')
        admins = [row[0] for row in cursor.fetchall()]
        conn.close()
        return admins

db = Database()

# ==================== КЛАВИАТУРЫ ====================
def get_user_keyboard():
    return ReplyKeyboardMarkup([
        ["📝 Отправить заявку"],
        ["📋 Правила", "⚠️ Пожаловаться"],
        ["👥 Модерация"]
    ], resize_keyboard=True)

def get_admin_keyboard():
    return ReplyKeyboardMarkup([
        ["📝 Отправить заявку"],
        ["📋 Правила", "⚠️ Пожаловаться"],
        ["👥 Модерация"],
        ["📊 Заявки", "📜 История"]
    ], resize_keyboard=True)

def get_owner_keyboard():
    return ReplyKeyboardMarkup([
        ["📝 Отправить заявку"],
        ["📋 Правила", "⚠️ Пожаловаться"],
        ["👥 Модерация"],
        ["📊 Заявки", "📜 История"],
        ["👑 Управление админами"]
    ], resize_keyboard=True)

def get_categories_keyboard():
    keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in CATEGORIES]
    return InlineKeyboardMarkup(keyboard)

def get_app_view_keyboard(app_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ ПРИНЯТЬ", callback_data=f"accept_{app_id}"),
         InlineKeyboardButton("❌ ОТКЛОНИТЬ", callback_data=f"reject_{app_id}")],
        [InlineKeyboardButton("📝 ДОПОЛНИТЬ", callback_data=f"note_{app_id}")]
    ])

def get_apps_list_keyboard(apps):
    if not apps:
        return None
    keyboard = []
    for app in apps:
        keyboard.append([InlineKeyboardButton(f"👤 {app[3]} | #{app[0]}", callback_data=f"view_{app[0]}")])
    return InlineKeyboardMarkup(keyboard)

# ==================== СОСТОЯНИЯ ====================
APP_AVATAR, APP_NICKNAME, APP_CATEGORY, APP_PROJECT, APP_CHAT, APP_KM_YEAR, APP_PARTICIPATED, APP_REASON, APP_FAME_METHOD, APP_ACQUAINTANCES = range(10)
COMPLAINT_USER, COMPLAINT_REASON, COMPLAINT_EVIDENCE = range(10, 13)
ADD_NOTE_STATE = range(13, 14)
ADD_ADMIN_STATE = range(14, 15)

# ==================== УТИЛИТЫ ====================
async def check_subscription(bot: Bot, user_id: int) -> bool:
    if not CHECK_SUBSCRIPTION:
        return True
    try:
        chat_member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except:
        return False

def format_application(app):
    note_text = app[16] if len(app) > 16 and app[16] else 'Нет'
    return f"""
📝 <b>ЗАЯВКА #{app[0]}</b>

👤 <b>Никнейм:</b> {app[3] or 'Не указан'}
🆔 <b>User ID:</b> <code>{app[1]}</code>
📌 <b>Юзернейм:</b> @{app[2] if app[2] else 'нет'}
🏷 <b>Категория:</b> {app[5]}

📁 <b>Проект:</b> {app[6]}
💬 <b>Чат:</b> {app[7] or 'Пропущено'}

📅 <b>Год в КМ:</b> {app[8]}
🎯 <b>Участие в ВК/ДС КМ:</b> {app[9]}

💭 <b>Почему хочет попасть:</b> {app[10] or 'Не указано'}
📈 <b>Как поднимал фейм:</b> {app[11]}
👥 <b>Знакомства:</b> {app[12]}

📝 <b>Заметка админа:</b> {note_text}

⏰ <b>Дата:</b> {app[13]}
"""

# ==================== ОСНОВНЫЕ ОБРАБОТЧИКИ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.clear()
    
    if not await check_subscription(context.bot, user_id):
        await update.message.reply_text(
            f"❌ <b>Подпишись на канал!</b>\n\n👉 <a href='{CHANNEL_LINK}'>ПОДПИСАТЬСЯ</a>",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
        return
    
    if user_id == OWNER_ID:
        await update.message.reply_text("👑 Владелец", reply_markup=get_owner_keyboard())
    elif user_id in ADMINS:
        await update.message.reply_text("🛡️ Админ", reply_markup=get_admin_keyboard())
    else:
        await update.message.reply_text("✨ Добро пожаловать!", reply_markup=get_user_keyboard())

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📜 ПРАВИЛА:\n1. Заполняй анкету честно\n2. Без оскорблений\n3. Без спама\n4. За скам - бан")

async def moderation_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👥 Модераторы проверяют заявки 48-104 часов")

# ==================== ПОДАЧА ЗАЯВКИ ====================
async def start_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    for app in db.get_pending_applications():
        if app[1] == user_id:
            await update.message.reply_text("❌ У вас уже есть активная заявка!")
            return
    await update.message.reply_text("📝 Отправьте аву которую хотите видеть на сайте:")
    return APP_AVATAR

async def app_avatar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Отправьте аву которую хотите видеть на сайте!")
        return APP_AVATAR
    context.user_data['avatar'] = update.message.photo[-1].file_id
    await update.message.reply_text("✅ Введите ник:")
    return APP_NICKNAME

async def app_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['nickname'] = update.message.text
    await update.message.reply_text("✅ Выберите категорию:", reply_markup=get_categories_keyboard())
    return APP_CATEGORY

async def app_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['category'] = query.data.replace("cat_", "")
    await query.edit_message_text("✅ Введите ссылку на ваш проект:")
    return APP_PROJECT

async def app_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['project'] = update.message.text
    await update.message.reply_text("✅ Ссылка на ваш чат (или '-'):")
    return APP_CHAT

async def app_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data['chat'] = None if text == '-' else text
    await update.message.reply_text("✅ с какого года вы в КМ?")
    return APP_KM_YEAR

async def app_km_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['km_year'] = update.message.text
    await update.message.reply_text("✅ Участвовали в ВК или ДС КМ?")
    return APP_PARTICIPATED

async def app_participated(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['participated'] = update.message.text
    await update.message.reply_text("✅ Почему хотите попасть к нам? (или '-'):")
    return APP_REASON

async def app_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data['reason'] = None if text == '-' else text
    await update.message.reply_text("✅ Как поднимали фейм?")
    return APP_FAME_METHOD

async def app_fame_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['fame_method'] = update.message.text
    await update.message.reply_text("✅ С кем знакомы и кто может из них подтвердит?")
    return APP_ACQUAINTANCES

async def app_acquaintances(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = context.user_data
    
    app_id = db.add_application(
        user.id, user.username, data['nickname'], data['avatar'], data['category'],
        data['project'], data.get('chat'), data['km_year'], data['participated'],
        data.get('reason'), data['fame_method'], update.message.text
    )
    
    await update.message.reply_text(f"✅ Заявка #{app_id} отправлена!", reply_markup=get_user_keyboard())
    
    for admin_id in ADMINS:
        try:
            await context.bot.send_message(admin_id, f"🔔 Новая заявка #{app_id} от {data['nickname']}")
        except:
            pass
    
    context.user_data.clear()
    return ConversationHandler.END

# ==================== АДМИНКА ====================
async def show_applications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS and user_id != OWNER_ID:
        await update.message.reply_text("⛔ Нет прав!")
        return
    
    apps = db.get_pending_applications()
    if not apps:
        await update.message.reply_text("📭 Нет активных заявок.")
        return
    
    kb = get_apps_list_keyboard(apps)
    if kb:
        await update.message.reply_text("📊 Список заявок:", reply_markup=kb)

async def view_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    app_id = int(query.data.split("_")[1])
    app = db.get_application_by_id(app_id)
    
    if not app:
        await query.message.reply_text("❌ Заявка не найдена!")
        await query.message.delete()
        return
    
    text = format_application(app)
    
    if app[4]:
        await query.message.reply_photo(photo=app[4], caption=text, parse_mode=ParseMode.HTML, reply_markup=get_app_view_keyboard(app_id))
    else:
        await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=get_app_view_keyboard(app_id))
    
    await query.message.delete()

async def accept_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id not in ADMINS and user_id != OWNER_ID:
        await query.message.reply_text("⛔ Нет прав!")
        return
    
    app_id = int(query.data.split("_")[1])
    app = db.get_application_by_id(app_id)
    
    if not app:
        await query.message.reply_text("❌ Заявка не найдена!")
        return
    
    db.update_application_status(app_id, 'accepted', user_id)
    
    try:
        await context.bot.send_message(app[1], f"✅ ЗАЯВКА #{app_id} ПРИНЯТА! Добро пожаловать!")
    except:
        pass
    
    await query.message.reply_text(f"✅ Заявка #{app_id} ПРИНЯТА!")
    await query.message.delete()

async def reject_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id not in ADMINS and user_id != OWNER_ID:
        await query.message.reply_text("⛔ Нет прав!")
        return
    
    app_id = int(query.data.split("_")[1])
    app = db.get_application_by_id(app_id)
    
    if not app:
        await query.message.reply_text("❌ Заявка не найдена!")
        return
    
    db.update_application_status(app_id, 'rejected', user_id)
    
    try:
        await context.bot.send_message(app[1], f"❌ ЗАЯВКА #{app_id} ОТКЛОНЕНА")
    except:
        pass
    
    await query.message.reply_text(f"❌ Заявка #{app_id} ОТКЛОНЕНА!")
    await query.message.delete()

async def add_note_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    app_id = int(query.data.split("_")[2])
    context.user_data['note_app_id'] = app_id
    await query.message.reply_text("📝 Введите заметку для этой заявки:")
    return ADD_NOTE_STATE

async def add_note_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note = update.message.text
    app_id = context.user_data.get('note_app_id')
    if app_id:
        db.update_application_note(app_id, note)
        await update.message.reply_text(f"✅ Заметка для заявки #{app_id} сохранена!", reply_markup=get_admin_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("⛔ Только для владельца!")
        return
    
    history = db.get_history_applications()
    if not history:
        await update.message.reply_text("📭 История пуста.")
        return
    
    text = "📜 ИСТОРИЯ ЗАЯВОК:\n\n"
    for h in history[:20]:
        text += f"👤 {h[3]} | #{h[0]} | Принял: {h[5]}\n"
    await update.message.reply_text(text)

async def manage_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("⛔ Только для владельца!")
        return
    
    admins = db.get_all_admins()
    text = "👑 Управление админами\n\nТекущие админы:\n"
    for admin in admins:
        text += f"• {admin}\n"
    text += "\nОтправьте ID пользователя для добавления:"
    
    await update.message.reply_text(text)
    return ADD_ADMIN_STATE

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_admin_id = int(update.message.text)
        db.add_admin(new_admin_id)
        ADMINS.append(new_admin_id)
        await update.message.reply_text(f"✅ Админ {new_admin_id} добавлен!", reply_markup=get_owner_keyboard())
    except:
        await update.message.reply_text("❌ Неверный ID!")
    context.user_data.clear()
    return ConversationHandler.END

# ==================== ЖАЛОБЫ ====================
async def handle_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚠️ Укажите username нарушителя:")
    return COMPLAINT_USER

async def complaint_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['complaint_on'] = update.message.text
    await update.message.reply_text("📝 Причина жалобы:")
    return COMPLAINT_REASON

async def complaint_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['complaint_reason'] = update.message.text
    await update.message.reply_text("🔗 Доказательства (или '-'):")
    return COMPLAINT_EVIDENCE

async def complaint_evidence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    evidence = update.message.text if update.message.text != '-' else None
    db.add_complaint(update.effective_user.id, 0, context.user_data['complaint_on'], context.user_data['complaint_reason'], evidence)
    await update.message.reply_text("✅ Жалоба отправлена!", reply_markup=get_user_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user_id = update.effective_user.id
    if user_id == OWNER_ID:
        kb = get_owner_keyboard()
    elif user_id in ADMINS:
        kb = get_admin_keyboard()
    else:
        kb = get_user_keyboard()
    await update.message.reply_text("❌ Отменено.", reply_markup=kb)
    return ConversationHandler.END

# ==================== MAIN ====================
def main():
    print("🚀 БОТ ЗАПУЩЕН!")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    
    # Кнопки меню
    app.add_handler(MessageHandler(filters.Regex('^📋 Правила$'), rules))
    app.add_handler(MessageHandler(filters.Regex('^👥 Модерация$'), moderation_info))
    app.add_handler(MessageHandler(filters.Regex('^📊 Заявки$'), show_applications))
    app.add_handler(MessageHandler(filters.Regex('^📜 История$'), show_history))
    app.add_handler(MessageHandler(filters.Regex('^👑 Управление админами$'), manage_admins))
    
    # Подача заявки
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^📝 Отправить заявку$'), start_app)],
        states={
            APP_AVATAR: [MessageHandler(filters.PHOTO, app_avatar)],
            APP_NICKNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, app_nickname)],
            APP_CATEGORY: [CallbackQueryHandler(app_category, pattern="^cat_")],
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
    
    # Жалоба
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^⚠️ Пожаловаться$'), handle_complaint)],
        states={
            COMPLAINT_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_user)],
            COMPLAINT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_reason)],
            COMPLAINT_EVIDENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_evidence)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    # Заметки
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(add_note_start, pattern="^note_")],
        states={ADD_NOTE_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_note_save)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    # Управление админами
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^👑 Управление админами$'), manage_admins)],
        states={ADD_ADMIN_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(view_application, pattern="^view_"))
    app.add_handler(CallbackQueryHandler(accept_app, pattern="^accept_"))
    app.add_handler(CallbackQueryHandler(reject_app, pattern="^reject_"))
    
    print("✅ Бот готов!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
