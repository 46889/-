import requests
import textwrap
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, filters

# Конфигурация
API_KEY = "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"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "deepseek/deepseek-chat"
TOKEN = "7951956501:AAH0D0oMdiMXUnhCtvWavrrOCU2zqWUA69I"
ADMIN_ID = 123456789  # Замените на свой ID

# Состояния разговора
MAIN_MENU, AWAITING_TOPIC, PLAN_CREATED, POST_STUDY_CHOICE, TEST_IN_PROGRESS, POST_TEST_CHOICE, HISTORY_VIEW = range(7)

class Database:
    def __init__(self):
        self.data = {"users": {}, "stats": {"total_users": 0, "total_searches": 0}}
    
    def save_data(self):
        # Данные хранятся только в памяти
        pass
    
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
            self.save_data()
    
    def add_search(self, user_id, topic):
        user_id = str(user_id)
        self.data["users"][user_id]["searches"].append({
            "topic": topic,
            "date": datetime.now().isoformat()
        })
        self.data["stats"]["total_searches"] += 1
        self.save_data()
    
    def add_to_history(self, user_id, topic, plan, score=None):
        user_id = str(user_id)
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
        self.save_data()
    
    def get_user_history(self, user_id):
        user_id = str(user_id)
        return self.data["users"].get(user_id, {}).get("history", [])
    
    def get_all_users(self):
        return self.data["users"]
    
    def get_stats(self):
        return self.data["stats"]

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

def format_response(text):
    cleaned = text.replace("**", "").replace("__", "").replace("\\", "")
    wrapped = textwrap.fill(cleaned, width=100)
    return f"{get_time()} AI: {wrapped}"

def generate_plan(topic):
    messages = [{
        "role": "system",
        "content": "Ты учитель. Создай учебный план из 5 шагов по заданной теме. Каждый шаг должен быть кратко озаглавлен. Выведи только шаги в формате: 1. [Название шага 1]\n2. [Название шага 2]\n...\n5. [Название шага 5]"
    }, {
        "role": "user",
        "content": f"Создай учебный план из 5 шагов по теме: '{topic}'"
    }]
    
    response = send_api_request(messages, max_tokens=300)
    steps = []
    
    for line in response.split('\n'):
        if line.strip() == '':
            continue
        match = re.match(r'(\d+)\.\s*(.+)', line)
        if match:
            step_title = match.group(2).strip()
            steps.append({"title": step_title})
    
    if len(steps) < 3:
        return [
            {"title": f"Введение в {topic}"},
            {"title": "Основные понятия и определения"},
            {"title": "Ключевые методы решения"},
            {"title": "Практическое применение"},
            {"title": "Закрепление материала"}
        ]
    return steps[:5]

def send_api_request(messages, max_tokens=200):
    try:
        response = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://localhost",
                "X-Title": "Math Tutor"
            },
            json={
                "model": MODEL,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": max_tokens
            },
            timeout=45
        )
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            error = response.json().get("error", {}).get("message", "Неизвестная ошибка API")
            return f"⚠️ Ошибка API: {error}"
            
    except Exception as e:
        return f"⚠️ Ошибка соединения: {str(e)}"

def generate_test_questions(topic, count=3):
    messages = [{
        "role": "system",
        "content": f"Создай {count} тестовых вопроса по теме '{topic}' с вариантами ответов. Формат каждого вопроса:\nВОПРОС [номер]: [текст вопроса]\nA) [вариант A]\nB) [вариант B]\nC) [вариант C]\nD) [вариант D]\nОТВЕТ: [буква правильного варианта]\n\nИзбегай разметки, используй только буквы для вариантов."
    }]
    
    prompt = f"Создай {count} разнообразных тестовых вопроса по теме '{topic}' с 4 вариантами ответов каждый."
    messages.append({"role": "user", "content": prompt})
    
    response = send_api_request(messages, max_tokens=800)
    return response

def parse_test_questions(text):
    questions = []
    pattern = r'ВОПРОС\s*\d+:\s*(.+?)\s*A\)\s*(.+?)\s*B\)\s*(.+?)\s*C\)\s*(.+?)\s*D\)\s*(.+?)\s*ОТВЕТ:\s*([A-D])'
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
    
    for match in matches:
        question = {
            "text": match[0].strip(),
            "options": {
                "A": match[1].strip(),
                "B": match[2].strip(),
                "C": match[3].strip(),
                "D": match[4].strip()
            },
            "correct": match[5].upper().strip()
        }
        questions.append(question)
    
    return questions

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    db.add_user(user_id, username)
    
    context.user_data['state'] = StudyState()
    context.user_data['messages'] = [{
        "role": "system",
        "content": "Ты учитель. Объясняй темы кратко и понятно на русском языке максимум 200 слов. Используй простые примеры. Избегай разметки."
    }]
    
    keyboard = [
        [InlineKeyboardButton("📚 Новое обучение", callback_data="new_learning")],
        [InlineKeyboardButton("📖 Моя история", callback_data="my_history")],
        [InlineKeyboardButton("ℹ️ О боте", callback_data="about")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = "🎓 Добро пожаловать в учебного бота!\n\nВыберите действие:"
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
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
        about_text = "🤖 Учебный бот v2.0\n\n📚 Создаю планы обучения\n🧪 Провожу тесты\n📊 Сохраняю историю\n\nВыберите 'Новое обучение' для начала!"
        
        keyboard = [[InlineKeyboardButton("← Главное меню", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(about_text, reply_markup=reply_markup)
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
    
    welcome_text = "🎓 Главное меню\n\nВыберите действие:"
    await query.edit_message_text(welcome_text, reply_markup=reply_markup)
    return MAIN_MENU

async def show_history(query, context):
    user_id = query.from_user.id
    history = db.get_user_history(user_id)
    
    if not history:
        await query.edit_message_text("📖 История обучения пуста\n\nНачните новое обучение!")
        
        keyboard = [[InlineKeyboardButton("← Главное меню", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=user_id, text="Выберите действие:", reply_markup=reply_markup)
        return MAIN_MENU
    
    text = "📖 Ваша история обучения:\n\n"
    keyboard = []
    
    for i, item in enumerate(history[-10:]):  # Показываем последние 10
        date = datetime.fromisoformat(item["date"]).strftime("%d.%m")
        score_text = f" ({item['score']}%)" if item.get('score') else ""
        text += f"{i+1}. {item['topic']} - {date}{score_text}\n"
        keyboard.append([InlineKeyboardButton(f"{i+1}. {item['topic'][:25]}...", callback_data=f"history_{i}")])
    
    keyboard.append([InlineKeyboardButton("← Главное меню", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)
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
        
        if index < len(history):
            item = history[-(10-index)]  # Берем из последних 10
            state = context.user_data['state']
            state.current_topic = item["topic"]
            state.study_plan = item["plan"]
            state.from_history = True
            
            await query.edit_message_text(f"📚 Возвращаемся к теме: {item['topic']}\n\nПлан обучения загружен!")
            
            keyboard = [[InlineKeyboardButton("Начать обучение →", callback_data="start_learning")]]
            keyboard.append([InlineKeyboardButton("← Назад к истории", callback_data="back_to_history")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(chat_id=user_id, text="Выберите действие:", reply_markup=reply_markup)
            return PLAN_CREATED
    
    return HISTORY_VIEW

async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    state = context.user_data['state']
    user_input = update.message.text.strip()
    user_id = update.effective_user.id
    
    state.current_topic = user_input
    db.add_search(user_id, user_input)
    
    await update.message.reply_text(f"🌀 Генерирую план по теме '{user_input}'...")
    
    state.study_plan = generate_plan(user_input)
    state.current_state = PLAN_CREATED
    
    plan_text = f"📚 План: '{user_input}'\n\n"
    plan_text += "\n".join([f"{i+1}. {item['title']}" for i, item in enumerate(state.study_plan)])
    
    keyboard = []
    row = []
    for i, item in enumerate(state.study_plan):
        row.append(InlineKeyboardButton(f"{i+1}", callback_data=f"step_{i}"))
        if len(row) == 5 or i == len(state.study_plan) - 1:
            keyboard.append(row)
            row = []
    
    keyboard.append([InlineKeyboardButton("Начать обучение →", callback_data="start_learning")])
    keyboard.append([InlineKeyboardButton("← Главное меню", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(plan_text, reply_markup=reply_markup)
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
    
    prompt = f"Объясни кратко и понятно тему: '{current_item['title']}' по предмету '{state.current_topic}'. Максимум 200 слов, простые примеры."
    
    messages.append({"role": "user", "content": prompt})
    content = send_api_request(messages, max_tokens=200)
    messages.append({"role": "assistant", "content": content})
    
    await context.bot.send_message(chat_id=query.from_user.id, text=format_response(content))
    
    keyboard = []
    if state.current_step < len(state.study_plan) - 1:
        keyboard.append([InlineKeyboardButton("Следующий →", callback_data="next")])
    else:
        keyboard.append([InlineKeyboardButton("Завершить", callback_data="finish_plan")])
    
    keyboard.append([InlineKeyboardButton("← Главное меню", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(chat_id=query.from_user.id, text="📝 Навигация:", reply_markup=reply_markup)
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
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(chat_id=user_id, text="🎉 План завершен! Пройдите тест?", reply_markup=reply_markup)
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
        test_content = generate_test_questions(state.current_topic)
        state.test_questions = parse_test_questions(test_content)
        
        if state.test_questions:
            state.current_question_index = 0
            state.test_score = 0
            state.user_answers = []
            await show_question(context, state, query.from_user.id)
            return TEST_IN_PROGRESS
        else:
            await query.edit_message_text("⚠️ Ошибка создания теста")
            return await handle_end_plan(query, context)

async def show_question(context, state, user_id):
    if state.current_question_index >= len(state.test_questions):
        return await finish_test(context, state, user_id)
    
    question = state.test_questions[state.current_question_index]
    question_text = f"📝 Вопрос {state.current_question_index+1}/{len(state.test_questions)}:\n\n{question['text']}"
    
    keyboard = []
    for option in ['A', 'B', 'C', 'D']:
        keyboard.append([InlineKeyboardButton(f"{option}) {question['options'][option]}", callback_data=f"answer_{option}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=user_id, text=question_text, reply_markup=reply_markup)

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
    score_percent = int((state.test_score / len(state.test_questions)) * 100)
    result_text = f"📊 Результат: {state.test_score}/{len(state.test_questions)} ({score_percent}%)"
    
    if state.test_score == len(state.test_questions):
        result_text += "\n🎉 Отлично!"
    elif state.test_score >= len(state.test_questions) / 2:
        result_text += "\n👍 Хорошо!"
    else:
        result_text += "\n📖 Стоит повторить"
    
    if not state.from_history:
        db.add_to_history(user_id, state.current_topic, state.study_plan, score_percent)
    
    keyboard = [
        [InlineKeyboardButton("🔄 Повторить тест", callback_data="retry_test")],
        [InlineKeyboardButton("📚 Новая тема", callback_data="new_learning")],
        [InlineKeyboardButton("← Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(chat_id=user_id, text=result_text, reply_markup=reply_markup)
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
        username_display = f"@{username}" if username != 'Без ника' else f"ID: {user_id}"
        tests_count = data.get('tests_taken', 0)
        searches_count = len(data.get('searches', []))
        join_date = datetime.fromisoformat(data['join_date']).strftime("%d.%m.%Y")
        
        avg_score = 0
        if tests_count > 0:
            avg_score = data.get('total_score', 0) / tests_count
        
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
        username_display = f"@{username}" if username != 'Без ника' else f"ID: {user_id}"
        for search in data.get('searches', [])[-3:]:
            recent_searches.append((username_display, search['topic'], search['date']))
    
    recent_searches.sort(key=lambda x: x[2], reverse=True)
    
    for username_display, topic, date in recent_searches[:10]:
        date_str = datetime.fromisoformat(date).strftime("%d.%m %H:%M")
        text += f"• {username_display}: {topic[:25]}... ({date_str})\n"
    
    if not recent_searches:
        text += "Поисков пока нет.\n"
    
    await update.message.reply_text(text)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Отменено")
    return ConversationHandler.END

def main() -> None:
    application = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [
                CommandHandler('start', start),
                CallbackQueryHandler(handle_main_menu)
            ],
            AWAITING_TOPIC: [
                CommandHandler('start', start),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic),
                CallbackQueryHandler(handle_main_menu)
            ],
            PLAN_CREATED: [
                CommandHandler('start', start),
                CallbackQueryHandler(handle_plan)
            ],
            POST_STUDY_CHOICE: [
                CommandHandler('start', start),
                CallbackQueryHandler(handle_test_choice)
            ],
            TEST_IN_PROGRESS: [
                CommandHandler('start', start),
                CallbackQueryHandler(handle_test_answer)
            ],
            POST_TEST_CHOICE: [
                CommandHandler('start', start),
                CallbackQueryHandler(handle_post_test)
            ],
            HISTORY_VIEW: [
                CommandHandler('start', start),
                CallbackQueryHandler(handle_history_selection)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('admin', admin_panel))
    application.run_polling()

if __name__ == "__main__":
    main()
