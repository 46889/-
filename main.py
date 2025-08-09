import requests
import textwrap
import re
import logging
import json
import base64
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
API_KEY = "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"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "mistralai/mistral-7b-instruct"
TOKEN = "7951956501:AAH0D0oMdiMXUnhCtvWavrrOCU2zqWUA69I"
ADMIN_ID = 1478525032  # Замените на свой ID

# Состояния разговора
MAIN_MENU, AWAITING_TOPIC, PLAN_CREATED, POST_STUDY_CHOICE, TEST_IN_PROGRESS, POST_TEST_CHOICE, HISTORY_VIEW = range(7)

class Database:
    def __init__(self, state_data=None):
        if state_data:
            self.data = json.loads(base64.b64decode(state_data).decode('utf-8'))
            logger.info("Database restored from backup")
        else:
            self.data = {"users": {}, "stats": {"total_users": 0, "total_searches": 0}}
            logger.info("New database created")
    
    def export_state(self):
        """Экспортирует состояние базы данных в base64 строку"""
        return base64.b64encode(json.dumps(self.data).encode('utf-8')).decode('utf-8')
    
    def add_user(self, user_id, username=None):
        user_id = str(user_id)
        if user_id not in self.data["users"]:
            self.data["users"][user_id] = {
                "username": username,
                "join_date": datetime.now().isoformat(),
                "searches": [],
                "history": [],
                "total_score": 0,
                "tests_taken": 0
            }
            self.data["stats"]["total_users"] += 1
            logger.info(f"New user added: {user_id}")
    
    def add_search(self, user_id, topic):
        user_id = str(user_id)
        if user_id in self.data["users"]:
            self.data["users"][user_id]["searches"].append({
                "topic": topic,
                "date": datetime.now().isoformat()
            })
            self.data["stats"]["total_searches"] += 1
            logger.info(f"Search added for {user_id}: {topic}")
    
    def add_to_history(self, user_id, topic, plan, score=None):
        user_id = str(user_id)
        if user_id in self.data["users"]:
            history_item = {
                "topic": topic,
                "plan": plan,
                "date": datetime.now().isoformat(),
                "score": score
            }
            self.data["users"][user_id]["history"].append(history_item)
            if score is not None:
                self.data["users"][user_id]["total_score"] += score
                self.data["users"][user_id]["tests_taken"] += 1
            logger.info(f"History added for {user_id}: {topic} ({score}%)")
    
    def get_user_history(self, user_id):
        user_id = str(user_id)
        return self.data["users"].get(user_id, {}).get("history", [])
    
    def get_all_users(self):
        return self.data["users"]
    
    def get_stats(self):
        return self.data["stats"]
    
    def clear_database(self):
        """Очищает базу данных"""
        self.data = {"users": {}, "stats": {"total_users": 0, "total_searches": 0}}
        logger.info("Database cleared")

# Инициализация базы данных
db = Database()

class StudyState:
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.current_state = MAIN_MENU
        self.study_plan = []
        self.current_step = 0
        self.current_topic = ""
        self.test_questions = []
        self.current_question_index = 0
        self.test_score = 0
        self.user_answers = []
        self.from_history = False

def get_time():
    return datetime.now().strftime("%H:%M")

def clean_math_symbols(text):
    """Упрощает математические выражения для текстового отображения"""
    text = re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', r'\1/\2', text)
    text = re.sub(r'\\[a-zA-Z]+\{?', '', text)
    text = re.sub(r'\{|\}', '', text)
    return text.strip()

def format_response(text):
    """Форматирует ответ для отправки пользователю"""
    cleaned = clean_math_symbols(text)
    cleaned = re.sub(r'\*\*|__', '', cleaned)
    wrapped = textwrap.fill(cleaned, width=100)
    return f"{get_time()} AI: {wrapped}"

def generate_plan(topic):
    fallback_plan = [
        {"title": f"Введение в {topic}"},
        {"title": "Основные понятия и определения"},
        {"title": "Ключевые методы решения"},
        {"title": "Практическое применение"},
        {"title": "Закрепление материала"}
    ]
    
    try:
        messages = [{
            "role": "system",
            "content": "Ты учитель. Создай учебный план из 5 шагов по заданной теме. "
                       "Каждый шаг должен быть кратко озаглавлен. Выведи только шаги в формате: "
                       "1. [Название шага 1]\n2. [Название шага 2]\n...\n5. [Название шага 5]"
        }, {
            "role": "user",
            "content": f"Создай учебный план из 5 шагов по теме: '{topic}'"
        }]
        
        response = send_api_request(messages, max_tokens=300)
        if response.startswith("⚠️"):
            return fallback_plan
            
        steps = []
        for line in response.split('\n'):
            if line.strip() == '':
                continue
            match = re.match(r'(\d+)\.\s*(.+)', line)
            if match:
                step_title = match.group(2).strip()
                steps.append({"title": clean_math_symbols(step_title)})
        
        return steps[:5] if steps else fallback_plan
    except Exception:
        return fallback_plan

def send_api_request(messages, max_tokens=200):
    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://localhost",
            "X-Title": "Math Tutor"
        }
        
        payload = {
            "model": MODEL,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": max_tokens
        }
        
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        return clean_math_symbols(data["choices"][0]["message"]["content"])
    
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        return f"⚠️ Ошибка соединения: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return f"⚠️ Ошибка обработки: {str(e)}"

def generate_test_questions(topic, count=3):
    try:
        messages = [{
            "role": "system",
            "content": f"Создай {count} тестовых вопроса по теме '{topic}' с вариантами ответов. "
                       "Формат каждого вопроса:\n"
                       "ВОПРОС [номер]: [текст вопроса]\n"
                       "A) [вариант A]\nB) [вариант B]\nC) [вариант C]\nD) [вариант D]\n"
                       "ОТВЕТ: [буква правильного варианта]\n\n"
                       "Избегай разметки, используй только буквы для вариантов."
        }]
        
        messages.append({
            "role": "user", 
            "content": f"Создай {count} разнообразных тестовых вопроса по теме '{topic}'"
        })
        
        response = send_api_request(messages, max_tokens=800)
        return parse_test_questions(response) if not response.startswith("⚠️") else []
    except Exception:
        return []

def parse_test_questions(text):
    questions = []
    pattern = r'ВОПРОС\s*\d+:\s*(.+?)\s*A\)\s*(.+?)\s*B\)\s*(.+?)\s*C\)\s*(.+?)\s*D\)\s*(.+?)\s*ОТВЕТ:\s*([A-D])'
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
    
    for match in matches:
        questions.append({
            "text": clean_math_symbols(match[0].strip()),
            "options": {
                "A": clean_math_symbols(match[1].strip()),
                "B": clean_math_symbols(match[2].strip()),
                "C": clean_math_symbols(match[3].strip()),
                "D": clean_math_symbols(match[4].strip())
            },
            "correct": match[5].upper().strip()
        })
    
    return questions

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    db.add_user(user.id, user.username)
    
    context.user_data['state'] = StudyState()
    context.user_data['messages'] = [{
        "role": "system",
        "content": "Ты учитель. Объясняй темы кратко и понятно на русском языке. "
                   "Используй простые примеры. Избегай сложной разметки."
    }]
    
    keyboard = [
        [InlineKeyboardButton("📚 Новое обучение", callback_data="new_learning")],
        [InlineKeyboardButton("📖 Моя история", callback_data="my_history")],
        [InlineKeyboardButton("ℹ️ О боте", callback_data="about")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎓 Добро пожаловать в учебного бота!\n\nВыберите действие:",
        reply_markup=reply_markup
    )
    return MAIN_MENU

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    state = context.user_data['state']
    
    if query.data == "new_learning":
        state.from_history = False
        await query.edit_message_text("📝 Введите тему, которую хотите изучить:")
        return AWAITING_TOPIC
    
    elif query.data == "my_history":
        return await show_history(query, context)
    
    elif query.data == "about":
        about_text = (
            "🤖 Учебный бот v3.0\n\n"
            "📚 Создаю планы обучения\n"
            "🧪 Провожу тесты\n"
            "📊 Сохраняю историю\n"
            "💾 Данные сохраняются в памяти\n\n"
            "Выберите 'Новое обучение' для начала!"
        )
        
        keyboard = [[InlineKeyboardButton("← Главное меню", callback_data="main_menu")]]
        await query.edit_message_text(about_text, reply_markup=InlineKeyboardMarkup(keyboard))
        return MAIN_MENU
    
    elif query.data == "main_menu":
        return await start_from_callback(query, context)

async def start_from_callback(query, context):
    keyboard = [
        [InlineKeyboardButton("📚 Новое обучение", callback_data="new_learning")],
        [InlineKeyboardButton("📖 Моя история", callback_data="my_history")],
        [InlineKeyboardButton("ℹ️ О боте", callback_data="about")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("🎓 Главное меню\n\nВыберите действие:", reply_markup=reply_markup)
    return MAIN_MENU

async def show_history(query, context):
    user_id = query.from_user.id
    history = db.get_user_history(user_id)
    
    if not history:
        await query.edit_message_text("📖 История обучения пуста\n\nНачните новое обучение!")
        keyboard = [[InlineKeyboardButton("← Главное меню", callback_data="main_menu")]]
        await context.bot.send_message(
            chat_id=user_id, 
            text="Выберите действие:", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return MAIN_MENU
    
    text = "📖 Ваша история обучения:\n\n"
    keyboard = []
    
    recent_history = history[-10:]
    for i, item in enumerate(recent_history):
        date = datetime.fromisoformat(item["date"]).strftime("%d.%m")
        score_text = f" ({item['score']}%)" if item.get('score') else ""
        text += f"{i+1}. {item['topic']} - {date}{score_text}\n"
        keyboard.append([InlineKeyboardButton(
            f"{i+1}. {item['topic'][:25]}...", 
            callback_data=f"history_{len(history)-10+i}"
        )])
    
    keyboard.append([InlineKeyboardButton("← Главное меню", callback_data="main_menu")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return HISTORY_VIEW

async def handle_history_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == "main_menu":
        return await start_from_callback(query, context)
    
    if query.data.startswith("history_"):
        index = int(query.data.split("_")[1])
        user_id = query.from_user.id
        history = db.get_user_history(user_id)
        
        if 0 <= index < len(history):
            item = history[index]
            state = context.user_data['state']
            state.current_topic = item["topic"]
            state.study_plan = item["plan"]
            state.from_history = True
            
            await query.edit_message_text(f"📚 Возвращаемся к теме: {item['topic']}\n\nПлан обучения загружен!")
            
            keyboard = [
                [InlineKeyboardButton("Начать обучение →", callback_data="start_learning")],
                [InlineKeyboardButton("← Назад к истории", callback_data="back_to_history")]
            ]
            await context.bot.send_message(
                chat_id=user_id, 
                text="Выберите действие:", 
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return PLAN_CREATED
    
    return HISTORY_VIEW

async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    state = context.user_data['state']
    user_input = update.message.text.strip()
    user_id = update.effective_user.id
    
    if not user_input:
        await update.message.reply_text("⚠️ Пожалуйста, введите тему для изучения")
        return AWAITING_TOPIC
    
    state.current_topic = user_input
    db.add_search(user_id, user_input)
    
    await update.message.reply_text(f"🌀 Генерирую план по теме '{user_input}'...")
    state.study_plan = generate_plan(user_input)
    
    plan_text = f"📚 План: '{user_input}'\n\n" + "\n".join(
        [f"{i+1}. {item['title']}" for i, item in enumerate(state.study_plan)]
    )
    
    keyboard = []
    for i in range(len(state.study_plan)):
        if i % 3 == 0:
            keyboard.append([])
        keyboard[-1].append(InlineKeyboardButton(f"{i+1}", callback_data=f"step_{i}"))
    
    keyboard.append([InlineKeyboardButton("Начать обучение →", callback_data="start_learning")])
    keyboard.append([InlineKeyboardButton("← Главное меню", callback_data="main_menu")])
    
    await update.message.reply_text(
        plan_text, 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PLAN_CREATED

async def handle_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    state = context.user_data['state']
    messages = context.user_data['messages']
    
    if query.data == "main_menu":
        return await start_from_callback(query, context)
    elif query.data == "back_to_history":
        return await show_history(query, context)
    elif query.data == "start_learning":
        state.current_step = 0
    elif query.data == "next":
        state.current_step += 1
        if state.current_step >= len(state.study_plan):
            return await handle_end_plan(query, context)
    elif query.data == "finish_plan":
        return await handle_end_plan(query, context)
    elif query.data.startswith("step_"):
        state.current_step = int(query.data.split("_")[1])
    
    current_item = state.study_plan[state.current_step]
    await query.edit_message_text(f"🔍 Пункт {state.current_step+1}: {current_item['title']}")
    
    try:
        prompt = (
            f"Объясни кратко и понятно тему: '{current_item['title']}' "
            f"по предмету '{state.current_topic}'. Используй простые примеры."
        )
        
        messages.append({"role": "user", "content": prompt})
        content = send_api_request(messages, max_tokens=300)
        messages.append({"role": "assistant", "content": content})
        
        await context.bot.send_message(
            chat_id=query.from_user.id, 
            text=format_response(content)
        )
    except Exception as e:
        logger.error(f"Error in explanation: {str(e)}")
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="⚠️ Не удалось получить объяснение. Попробуйте следующий шаг."
        )
    
    keyboard = []
    if state.current_step < len(state.study_plan) - 1:
        keyboard.append([InlineKeyboardButton("Следующий →", callback_data="next")])
    else:
        keyboard.append([InlineKeyboardButton("Завершить", callback_data="finish_plan")])
    
    keyboard.append([InlineKeyboardButton("← Главное меню", callback_data="main_menu")])
    await context.bot.send_message(
        chat_id=query.from_user.id, 
        text="📝 Навигация:", 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PLAN_CREATED

async def handle_end_plan(update, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(update, Update):
        user_id = update.message.from_user.id
    else:
        user_id = update.from_user.id
        await update.answer()
    
    state = context.user_data['state']
    
    keyboard = [
        [InlineKeyboardButton("🧪 Пройти тест", callback_data="take_test")],
        [InlineKeyboardButton("📚 Новая тема", callback_data="new_learning")],
        [InlineKeyboardButton("← Главное меню", callback_data="main_menu")]
    ]
    await context.bot.send_message(
        chat_id=user_id, 
        text="🎉 План завершен! Пройдите тест?", 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return POST_STUDY_CHOICE

async def handle_test_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    state = context.user_data['state']
    
    if query.data == "main_menu":
        return await start_from_callback(query, context)
    elif query.data == "new_learning":
        state.reset()
        await query.edit_message_text("📝 Введите новую тему:")
        return AWAITING_TOPIC
    elif query.data == "take_test":
        await query.edit_message_text("🌀 Создаю тест...")
        state.test_questions = generate_test_questions(state.current_topic)
        
        if state.test_questions:
            state.current_question_index = 0
            state.test_score = 0
            state.user_answers = []
            await show_question(context, state, query.from_user.id)
            return TEST_IN_PROGRESS
        else:
            await query.edit_message_text("⚠️ Не удалось создать тест")
            return await handle_end_plan(query, context)

async def show_question(context, state, user_id):
    if state.current_question_index >= len(state.test_questions):
        return await finish_test(context, state, user_id)
    
    question = state.test_questions[state.current_question_index]
    question_text = f"📝 Вопрос {state.current_question_index+1}/{len(state.test_questions)}:\n\n{question['text']}"
    
    keyboard = []
    for option in ['A', 'B', 'C', 'D']:
        keyboard.append([InlineKeyboardButton(
            f"{option}) {question['options'][option]}", 
            callback_data=f"answer_{option}"
        )])
    
    await context.bot.send_message(
        chat_id=user_id, 
        text=question_text, 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_test_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    state = context.user_data['state']
    
    user_answer = query.data.split("_")[1]
    current_question = state.test_questions[state.current_question_index]
    
    state.user_answers.append({
        "question": current_question["text"],
        "user_answer": user_answer,
        "correct_answer": current_question["correct"]
    })
    
    if user_answer == current_question["correct"]:
        response_text = "✅ Правильно!"
        state.test_score += 1
    else:
        response_text = f"❌ Неверно. Правильный ответ: {current_question['correct']}"
    
    await query.edit_message_text(response_text)
    state.current_question_index += 1
    
    if state.current_question_index < len(state.test_questions):
        await show_question(context, state, query.from_user.id)
        return TEST_IN_PROGRESS
    else:
        return await finish_test(context, state, query.from_user.id)

async def finish_test(context, state, user_id):
    score_percent = int((state.test_score / len(state.test_questions)) * 100) if state.test_questions else 0
    
    result_text = f"📊 Результат: {state.test_score}/{len(state.test_questions)} ({score_percent}%)"
    if state.test_score == len(state.test_questions):
        result_text += "\n🎉 Отлично!"
    elif score_percent >= 50:
        result_text += "\n👍 Хорошо!"
    else:
        result_text += "\n📖 Стоит повторить материал"
    
    if not state.from_history:
        db.add_to_history(user_id, state.current_topic, state.study_plan, score_percent)
    
    keyboard = [
        [InlineKeyboardButton("🔄 Повторить тест", callback_data="retry_test")],
        [InlineKeyboardButton("📚 Новая тема", callback_data="new_learning")],
        [InlineKeyboardButton("← Главное меню", callback_data="main_menu")]
    ]
    await context.bot.send_message(
        chat_id=user_id, 
        text=result_text, 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return POST_TEST_CHOICE

async def handle_post_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    state = context.user_data['state']
    
    if query.data == "main_menu":
        return await start_from_callback(query, context)
    elif query.data == "new_learning":
        state.reset()
        await query.edit_message_text("📝 Введите новую тему:")
        return AWAITING_TOPIC
    elif query.data == "retry_test":
        state.current_question_index = 0
        state.test_score = 0
        state.user_answers = []
        await show_question(context, state, query.from_user.id)
        return TEST_IN_PROGRESS

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель администратора"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    stats = db.get_stats()
    all_users = db.get_all_users()
    
    text = "👨‍💼 АДМИН ПАНЕЛЬ\n\n"
    text += f"📊 Общая статистика:\n"
    text += f"👥 Пользователей: {stats['total_users']}\n"
    text += f"🔍 Поисков: {stats['total_searches']}\n\n"
    
    text += "👥 Все пользователи:\n"
    for user_id, data in all_users.items():
        username = data.get('username', 'Без ника')
        username_display = f"@{username}" if username and username != 'Без ника' else f"ID: {user_id}"
        tests_count = data.get('tests_taken', 0)
        searches_count = len(data.get('searches', []))
        join_date = datetime.fromisoformat(data['join_date']).strftime("%d.%m.%Y")
        
        avg_score = data.get('total_score', 0) / tests_count if tests_count > 0 else 0
        
        text += f"• {username_display}\n"
        text += f"  📅 Регистрация: {join_date}\n"
        text += f"  🔍 Поисков: {searches_count}, 🧪 Тестов: {tests_count}\n"
        if tests_count > 0:
            text += f"  📊 Средний балл: {avg_score:.1f}%\n"
        text += "\n"
    
    if not all_users:
        text += "Пользователей пока нет.\n\n"
    
    text += "🔍 Последние поиски:\n"
    recent_searches = []
    for user_id, data in all_users.items():
        username = data.get('username', 'Без ника')
        username_display = f"@{username}" if username and username != 'Без ника' else f"ID: {user_id}"
        for search in data.get('searches', [])[-3:]:
            recent_searches.append((username_display, search['topic'], search['date']))
    
    recent_searches.sort(key=lambda x: x[2], reverse=True)
    
    for username_display, topic, date in recent_searches[:10]:
        date_str = datetime.fromisoformat(date).strftime("%d.%m %H:%M")
        text += f"• {username_display}: {topic[:25]}... ({date_str})\n"
    
    if not recent_searches:
        text += "Поисков пока нет.\n"
    
    await update.message.reply_text(text)

async def admin_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создание резервной копии базы данных"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    try:
        state_data = db.export_state()
        await update.message.reply_text(
            f"💾 Резервная копия базы данных (base64):\n\n"
            f"<code>{state_data}</code>\n\n"
            "Используйте /restore для восстановления",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Ошибка создания резервной копии: {str(e)}")

async def admin_restore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Восстановление базы данных из резервной копии"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    if not context.args:
        await update.message.reply_text("ℹ️ Использование: /restore <base64_data>")
        return
    
    try:
        global db
        state_data = ' '.join(context.args)
        db = Database(state_data)
        await update.message.reply_text("✅ База данных успешно восстановлена из резервной копии!")
        logger.info(f"Database restored. Users: {db.get_stats()['total_users']}")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Ошибка восстановления: {str(e)}")
        logger.error(f"Restore error: {str(e)}")

async def admin_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистка базы данных"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    db.clear_database()
    await update.message.reply_text("✅ База данных полностью очищена!")
    logger.info("Database cleared by admin")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Действие отменено")
    return ConversationHandler.END

def main() -> None:
    application = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [CallbackQueryHandler(handle_main_menu)],
            AWAITING_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic),
                CallbackQueryHandler(handle_main_menu)
            ],
            PLAN_CREATED: [CallbackQueryHandler(handle_plan)],
            POST_STUDY_CHOICE: [CallbackQueryHandler(handle_test_choice)],
            TEST_IN_PROGRESS: [CallbackQueryHandler(handle_test_answer)],
            POST_TEST_CHOICE: [CallbackQueryHandler(handle_post_test)],
            HISTORY_VIEW: [CallbackQueryHandler(handle_history_selection)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('admin', admin_panel))
    application.add_handler(CommandHandler('backup', admin_backup))
    application.add_handler(CommandHandler('restore', admin_restore))
    application.add_handler(CommandHandler('clear_db', admin_clear))
    application.add_handler(CommandHandler('start', start))
    
    logger.info("Бот запущен")
    logger.info(f"Текущее состояние базы: Пользователей: {db.get_stats()['total_users']}, Поисков: {db.get_stats()['total_searches']}")
    
    application.run_polling()

if __name__ == "__main__":
    main()
