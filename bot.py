import sqlite3
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
from telegram.constants import ParseMode

BOT_TOKEN = "8226025643:AAHyrVkbV8wFum7tLbAxvhtRq5Sh_-VkH-M"
OWNER_IDS = [287265398, 7396843811]
ADMIN_IDS = [287265398, 7396843811]
CHANNEL_ID = -1003911175144
CHANNEL_LINK = "https://t.me/mirokfame"
SITE_LINK = "https://example.com"
CHECK_SUBSCRIPTION = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_file="bot_data.db"):
        self.db_file = db_file
        self.init_db()
    
    def get_connection(self):
        return sqlite3.connect(self.db_file, timeout=30, isolation_level=None)
    
    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA synchronous=NORMAL')
        
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
            on_user_info TEXT,
            reason TEXT,
            evidence TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            question TEXT,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        conn.commit()
        conn.close()
    
    def add_user(self, user_id, username):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO users (user_id, username) VALUES (?, ?)', 
                          (user_id, username))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Ошибка add_user: {e}")
    
    def get_all_users(self):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT user_id FROM users')
            users = [row[0] for row in cursor.fetchall()]
            conn.close()
            return users
        except:
            return []
    
    def get_statistics(self):
        try:
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
            
            cursor.execute('SELECT COUNT(*) FROM tickets')
            total_tickets = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM complaints WHERE status = "pending"')
            pending_complaints = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM tickets WHERE status = "open"')
            open_tickets = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total_users': total_users,
                'total_apps': total_apps,
                'pending_apps': pending_apps,
                'accepted_apps': accepted_apps,
                'rejected_apps': rejected_apps,
                'total_complaints': total_complaints,
                'total_tickets': total_tickets,
                'pending_complaints': pending_complaints,
                'open_tickets': open_tickets
            }
        except Exception as e:
            logger.error(f"Ошибка статистики: {e}")
            return {'total_users': 0, 'total_apps': 0, 'pending_apps': 0, 'accepted_apps': 0, 
                   'rejected_apps': 0, 'total_complaints': 0, 'total_tickets': 0,
                   'pending_complaints': 0, 'open_tickets': 0}
    
    def add_application(self, user_id, username, nickname, avatar_file_id, 
                        project, chat_link, km_year, participated_before, 
                        reason, fame_method, acquaintances):
        try:
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
            conn.close()
            return app_id
        except Exception as e:
            logger.error(f"Ошибка add_application: {e}")
            return None
    
    def get_pending_applications(self):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id, user_id, username, nickname, created_at FROM applications WHERE status = "pending" ORDER BY created_at DESC')
            apps = cursor.fetchall()
            conn.close()
            return apps
        except:
            return []
    
    def get_application_by_id(self, app_id):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM applications WHERE id = ?', (app_id,))
            app = cursor.fetchone()
            conn.close()
            return app
        except:
            return None
    
    def update_application_status(self, app_id, status, admin_id, reject_reason=None):
        try:
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
            conn.close()
        except Exception as e:
            logger.error(f"Ошибка update_application_status: {e}")
    
    def add_admin_note(self, app_id, admin_id, admin_username, note):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT admin_notes FROM applications WHERE id = ?', (app_id,))
            result = cursor.fetchone()
            current_notes = result[0] if result and result[0] else ""
            
            timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
            new_note = f"\n📌 {timestamp} | {admin_username} (ID: {admin_id}):\n{note}\n{'─'*30}"
            
            cursor.execute('UPDATE applications SET admin_notes = ? WHERE id = ?', 
                          (current_notes + new_note, app_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Ошибка add_admin_note: {e}")
    
    def get_history(self, limit=30):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''SELECT id, application_id, user_id, username, nickname, 
                             action, admin_id, reason, timestamp 
                             FROM history ORDER BY timestamp DESC LIMIT ?''', (limit,))
            history = cursor.fetchall()
            conn.close()
            return history
        except:
            return []
    
    def add_complaint(self, from_user_id, on_user_info, reason, evidence):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO complaints (from_user_id, on_user_info, reason, evidence) VALUES (?, ?, ?, ?)',
                          (from_user_id, on_user_info, reason, evidence))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Ошибка add_complaint: {e}")
    
    def add_ticket(self, user_id, username, question):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO tickets (user_id, username, question) VALUES (?, ?, ?)',
                          (user_id, username, question))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Ошибка add_ticket: {e}")

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
        ["📨 Рассылка", "📈 Статистика"]
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

(APP_AVATAR, APP_NICKNAME, APP_PROJECT, APP_CHAT, APP_KM_YEAR, 
 APP_PARTICIPATED, APP_REASON, APP_FAME_METHOD, APP_ACQUAINTANCES) = range(9)
(COMPLAINT_USER, COMPLAINT_REASON, COMPLAINT_EVIDENCE) = range(9, 12)
(ADD_NOTE, REJECT_REASON, BROADCAST_MESSAGE, TICKET_QUESTION) = range(12, 16)

async def check_subscription(bot, user_id):
    if not CHECK_SUBSCRIPTION:
        return True
    try:
        chat_member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except:
        return True

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

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text("❌ Ошибка. Попробуйте /start")
    except:
        pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    context.user_data.clear()
    
    db.add_user(user_id, username)
    
    if is_admin(user_id):
        await update.message.reply_text("🛡️ Админ-панель активирована!", reply_markup=get_admin_keyboard())
    else:
        await update.message.reply_text("✨ Добро пожаловать в Aricto Fame!", reply_markup=get_user_keyboard())

async def site_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.add_user(update.effective_user.id, update.effective_user.username)
    await update.message.reply_text(f"🌐 Наш сайт: {SITE_LINK}")

async def aricto_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.add_user(update.effective_user.id, update.effective_user.username)
    await update.message.reply_text("🎯 Чтобы попасть в ArictoSession, напишите владельцу: @faymovy")

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.add_user(update.effective_user.id, update.effective_user.username)
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
    user_id = update.effective_user.id
    db.add_user(user_id, update.effective_user.username)
    context.user_data.clear()
    
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
    text = update.message.text
    context.user_data['chat_link'] = None if text == '-' else text
    await update.message.reply_text("📅 С какого года в КМ?")
    return APP_KM_YEAR

async def app_km_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['km_year'] = update.message.text
    await update.message.reply_text("🎯 Участвовали в ВК/ДС КМ?")
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
    
    app_id = db.add_application(
        user.id, user.username, data.get('nickname'), data.get('avatar'),
        data.get('project'), data.get('chat_link'), data.get('km_year'), 
        data.get('participated'), data.get('reason'), data.get('fame_method'), 
        update.message.text
    )
    
    kb = get_admin_keyboard() if is_admin(user.id) else get_user_keyboard()
    
    if app_id:
        await update.message.reply_text(
            f"✅ <b>Заявка #{app_id} отправлена!</b>",
            parse_mode=ParseMode.HTML, reply_markup=kb
        )
        
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id, 
                    f"🔔 <b>Новая заявка #{app_id}</b>\n👤 {data.get('nickname')}",
                    parse_mode=ParseMode.HTML
                )
            except:
                pass
    else:
        await update.message.reply_text("❌ Ошибка отправки заявки", reply_markup=kb)
    
    context.user_data.clear()
    return ConversationHandler.END

async def show_applications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
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
    
    app_id = int(query.data.split("_")[1])
    app = db.get_application_by_id(app_id)
    
    if not app:
        await query.message.reply_text("❌ Заявка не найдена!")
        return
    
    text = format_application(app)
    
    try:
        if app[4]:
            await query.message.reply_photo(
                photo=app[4], 
                caption=text, 
                parse_mode=ParseMode.HTML, 
                reply_markup=get_app_view_keyboard(app_id)
            )
        else:
            await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=get_app_view_keyboard(app_id))
    except Exception as e:
        logger.error(f"Ошибка просмотра заявки: {e}")
        await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=get_app_view_keyboard(app_id))

async def accept_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    admin_id = query.from_user.id
    if not is_admin(admin_id):
        return
    
    app_id = int(query.data.split("_")[1])
    app = db.get_application_by_id(app_id)
    
    if not app:
        await query.message.reply_text("❌ Заявка не найдена!")
        return
    
    db.update_application_status(app_id, 'accepted', admin_id)
    
    try:
        await context.bot.send_message(
            app[1],
            f"✅ <b>Заявка #{app_id} ПРИНЯТА!</b>",
            parse_mode=ParseMode.HTML
        )
    except:
        pass
    
    await query.message.edit_text(f"✅ Заявка #{app_id} принята!")

async def reject_app_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    admin_id = query.from_user.id
    if not is_admin(admin_id):
        return ConversationHandler.END
    
    app_id = int(query.data.split("_")[1])
    context.user_data['reject_app_id'] = app_id
    
    await query.message.reply_text("❌ Введите причину отклонения:")
    return REJECT_REASON

async def reject_app_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text
    admin_id = update.effective_user.id
    app_id = context.user_data.get('reject_app_id')
    
    if not app_id:
        await update.message.reply_text("❌ Ошибка", reply_markup=get_admin_keyboard())
        return ConversationHandler.END
    
    app = db.get_application_by_id(app_id)
    if app:
        db.update_application_status(app_id, 'rejected', admin_id, reason)
        
        try:
            await context.bot.send_message(
                app[1],
                f"❌ <b>Заявка #{app_id} ОТКЛОНЕНА</b>\n📝 {reason}",
                parse_mode=ParseMode.HTML
            )
        except:
            pass
    
    await update.message.reply_text(f"❌ Заявка #{app_id} отклонена", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

async def add_note_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    app_id = int(query.data.split("_")[1])
    context.user_data['note_app_id'] = app_id
    
    await query.message.reply_text("📝 Введите заметку:")
    return ADD_NOTE

async def add_note_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note_text = update.message.text
    admin = update.effective_user
    app_id = context.user_data.get('note_app_id')
    
    if app_id:
        db.add_admin_note(app_id, admin.id, admin.username or "NoName", note_text)
        await update.message.reply_text(f"✅ Заметка добавлена к #{app_id}", reply_markup=get_admin_keyboard())
    
    return ConversationHandler.END

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
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
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    
    stats = db.get_statistics()
    
    text = f"""
📈 <b>СТАТИСТИКА</b>

👥 Пользователей: {stats['total_users']}
📝 Заявок: {stats['total_apps']} (в ожидании: {stats['pending_apps']})
✅ Принято: {stats['accepted_apps']}
❌ Отклонено: {stats['rejected_apps']}
⚠️ Жалоб: {stats['total_complaints']}
🎫 Тикетов: {stats['total_tickets']}
"""
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    
    await update.message.reply_text("📨 Введите текст рассылки (/cancel - отмена):")
    return BROADCAST_MESSAGE

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    
    if message_text == '/cancel':
        await update.message.reply_text("❌ Отменено", reply_markup=get_admin_keyboard())
        return ConversationHandler.END
    
    users = db.get_all_users()
    
    if not users:
        await update.message.reply_text("❌ Нет пользователей", reply_markup=get_admin_keyboard())
        return ConversationHandler.END
    
    success = 0
    for user_id in users:
        try:
            await context.bot.send_message(user_id, f"📢 {message_text}")
            success += 1
        except:
            pass
    
    await update.message.reply_text(f"✅ Отправлено: {success}/{len(users)}", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

async def complaint_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("⚠️ Username нарушителя:")
    return COMPLAINT_USER

async def complaint_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['complaint_on'] = update.message.text
    await update.message.reply_text("📝 Причина:")
    return COMPLAINT_REASON

async def complaint_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['complaint_reason'] = update.message.text
    await update.message.reply_text("📎 Доказательства (текст/фото/видео):")
    return COMPLAINT_EVIDENCE

async def complaint_evidence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if 'complaint_on' not in context.user_data:
        await update.message.reply_text("❌ Ошибка. Начните заново.")
        return ConversationHandler.END
    
    evidence = "Не предоставлены"
    if update.message.text:
        evidence = update.message.text
    elif update.message.photo:
        evidence = f"Фото {update.message.photo[-1].file_id}"
    elif update.message.video:
        evidence = f"Видео {update.message.video.file_id}"
    
    db.add_complaint(user_id, context.user_data['complaint_on'], 
                    context.user_data['complaint_reason'], evidence)
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, 
                f"⚠️ <b>Жалоба</b>\n👤 {context.user_data['complaint_on']}\n📝 {context.user_data['complaint_reason']}",
                parse_mode=ParseMode.HTML)
        except:
            pass
    
    kb = get_admin_keyboard() if is_admin(user_id) else get_user_keyboard()
    await update.message.reply_text("✅ Жалоба отправлена!", reply_markup=kb)
    return ConversationHandler.END

async def ticket_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🎫 Ваш вопрос:")
    return TICKET_QUESTION

async def ticket_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = update.message.text
    user = update.effective_user
    
    db.add_ticket(user.id, user.username, question)
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, 
                f"🎫 <b>Тикет</b>\n👤 @{user.username or user.id}\n❓ {question}",
                parse_mode=ParseMode.HTML)
        except:
            pass
    
    kb = get_admin_keyboard() if is_admin(user.id) else get_user_keyboard()
    await update.message.reply_text("✅ Вопрос отправлен!", reply_markup=kb)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.clear()
    kb = get_admin_keyboard() if is_admin(user_id) else get_user_keyboard()
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
