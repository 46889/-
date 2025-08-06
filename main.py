import sqlite3
import telebot
import random
import time
import logging
import pandas as pd
import os
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Настройка логирования
logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

####################################################################
# ======================= НАСТРОЙКИ БОТА ========================= #
####################################################################

BOT_TOKEN = "7472230346:AAHydnjEp9UZviWGr7drZEVKxCXYFngvtCc"
CHANNEL_USERNAME = "@ldlfflgm"
CHANNEL_LINK = "https://t.me/ldlfflgm"
BONUS_AMOUNT = 100
# Список администраторов
ADMINS = [7338817463, 8190084234]  # Основной админ и новый админ
WB_LINK = "https://www.wildberries.ru/seller/ВАШ_МАГАЗИН"
OZON_LINK = "https://www.ozon.ru/seller/ВАШ_МАГАЗИН"

# Настройки фотографий (по умолчанию)
DEFAULT_PHOTOS = {
    "start": "1.jpg",
    "profile": "2.jpg", 
    "socials": "3.jpg",
    "support": "4.jpg",
    "admin": "5.jpg",
    "iphone": "6.jpg"
}

# Формат для копируемого текста
COPYABLE_TEXT = "`{text}`"  # Markdown формат для копирования

START_MESSAGE = "🌟 Добро пожаловать в наш сервис!\n👇 Выберите нужный раздел:"
SUPPORT_MESSAGE = "💬 Поддержка\n\nВыберите категорию вашего вопроса:"
SOCIALS_MESSAGE = "📱 Наши социальные сети\n\nПодпишитесь на официальные ресурсы:"
EARN_TOKENS_MESSAGE = "🟡 Выберите способ заработка токенов:"
PROFILE_MESSAGE = "👤 Ваш профиль\n\n🆔 ID: {user_id}\n👤 Username: {username}\n🟡 Токены: {tokens}\n🎁 Бонус за подписку: {bonus_status}\n{admin_status}"
GIVEAWAYS_MESSAGE = "🎁 Активные розыгрыши:\n\n"
GIVEAWAY_DETAILS_MESSAGE = "{name}\n\n{description}\n\n💸 Стоимость участия: {price}🟡"
SUCCESS_PARTICIPATION = "🎉 Вы успешно участвуете в розыгрыше!\n💸 С вас списано: {price}🟡\n🟡 Ваш новый баланс: {new_balance}"
SUCCESS_BONUS = "🎉 Поздравляем! Вы получили {bonus}🟡\n\n✅ Ваш новый баланс: {new_balance}\n\nСпасибо за подписку!"
NOT_SUBSCRIBED_MESSAGE = "❌ Вы не подписаны на канал!\n\nПожалуйста, подпишитесь: {CHANNEL_LINK}"
ADMIN_CANNOT_PARTICIPATE = "⛔ Администратор не может участвовать в розыгрышах!"

# Настройки поддержки
SUPPORT_CATEGORIES = {
    "Камеры": "https://t.me/ваш_чат_камеры",
    "Стекла": "https://t.me/ваш_чат_стекла",
    "Держатели": "https://t.me/ваш_чат_держатели",
    "Наушники": "https://t.me/ваш_чат_наушники"
}

SOCIAL_MEDIA = {
    "Instagram": "https://instagram.com/ваш_профиль",
    "Telegram": "https://t.me/ваш_канал",
    "ВКонтакте": "https://vk.com/ваша_группа"
}

GIVEAWAYS = [
    {
        "name": "🎁 Стандартный розыгрыш",
        "description": "Описание и условия розыгрыша...",
        "price": 15
    },
]

# Розыгрыш iPhone за отзыв (обновленный с использованием COPYABLE_TEXT)
IPHONE_GIVEAWAY_INSTRUCTION = """📱 Розыгрыш iPhone за отзыв!
 1. Вы купили любой товар TOFURA или FaizFull на Wb или OZON 
 2. Оставьте отзыв с ID розыгрыша, скопируйте его вставьте в ваш текст с отзывом (фото и текст обязательны), оставляйте честный отзыв о продукте 
 3. Ура вы уже участник, подпишитесь на наш telegram, и будьте в курсе розыгрыша 
 4. Розыгрыш произойдет 30.12.25 в 20:00 мск 
 5. Заявки принимаются до 29.12.25 00:00
✅ Ваш уникальный ID для участия: {unique_id}

📝 Текст для копирования, нажми👇:
{copy_text}

⚠️ Важно: сохраните ваш ID, он понадобится для подтверждения участия!
"""

####################################################################
# ======================= ОСНОВНОЙ КОД =========================== #
####################################################################

bot = telebot.TeleBot(BOT_TOKEN)
conn = sqlite3.connect('profiles.db', check_same_thread=False)
cursor = conn.cursor()

# Состояния пользователей
user_states = {}
admin_states = {}  # Для хранения состояний администраторов

# Инициализация базы данных
def init_db():
    # Таблица пользователей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        tokens INTEGER DEFAULT 100,
        bonus_received BOOLEAN DEFAULT 0,
        created_at TEXT,
        last_seen TEXT
    )
    ''')
    
    # Проверка и добавление столбцов
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if 'username' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
    
    if 'tokens' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN tokens INTEGER DEFAULT 100")
        cursor.execute("UPDATE users SET tokens = 100 WHERE tokens IS NULL")
    
    if 'bonus_received' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN bonus_received BOOLEAN DEFAULT 0")
        cursor.execute("UPDATE users SET bonus_received = 0 WHERE bonus_received IS NULL")
    
    if 'created_at' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN created_at TEXT")
        cursor.execute("UPDATE users SET created_at = ?", (now,))
    
    if 'last_seen' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN last_seen TEXT")
        cursor.execute("UPDATE users SET last_seen = ?", (now,))
    
    # Таблица розыгрышей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS giveaways (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        price INTEGER NOT NULL
    )
    ''')
    
    # Таблица участников розыгрышей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS giveaway_participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        giveaway_id INTEGER,
        participation_date TEXT,
        FOREIGN KEY(user_id) REFERENCES users(user_id),
        FOREIGN KEY(giveaway_id) REFERENCES giveaways(id)
    )
    ''')
    
    # Таблица участников розыгрыша iPhone
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS iphone_participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        unique_id TEXT UNIQUE,
        participation_date TEXT,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )
    ''')
    
    # Таблица настроек бота
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bot_settings (
        id INTEGER PRIMARY KEY,
        setting_name TEXT UNIQUE,
        setting_value TEXT
    )
    ''')
    
    # Добавляем столбец giveaway_id в таблицу iphone_participants если его нет
    cursor.execute("PRAGMA table_info(iphone_participants)")
    iphone_columns = [col[1] for col in cursor.fetchall()]
    
    if 'giveaway_id' not in iphone_columns:
        cursor.execute("ALTER TABLE iphone_participants ADD COLUMN giveaway_id INTEGER DEFAULT 1")
    
    # Инициализация настроек по умолчанию
    default_settings = {
        'start_message': START_MESSAGE,
        'support_message': SUPPORT_MESSAGE,
        'socials_message': SOCIALS_MESSAGE,
        'earn_tokens_message': EARN_TOKENS_MESSAGE,
        'profile_message': PROFILE_MESSAGE,
        'giveaways_message': GIVEAWAYS_MESSAGE,
        'iphone_instruction': IPHONE_GIVEAWAY_INSTRUCTION,
        'photo_start': DEFAULT_PHOTOS["start"],
        'photo_profile': DEFAULT_PHOTOS["profile"],
        'photo_socials': DEFAULT_PHOTOS["socials"],
        'photo_support': DEFAULT_PHOTOS["support"],
        'photo_admin': DEFAULT_PHOTOS["admin"],
        'photo_iphone': DEFAULT_PHOTOS["iphone"],
        'copyable_text': COPYABLE_TEXT  # Сохраняем формат копирования
    }
    
    for setting_name, setting_value in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO bot_settings (setting_name, setting_value) VALUES (?, ?)", 
                      (setting_name, setting_value))
    
    # Добавляем розыгрыши, если таблица пуста
    cursor.execute("SELECT COUNT(*) FROM giveaways")
    if cursor.fetchone()[0] == 0:
        for giveaway in GIVEAWAYS:
            cursor.execute(
                "INSERT INTO giveaways (name, description, price) VALUES (?, ?, ?)",
                (giveaway["name"], giveaway["description"], giveaway["price"])
            )
    conn.commit()

init_db()

# Функции для работы с настройками
def get_setting(setting_name, default_value=""):
    try:
        cursor.execute("SELECT setting_value FROM bot_settings WHERE setting_name = ?", (setting_name,))
        result = cursor.fetchone()
        return result[0] if result else default_value
    except:
        return default_value

def update_setting(setting_name, setting_value):
    try:
        cursor.execute("INSERT OR REPLACE INTO bot_settings (setting_name, setting_value) VALUES (?, ?)", 
                      (setting_name, setting_value))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления настройки {setting_name}: {str(e)}")
        return False

def send_photo_message(chat_id, photo_key, caption, reply_markup=None, parse_mode=None):
    try:
        photo_path = get_setting(f'photo_{photo_key}', DEFAULT_PHOTOS.get(photo_key, "1.jpg"))
        
        # Пробуем отправить как локальный файл
        try:
            with open(photo_path, 'rb') as photo:
                return bot.send_photo(chat_id, photo, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
        except FileNotFoundError:
            # Если файл не найден, отправляем текстовое сообщение
            return bot.send_message(chat_id, f"📸 {caption}", reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        logger.error(f"Ошибка отправки фото {photo_key}: {str(e)}")
        return bot.send_message(chat_id, caption, reply_markup=reply_markup, parse_mode=parse_mode)

def edit_photo_message(chat_id, message_id, photo_key, caption, reply_markup=None, parse_mode=None):
    try:
        photo_path = get_setting(f'photo_{photo_key}', DEFAULT_PHOTOS.get(photo_key, "1.jpg"))
        
        # Удаляем старое сообщение и отправляем новое с фото
        try:
            bot.delete_message(chat_id, message_id)
        except:
            pass
        
        return send_photo_message(chat_id, photo_key, caption, reply_markup, parse_mode)
    except Exception as e:
        logger.error(f"Ошибка редактирования фото {photo_key}: {str(e)}")
        return safe_edit_message(chat_id, message_id, caption, reply_markup, parse_mode)

# Функции для работы с базой данных
def update_user_info(user_id, username):
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            # Обновляем username и время последнего визита
            cursor.execute("UPDATE users SET username = ?, last_seen = ? WHERE user_id = ?", 
                          (username, now, user_id))
        else:
            # Создаем нового пользователя
            cursor.execute(
                "INSERT INTO users (user_id, username, tokens, bonus_received, created_at, last_seen) VALUES (?, ?, ?, ?, ?, ?)", 
                (user_id, username, 100, 0, now, now)
            )
        conn.commit()
        logger.info(f"Пользователь обновлен: {user_id} ({username})")
    except Exception as e:
        logger.error(f"Ошибка при обновлении пользователя {user_id}: {str(e)}")
        conn.rollback()

def is_user_subscribed(user_id):
    try:
        chat_member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return chat_member.status not in ['left', 'kicked']
    except Exception as e:
        logger.error(f"Ошибка проверки подписки пользователя {user_id}: {str(e)}")
        return False

def is_admin(user_id):
    return user_id in ADMINS

def get_all_users_except_admins():
    cursor.execute("SELECT user_id FROM users WHERE user_id NOT IN ({})".format(','.join('?' * len(ADMINS))), ADMINS)
    return [row[0] for row in cursor.fetchall()]

# Функция для экспорта данных в Excel
def export_users_to_excel():
    try:
        # Получаем данные о пользователях
        cursor.execute('''
            SELECT 
                u.user_id, 
                u.username, 
                u.tokens, 
                CASE WHEN u.bonus_received = 1 THEN 'Да' ELSE 'Нет' END as bonus_received,
                u.created_at,
                u.last_seen,
                (SELECT COUNT(*) FROM giveaway_participants gp WHERE gp.user_id = u.user_id) as participation_count
            FROM users u
            ORDER BY u.user_id
        ''')
        users = cursor.fetchall()
        
        # Получаем данные об участии в розыгрышах
        cursor.execute('''
            SELECT 
                gp.user_id,
                g.name as giveaway_name,
                gp.participation_date
            FROM giveaway_participants gp
            JOIN giveaways g ON gp.giveaway_id = g.id
        ''')
        participations = cursor.fetchall()
        
        # Создаем DataFrame для пользователей
        user_columns = [
            'ID', 'Username', 'Токены', 'Бонус получен', 
            'Дата регистрации', 'Последний визит', 'Участий в розыгрышах'
        ]
        df_users = pd.DataFrame(users, columns=user_columns)
        
        # Создаем DataFrame для участий
        participation_columns = ['ID пользователя', 'Розыгрыш', 'Дата участия']
        df_participations = pd.DataFrame(participations, columns=participation_columns)
        
        # Создаем Excel файл
        filename = f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        # Упрощенное создание Excel без сложного форматирования
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df_users.to_excel(writer, sheet_name='Пользователи', index=False)
            df_participations.to_excel(writer, sheet_name='Участия', index=False)
            
            # Автоматическое выравнивание ширины колонок
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = (max_length + 2) * 1.2
                    worksheet.column_dimensions[column_letter].width = adjusted_width
        
        logger.info(f"Файл экспорта создан: {filename}")
        return filename
    
    except Exception as e:
        logger.error(f"Ошибка при экспорте данных: {str(e)}", exc_info=True)
        return None

# Клавиатуры
def main_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    row1 = [
        InlineKeyboardButton("💬 Поддержка", callback_data="support"),
        InlineKeyboardButton("📱 Соцсети", callback_data="socials")
    ]
    row2 = [
        InlineKeyboardButton("🎁 Розыгрыши", callback_data="giveaways"),
        InlineKeyboardButton("👤 Профиль", callback_data="profile")
    ]
    row3_new = [
        InlineKeyboardButton("📱 iPhone за отзыв", callback_data="iphone_giveaway")
    ]
    row4 = [
        InlineKeyboardButton("Мы на WB", url=WB_LINK),
        InlineKeyboardButton("Мы на Ozon", url=OZON_LINK)
    ]
    keyboard.add(*row1)
    keyboard.add(*row2)
    keyboard.add(*row3_new)
    keyboard.add(*row4)
    return keyboard

def back_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return keyboard

def giveaway_keyboard(giveaway_id):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("✅ Участвовать", callback_data=f"participate_{giveaway_id}"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="giveaways"))
    return keyboard

def earn_tokens_menu_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("🔗 Подписаться на канал", callback_data="earn_by_subscribe"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return keyboard

def profile_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🟡 Заработать токены", callback_data="earn_tokens"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return keyboard

def admin_back_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 Назад в админку", callback_data="admin_back"))
    return keyboard

def admin_winner_type_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🎁 Стандартный розыгрыш", callback_data="winner_standard"),
        InlineKeyboardButton("📱 Розыгрыш iPhone", callback_data="winner_iphone")
    )
    keyboard.add(InlineKeyboardButton("🔙 Назад в админку", callback_data="admin_back"))
    return keyboard

def bot_editor_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📝 Тексты", callback_data="edit_texts"),
        InlineKeyboardButton("📸 Фотографии", callback_data="edit_photos")
    )
    keyboard.add(InlineKeyboardButton("🔙 Назад в админку", callback_data="admin_back"))
    return keyboard

def edit_texts_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🏠 Стартовое сообщение", callback_data="edit_text_start"),
        InlineKeyboardButton("👤 Сообщение профиля", callback_data="edit_text_profile"),
        InlineKeyboardButton("📱 Сообщение соцсетей", callback_data="edit_text_socials"),
        InlineKeyboardButton("💬 Сообщение поддержки", callback_data="edit_text_support"),
        InlineKeyboardButton("🟡 Сообщение токенов", callback_data="edit_text_tokens"),
        InlineKeyboardButton("🎁 Сообщение розыгрышей", callback_data="edit_text_giveaways"),
        InlineKeyboardButton("📱 Инструкция iPhone", callback_data="edit_text_iphone"),
        InlineKeyboardButton("📋 Формат копируемого текста", callback_data="edit_text_copyable")
    )
    keyboard.add(InlineKeyboardButton("🔙 Назад к редактору", callback_data="bot_editor"))
    return keyboard

def edit_photos_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🏠 Стартовое фото", callback_data="edit_photo_start"),
        InlineKeyboardButton("👤 Фото профиля", callback_data="edit_photo_profile")
    )
    keyboard.add(
        InlineKeyboardButton("📱 Фото соцсетей", callback_data="edit_photo_socials"),
        InlineKeyboardButton("💬 Фото поддержки", callback_data="edit_photo_support")
    )
    keyboard.add(
        InlineKeyboardButton("👑 Фото админки", callback_data="edit_photo_admin"),
        InlineKeyboardButton("📱 Фото iPhone", callback_data="edit_photo_iphone")
    )
    keyboard.add(InlineKeyboardButton("🔙 Назад к редактору", callback_data="bot_editor"))
    return keyboard

def admin_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("👥 Участники розыгрыша", callback_data="admin_participants"),
        InlineKeyboardButton("🎁 Узнать победителя", callback_data="admin_winner_type")
    )
    keyboard.add(
        InlineKeyboardButton("📱 Участники iPhone", callback_data="admin_iphone_participants")
    )
    keyboard.add(
        InlineKeyboardButton("👤 Все пользователи", callback_data="admin_all_users"),
        InlineKeyboardButton("📊 Выгрузить данные (Excel)", callback_data="admin_export_data")
    )
    keyboard.add(
        InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
        InlineKeyboardButton("⚙️ Редактировать бота", callback_data="bot_editor")
    )
    keyboard.add(InlineKeyboardButton("🔙 Назад в меню", callback_data="back"))
    return keyboard

def winner_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔁 Еще раз", callback_data="admin_winner"),
        InlineKeyboardButton("🔙 Назад в админку", callback_data="admin_back")
    )
    return keyboard

def support_categories_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    for category, link in SUPPORT_CATEGORIES.items():
        keyboard.add(InlineKeyboardButton(category, url=link))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return keyboard

def broadcast_confirmation_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_broadcast"),
        InlineKeyboardButton("❌ Отменить", callback_data="cancel_broadcast")
    )
    return keyboard

def animate_winner_selection(chat_id, message_id, participants):
    frames = 15
    frame_delay = 0.2
    
    try:
        bot.edit_message_text("🎰 Выбор победителя...", chat_id, message_id)
    except:
        pass
    
    for i in range(frames):
        participant = random.choice(participants)
        user_id, username = participant
        username_display = f"@{username}" if username else "без username"
        
        text = f"🎰 Выбор победителя...\n\n"
        text += f"▰{'▰' * (i % 5)}{'▱' * (4 - (i % 5))} {100 * (i + 1) // frames}%\n\n"
        text += f"👤 Текущий кандидат: ID {user_id} ({username_display})"
        
        try:
            bot.edit_message_text(text, chat_id, message_id)
        except:
            break
        
        time.sleep(frame_delay)
    
    return participant

# Безопасное редактирование сообщения
def safe_edit_message(chat_id, message_id, text, reply_markup=None, parse_mode=None):
    try:
        # Пробуем отредактировать текст
        bot.edit_message_text(
            text, 
            chat_id, 
            message_id, 
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except telebot.apihelper.ApiTelegramException as e:
        if "no text in the message" in str(e):
            # Если сообщение содержит фото, отправляем новое текстовое сообщение
            try:
                bot.delete_message(chat_id, message_id)
            except:
                pass
            bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            raise e
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {str(e)}")

# Обработчики команд
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    update_user_info(user_id, username)
    
    start_text = get_setting('start_message', START_MESSAGE)
    send_photo_message(message.chat.id, 'start', start_text, main_menu())

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ У вас нет прав доступа!")
        return
    bot.send_message(message.chat.id, "👑 Панель администратора:", reply_markup=admin_keyboard())

# Обработчики callback
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    user_id = call.from_user.id
    username = call.from_user.username
    
    # Всегда обновляем информацию о пользователе
    update_user_info(user_id, username)
    
    # Обработка основных команд
    if call.data == "support":
        support_text = get_setting('support_message', SUPPORT_MESSAGE)
        edit_photo_message(chat_id, message_id, 'support', support_text, support_categories_keyboard())
    
    elif call.data == "socials":
        keyboard = InlineKeyboardMarkup()
        for name, url in SOCIAL_MEDIA.items():
            keyboard.add(InlineKeyboardButton(name, url=url))
        keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
        
        socials_text = get_setting('socials_message', SOCIALS_MESSAGE)
        edit_photo_message(chat_id, message_id, 'socials', socials_text, keyboard)
    
    elif call.data == "giveaways":
        cursor.execute("SELECT id, name, description, price FROM giveaways")
        giveaways = cursor.fetchall()
        
        if not giveaways:
            safe_edit_message(chat_id, message_id, "🎁 На данный момент активных розыгрышей нет", back_keyboard())
            return
            
        text = get_setting('giveaways_message', GIVEAWAYS_MESSAGE)
        for giveaway in giveaways:
            giveaway_id, name, description, price = giveaway
            text += f"{name}\n{description}\nСтоимость участия: {price}🟡\n\n"
        
        keyboard = InlineKeyboardMarkup()
        for giveaway in giveaways:
            giveaway_id, name, *_ = giveaway
            keyboard.add(InlineKeyboardButton(name, callback_data=f"giveaway_{giveaway_id}"))
        keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
        safe_edit_message(chat_id, message_id, text, keyboard)
    
    elif call.data == "earn_tokens":
        earn_text = get_setting('earn_tokens_message', EARN_TOKENS_MESSAGE)
        keyboard = earn_tokens_menu_keyboard()
        safe_edit_message(chat_id, message_id, earn_text, keyboard)
    
    elif call.data == "earn_by_subscribe":
        cursor.execute("SELECT bonus_received FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result and result[0] and not is_admin(user_id):
            safe_edit_message(chat_id, message_id, "🟡 Вы уже получали бонус за подписку!\n\nПопробуйте позже.", back_keyboard())
            return
        
        text = f"🟡 Подпишитесь на наш канал и получите {BONUS_AMOUNT} токенов!\n\nКанал: {CHANNEL_LINK}"
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔗 Подписаться на канал", url=CHANNEL_LINK))
        keyboard.add(InlineKeyboardButton("✅ Проверить подписку", callback_data="check_subscription"))
        keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="earn_tokens"))
        safe_edit_message(chat_id, message_id, text, keyboard)
    
    elif call.data == "check_subscription":
        if not is_admin(user_id):
            cursor.execute("SELECT bonus_received FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            if result and result[0]:
                bot.answer_callback_query(call.id, "⛔ Вы уже получали бонус!")
                return
        
        if is_user_subscribed(user_id):
            bonus = BONUS_AMOUNT * 10 if is_admin(user_id) else BONUS_AMOUNT
            cursor.execute("UPDATE users SET tokens = tokens + ?, bonus_received = 1 WHERE user_id = ?", (bonus, user_id))
            conn.commit()
            
            cursor.execute("SELECT tokens FROM users WHERE user_id = ?", (user_id,))
            new_balance = cursor.fetchone()[0]
            
            text = SUCCESS_BONUS.format(bonus=bonus, new_balance=new_balance)
            if is_admin(user_id):
                text += "\n\n👑 Администраторский бонус x10!"
            safe_edit_message(chat_id, message_id, text, back_keyboard())
        else:
            bot.answer_callback_query(call.id, "❌ Вы не подписаны!")
            safe_edit_message(chat_id, message_id, NOT_SUBSCRIBED_MESSAGE.format(CHANNEL_LINK=CHANNEL_LINK), earn_tokens_menu_keyboard())
    
    elif call.data.startswith("giveaway_"):
        giveaway_id = int(call.data.split("_")[1])
        cursor.execute("SELECT name, description, price FROM giveaways WHERE id = ?", (giveaway_id,))
        giveaway = cursor.fetchone()
        
        if not giveaway:
            bot.answer_callback_query(call.id, "❌ Розыгрыш не найден")
            return
            
        name, description, price = giveaway
        text = GIVEAWAY_DETAILS_MESSAGE.format(name=name, description=description, price=price)
        safe_edit_message(chat_id, message_id, text, giveaway_keyboard(giveaway_id))
    
    elif call.data.startswith("participate_"):
        giveaway_id = int(call.data.split("_")[1])
        
        if is_admin(user_id):
            bot.answer_callback_query(call.id, ADMIN_CANNOT_PARTICIPATE)
            return
            
        cursor.execute("SELECT price FROM giveaways WHERE id = ?", (giveaway_id,))
        result = cursor.fetchone()
        
        if not result:
            bot.answer_callback_query(call.id, "❌ Розыгрыш не найден")
            return
            
        price = result[0]
        cursor.execute("SELECT tokens FROM users WHERE user_id = ?", (user_id,))
        tokens_result = cursor.fetchone()
        
        if not tokens_result:
            bot.answer_callback_query(call.id, "❌ Профиль не найден!")
            return
            
        tokens = tokens_result[0]
        
        if tokens < price:
            bot.answer_callback_query(call.id, f"⛔ Недостаточно токенов! Нужно {price}🟡")
            return
        
        new_balance = tokens - price
        cursor.execute("UPDATE users SET tokens = ? WHERE user_id = ?", (new_balance, user_id))
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO giveaway_participants (user_id, giveaway_id, participation_date) VALUES (?, ?, ?)",
            (user_id, giveaway_id, now)
        )
        conn.commit()
        
        bot.answer_callback_query(call.id, f"✅ Успешно! Списанно {price}🟡")
        safe_edit_message(
            chat_id, message_id,
            SUCCESS_PARTICIPATION.format(price=price, new_balance=new_balance),
            back_keyboard()
        )
    
    elif call.data == "profile":
        cursor.execute("SELECT tokens, username, bonus_received FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        if result:
            tokens, db_username, bonus_received = result
            username_display = f"@{db_username}" if db_username else "не указан"
            
            if is_admin(user_id):
                admin_status = "👑 Администратор"
                bonus_status = "♾️ Без ограничений"
            else:
                admin_status = ""
                bonus_status = "✅ Получен" if bonus_received else "❌ Не получен"
            
            profile_text = get_setting('profile_message', PROFILE_MESSAGE)
            text = profile_text.format(
                user_id=user_id,
                username=username_display,
                tokens=tokens,
                bonus_status=bonus_status,
                admin_status=admin_status
            )
        else:
            text = "❌ Профиль не найден! Попробуйте /start"
        
        edit_photo_message(chat_id, message_id, 'profile', text, profile_keyboard())
    
    elif call.data == "back":
        safe_edit_message(chat_id, message_id, START_MESSAGE, main_menu())
    
    # Розыгрыш iPhone за отзыв
    elif call.data == "iphone_giveaway":
        # Проверяем, участвует ли уже пользователь
        cursor.execute("SELECT unique_id FROM iphone_participants WHERE user_id = ?", (user_id,))
        existing = cursor.fetchone()
        
        iphone_instruction = get_setting('iphone_instruction', IPHONE_GIVEAWAY_INSTRUCTION)
        copyable_format = get_setting('copyable_text', COPYABLE_TEXT)
        
        if existing:
            # Показываем существующий ID
            unique_id = existing[0]
            # Формируем текст для копирования с Markdown
            copy_text = copyable_format.format(text=f"Участвую в розыгрыше iPhone! ID: {unique_id}")
            text = iphone_instruction.format(unique_id=unique_id, copy_text=copy_text)
            text += "\n\n✅ Вы уже участвуете в розыгрыше!"
        else:
            # Генерируем новый уникальный ID
            unique_id = f"IP{random.randint(10000, 99999)}{random.randint(100, 999)}"
            
            # Проверяем уникальность ID
            while True:
                cursor.execute("SELECT id FROM iphone_participants WHERE unique_id = ?", (unique_id,))
                if not cursor.fetchone():
                    break
                unique_id = f"IP{random.randint(10000, 99999)}{random.randint(100, 999)}"
            
            # Сохраняем участника
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "INSERT INTO iphone_participants (user_id, unique_id, participation_date, giveaway_id) VALUES (?, ?, ?, ?)",
                (user_id, unique_id, now, 1)
            )
            conn.commit()
            
            # Формируем текст для копирования с Markdown
            copy_text = copyable_format.format(text=f"Участвую в розыгрыше iPhone! ID: {unique_id}")
            text = iphone_instruction.format(unique_id=unique_id, copy_text=copy_text)
            text += "\n\n🎉 Вы успешно зарегистрированы в розыгрыше!"
        
        # Отправляем с Markdown для форматирования текста
        edit_photo_message(chat_id, message_id, 'iphone', text, back_keyboard(), parse_mode="Markdown")
    
    # Админские команды
    elif call.data == "admin_participants":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещен!")
            return
            
        cursor.execute('''
        SELECT u.user_id, u.username, g.name, gp.participation_date 
        FROM giveaway_participants gp
        JOIN users u ON gp.user_id = u.user_id
        JOIN giveaways g ON gp.giveaway_id = g.id
        ''')
        participants = cursor.fetchall()
        
        if not participants:
            safe_edit_message(chat_id, message_id, "❌ Участников розыгрышей пока нет", admin_back_keyboard())
            return
            
        response = "🎫 Участники розыгрышей:\n\n"
        for idx, participant in enumerate(participants, 1):
            user_id, username, giveaway_name, date = participant
            username_display = f"@{username}" if username else "без username"
            response += f"{idx}. ID {user_id} ({username_display})\n"
            response += f"   Розыгрыш: {giveaway_name}\n"
            response += f"   Дата: {date}\n\n"
        
        safe_edit_message(chat_id, message_id, response, admin_back_keyboard())
    
    elif call.data == "admin_winner_type":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещен!")
            return
            
        safe_edit_message(chat_id, message_id, "🎁 Выберите тип розыгрыша:", admin_winner_type_keyboard())
    
    elif call.data == "winner_standard":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещен!")
            return
            
        cursor.execute('''
        SELECT u.user_id, u.username 
        FROM giveaway_participants gp
        JOIN users u ON gp.user_id = u.user_id
        WHERE u.user_id NOT IN ({})
        '''.format(','.join('?' * len(ADMINS))), ADMINS)
        participants = cursor.fetchall()
        
        if not participants:
            safe_edit_message(chat_id, message_id, "❌ Нет участников стандартного розыгрыша", admin_back_keyboard())
            return
        
        last_shown = animate_winner_selection(chat_id, message_id, participants)
        
        winner = random.choice(participants)
        winner_id, winner_username = winner
        username_display = f"@{winner_username}" if winner_username else "без username"
        
        response = "🎉🎊 ПОБЕДИТЕЛЬ СТАНДАРТНОГО РОЗЫГРЫША 🎊🎉\n\n"
        response += "┏━━━━━━━━━━━━━━━━┓\n"
        response += "┃  🏆 ВЫИГРАЛ 🏆  ┃\n"
        response += "┗━━━━━━━━━━━━━━━━┛\n\n"
        response += f"🆔 ID: {winner_id}\n"
        response += f"👤 Username: {username_display}"
        
        if winner_username:
            response += f"\n\n✉️ Написать: @{winner_username}"
        
        safe_edit_message(chat_id, message_id, response, winner_keyboard())
    
    elif call.data == "winner_iphone":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещен!")
            return
            
        cursor.execute('''
        SELECT ip.user_id, u.username, ip.unique_id
        FROM iphone_participants ip
        JOIN users u ON ip.user_id = u.user_id
        WHERE ip.user_id NOT IN ({})
        '''.format(','.join('?' * len(ADMINS))), ADMINS)
        participants = cursor.fetchall()
        
        if not participants:
            safe_edit_message(chat_id, message_id, "❌ Нет участников розыгрыша iPhone", admin_back_keyboard())
            return
        
        # Анимация для iPhone розыгрыша
        frames = 15
        frame_delay = 0.2
        
        try:
            bot.edit_message_text("📱 Выбор победителя iPhone...", chat_id, message_id)
        except:
            pass
        
        for i in range(frames):
            participant = random.choice(participants)
            participant_user_id, username, unique_id = participant
            username_display = f"@{username}" if username else "без username"
            
            text = f"📱 Выбор победителя iPhone...\n\n"
            text += f"▰{'▰' * (i % 5)}{'▱' * (4 - (i % 5))} {100 * (i + 1) // frames}%\n\n"
            text += f"👤 Кандидат: {unique_id}\n"
            text += f"Пользователь: ID {participant_user_id} ({username_display})"
            
            try:
                bot.edit_message_text(text, chat_id, message_id)
            except:
                break
            
            time.sleep(frame_delay)
        
        winner = random.choice(participants)
        winner_user_id, winner_username, winner_unique_id = winner
        username_display = f"@{winner_username}" if winner_username else "без username"
        
        response = "📱🎉 ПОБЕДИТЕЛЬ РОЗЫГРЫША IPHONE 🎉📱\n\n"
        response += "┏━━━━━━━━━━━━━━━━┓\n"
        response += "┃ 📱 IPHONE! 📱 ┃\n"
        response += "┗━━━━━━━━━━━━━━━━┛\n\n"
        response += f"🏷️ ID розыгрыша: {winner_unique_id}\n"
        response += f"🆔 User ID: {winner_user_id}\n"
        response += f"👤 Username: {username_display}"
        
        if winner_username:
            response += f"\n\n✉️ Написать: @{winner_username}"
        
        safe_edit_message(chat_id, message_id, response, winner_keyboard())
    
    elif call.data == "admin_back":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещен!")
            return
            
        safe_edit_message(chat_id, message_id, "👑 Панель администратора:", admin_keyboard())
    
    # Участники розыгрыша iPhone
    elif call.data == "admin_iphone_participants":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещен!")
            return
            
        cursor.execute('''
        SELECT ip.user_id, u.username, ip.unique_id, ip.participation_date 
        FROM iphone_participants ip
        JOIN users u ON ip.user_id = u.user_id
        ORDER BY ip.participation_date DESC
        ''')
        participants = cursor.fetchall()
        
        if not participants:
            safe_edit_message(chat_id, message_id, "📱 Участников розыгрыша iPhone пока нет", admin_back_keyboard())
            return
            
        response = "📱 Участники розыгрыша iPhone:\n\n"
        for idx, participant in enumerate(participants, 1):
            participant_user_id, username, unique_id, date = participant
            username_display = f"@{username}" if username else "без username"
            response += f"{idx}. ID: {unique_id}\n"
            response += f"   Пользователь: {participant_user_id} ({username_display})\n"
            response += f"   Дата регистрации: {date}\n\n"
        
        response += f"📊 Всего участников: {len(participants)}"
        safe_edit_message(chat_id, message_id, response, admin_back_keyboard())
    
    # Рассылка сообщений
    elif call.data == "admin_broadcast":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещен!")
            return
        
        admin_states[user_id] = {"state": "waiting_broadcast"}
        safe_edit_message(
            chat_id, message_id,
            "✉️ Отправьте сообщение для рассылки:\n"
            "• Можно отправить текст\n"
            "• Или фото с подписью (текст под фото)\n"
            "• Или просто фото"
        )
    
    # Просмотр всех пользователей
    elif call.data == "admin_all_users":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещен!")
            return
            
        # Получаем всех пользователей из БД
        cursor.execute("SELECT user_id, username, tokens, bonus_received, created_at, last_seen FROM users ORDER BY user_id DESC")
        users = cursor.fetchall()
        
        if not users:
            safe_edit_message(chat_id, message_id, "❌ Пользователей пока нет", admin_back_keyboard())
            return
            
        # Форматируем список пользователей
        response = "👤 Все пользователи бота:\n\n"
        for user in users:
            user_id, username, tokens, bonus_received, created_at, last_seen = user
            username_display = f"@{username}" if username else "без username"
            bonus_status = "✅" if bonus_received else "❌"
            response += f"🆔 {user_id}\n👤 {username_display}\n🟡 Токены: {tokens}\n🎁 Бонус: {bonus_status}\n📅 Регистрация: {created_at}\n👀 Последний визит: {last_seen}\n\n"
        
        # Добавляем пагинацию, если пользователей много
        if len(response) > 3000:
            parts = [response[i:i+3000] for i in range(0, len(response), 3000)]
            for part in parts:
                bot.send_message(chat_id, part)
            safe_edit_message(chat_id, message_id, f"👤 Отправлено {len(users)} пользователей", admin_back_keyboard())
        else:
            safe_edit_message(chat_id, message_id, response, admin_back_keyboard())
    
    # Экспорт данных в Excel
    elif call.data == "admin_export_data":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещен!")
            return
            
        bot.answer_callback_query(call.id, "⏳ Формируем отчет...")
        
        try:
            filename = export_users_to_excel()
            if filename:
                # Проверяем существование файла перед отправкой
                if os.path.exists(filename) and os.path.getsize(filename) > 0:
                    with open(filename, 'rb') as file:
                        bot.send_document(
                            chat_id=chat_id,
                            document=file,
                            caption="📊 Полный отчет по пользователям",
                            reply_markup=admin_back_keyboard()
                        )
                    # Удаляем временный файл
                    os.remove(filename)
                else:
                    logger.error(f"Файл не создан или пуст: {filename}")
                    bot.send_message(chat_id, "❌ Ошибка: файл отчета не создан", reply_markup=admin_back_keyboard())
            else:
                logger.error("Функция export_users_to_excel вернула None")
                bot.send_message(chat_id, "❌ Ошибка при формировании отчета", reply_markup=admin_back_keyboard())
        except Exception as e:
            logger.error(f"Ошибка при экспорте данных: {str(e)}", exc_info=True)
            bot.send_message(chat_id, f"❌ Критическая ошибка при экспорте: {str(e)}", reply_markup=admin_back_keyboard())
    
    elif call.data == "confirm_broadcast":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещен!")
            return
            
        state_data = admin_states.get(user_id, {})
        if state_data.get("state") != "confirmation":
            bot.answer_callback_query(call.id, "❌ Нет данных для рассылки")
            return
        
        text = state_data.get("text", "")
        photo_id = state_data.get("photo_id", None)
        
        user_ids = get_all_users_except_admins()
        total = len(user_ids)
        success = 0
        errors = 0
        
        # Отправка тестового сообщения администратору
        try:
            if photo_id:
                bot.send_photo(chat_id, photo=photo_id, caption="✅ Тестовое сообщение перед рассылкой\n\n" + (text[:900] if text else ""))
            else:
                bot.send_message(chat_id, "✅ Тестовое сообщение перед рассылкой:\n\n" + text)
        except Exception as e:
            logger.error(f"Ошибка тестовой отправки: {str(e)}")
        
        # Отправка всем пользователям (кроме администраторов)
        for uid in user_ids:
            try:
                if photo_id:
                    bot.send_photo(uid, photo=photo_id, caption=text[:1024] if text else None)
                else:
                    bot.send_message(uid, text)
                success += 1
            except Exception as e:
                logger.error(f"Ошибка при отправке пользователю {uid}: {str(e)}")
                errors += 1
        
        # Удаление состояния
        if user_id in admin_states:
            del admin_states[user_id]
        
        # Редактирование сообщения с результатами
        safe_edit_message(
            chat_id, message_id,
            f"✅ Рассылка завершена!\n"
            f"• Всего получателей: {total}\n"
            f"• Успешно: {success}\n"
            f"• Ошибок: {errors}"
        )
    
    elif call.data == "cancel_broadcast":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещен!")
            return
            
        # Очищаем состояние
        if user_id in admin_states:
            del admin_states[user_id]
        
        # Возвращаемся в админ-панель
        safe_edit_message(
            chat_id, message_id,
            "👑 Панель администратора:",
            admin_keyboard()
        )
    
    # Редактор бота
    elif call.data == "bot_editor":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещен!")
            return
            
        edit_photo_message(chat_id, message_id, 'admin', "⚙️ Редактор бота\n\nВыберите что хотите изменить:", bot_editor_keyboard())
    
    elif call.data == "edit_texts":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещен!")
            return
            
        safe_edit_message(chat_id, message_id, "📝 Редактирование текстов\n\nВыберите текст для изменения:", edit_texts_keyboard())
    
    elif call.data == "edit_photos":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещен!")
            return
            
        safe_edit_message(chat_id, message_id, "📸 Редактирование фотографий\n\nВыберите фото для изменения:", edit_photos_keyboard())

    # Обработчики редактирования текстов
    elif call.data.startswith("edit_text_"):
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещен!")
            return
        
        text_type = call.data.replace("edit_text_", "")
        text_names = {
            "start": "стартового сообщения",
            "profile": "сообщения профиля", 
            "socials": "сообщения соцсетей",
            "support": "сообщения поддержки",
            "tokens": "сообщения о токенах",
            "giveaways": "сообщения розыгрышей",
            "iphone": "инструкции iPhone",
            "copyable": "формата копируемого текста"
        }
        
        admin_states[user_id] = {"state": "editing_text", "text_type": text_type}
        
        current_text = get_setting(f'{text_type}_message', "")
        if text_type == "iphone":
            current_text = get_setting('iphone_instruction', "")
        elif text_type == "copyable":
            current_text = get_setting('copyable_text', "")
        
        safe_edit_message(
            chat_id, message_id,
            f"📝 Редактирование {text_names.get(text_type, text_type)}\n\n"
            f"Текущий текст:\n{current_text[:500]}...\n\n"
            f"Отправьте новый текст:"
        )
    
    # Обработчики редактирования фото
    elif call.data.startswith("edit_photo_"):
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ Доступ запрещен!")
            return
        
        photo_type = call.data.replace("edit_photo_", "")
        photo_names = {
            "start": "стартового экрана",
            "profile": "профиля",
            "socials": "соцсетей", 
            "support": "поддержки",
            "admin": "админки",
            "iphone": "iPhone розыгрыша"
        }
        
        admin_states[user_id] = {"state": "editing_photo", "photo_type": photo_type}
        
        safe_edit_message(
            chat_id, message_id,
            f"📸 Редактирование фото {photo_names.get(photo_type, photo_type)}\n\n"
            f"Отправьте новое фото в чат.\n"
            f"Фото должно быть в формате JPG/PNG и весить не более 20MB."
        )

# Обработчик для сообщений администратора (рассылка)
@bot.message_handler(content_types=['text', 'photo'], 
                     func=lambda message: is_admin(message.from_user.id) and 
                     admin_states.get(message.from_user.id, {}).get("state") == "waiting_broadcast")
def handle_broadcast_input(message):
    user_id = message.from_user.id
    state_data = admin_states.get(user_id, {})
    
    # Обработка фото
    if message.photo:
        # Берем последнее (самое качественное) фото
        file_id = message.photo[-1].file_id
        caption = message.caption if message.caption else ""
        
        # Сохраняем данные
        state_data.update({
            "state": "confirmation",
            "text": caption,
            "photo_id": file_id
        })
        admin_states[user_id] = state_data
        
        # Формируем предпросмотр
        preview = "📸 *Фото с подписью:*\n"
        if caption:
            preview += f"{caption}\n"
        preview += f"\nПолучателей: {len(get_all_users_except_admins())}"
        
        # Отправляем подтверждение
        bot.send_photo(
            message.chat.id, 
            photo=file_id, 
            caption=preview,
            reply_markup=broadcast_confirmation_keyboard(),
            parse_mode="Markdown"
        )
    
    # Обработка текста
    elif message.text:
        # Сохраняем текст
        state_data.update({
            "state": "confirmation",
            "text": message.text,
            "photo_id": None
        })
        admin_states[user_id] = state_data
        
        # Формируем предпросмотр
        preview = f"✉️ *Текст сообщения:*\n{message.text}\n\n"
        preview += f"Получателей: {len(get_all_users_except_admins())}"
        
        # Отправляем подтверждение
        bot.reply_to(
            message,
            preview,
            reply_markup=broadcast_confirmation_keyboard(),
            parse_mode="Markdown"
        )

# Обработчик для редактирования текстов
@bot.message_handler(content_types=['text'], 
                     func=lambda message: is_admin(message.from_user.id) and 
                     admin_states.get(message.from_user.id, {}).get("state") == "editing_text")
def handle_text_editing(message):
    user_id = message.from_user.id
    state_data = admin_states.get(user_id, {})
    text_type = state_data.get("text_type")
    
    if not text_type:
        return
    
    new_text = message.text
    
    # Обработка формата копируемого текста
    if text_type == "copyable":
        setting_name = 'copyable_text'
        # Проверяем наличие плейсхолдера
        if "{text}" not in new_text:
            bot.reply_to(message, "❌ Формат должен содержать плейсхолдер {text}!")
            return
    else:
        setting_name = f'{text_type}_message'
        if text_type == "iphone":
            setting_name = 'iphone_instruction'
    
    if update_setting(setting_name, new_text):
        bot.reply_to(message, f"✅ Текст {text_type} успешно обновлен!", reply_markup=edit_texts_keyboard())
    else:
        bot.reply_to(message, f"❌ Ошибка при обновлении текста {text_type}")
    
    # Очищаем состояние
    if user_id in admin_states:
        del admin_states[user_id]

# Обработчик для редактирования фото
@bot.message_handler(content_types=['photo'], 
                     func=lambda message: is_admin(message.from_user.id) and 
                     admin_states.get(message.from_user.id, {}).get("state") == "editing_photo")
def handle_photo_editing(message):
    user_id = message.from_user.id
    state_data = admin_states.get(user_id, {})
    photo_type = state_data.get("photo_type")
    
    if not photo_type:
        return
    
    try:
        # Получаем информацию о файле
        file_info = bot.get_file(message.photo[-1].file_id)
        
        # Скачиваем файл
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Определяем расширение файла
        file_extension = file_info.file_path.split('.')[-1]
        new_filename = f"{photo_type}.{file_extension}"
        
        # Сохраняем файл
        with open(new_filename, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        # Обновляем настройки
        if update_setting(f'photo_{photo_type}', new_filename):
            bot.reply_to(message, f"✅ Фото {photo_type} успешно обновлено!", reply_markup=edit_photos_keyboard())
        else:
            bot.reply_to(message, f"❌ Ошибка при обновлении фото {photo_type}")
            
    except Exception as e:
        logger.error(f"Ошибка при сохранении фото {photo_type}: {str(e)}")
        bot.reply_to(message, f"❌ Ошибка при сохранении фото: {str(e)}")
    
    # Очищаем состояние
    if user_id in admin_states:
        del admin_states[user_id]

# Запуск бота
if __name__ == "__main__":
    logger.info("Бот успешно запущен!")
    logger.info(f"Администраторы: {ADMINS}")
    bot.infinity_polling()
