# устанавливаемые либы
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

################# текста клавиатур #################
# обновление статуса пользователя
BTN_CHECK_STATUS = "🔄 Обновить статус пользователя"   

# root админ меню
BTN_ADMIN_MENU_MANAGE_USERS = "👤 Управление пользователями"
BTN_ADMIN_MENU_GO_TO_SANDBOX = "🏖 Взаимодействие с песочницей"
BTN_ADMIN_MENU_MANAGE_APP = "💻 Управление приложением"

# меню управления пользователями
BTN_MANAGE_USERS_LIST_ALL = "📋 Отобразить всех пользователей"
BTN_MANAGE_USERS_INFO = "ℹ️ Подробная информация о пользователе по ID"
BTN_MANAGE_USERS_ADD = "➕ Добавить пользователя по ID"
BTN_MANAGE_USERS_BAN = "🔒 Заблокировать по ID"
BTN_MANAGE_USERS_UNBAN = "🔓 Разблокировать по ID"
BTN_MANAGE_USERS_DELETE = "🗑 Удалить пользователя по ID"
BTN_MANAGE_USERS_RETURN = "🔙 Вернуться в главное меню"

BTN_MANAGE_USERS_NO_FILTER = "♾️ Отобразить без фильтра"

# меню админа для управления приложением
BTN_MANAGE_APP_GET_DB_BACKUP = "🗄 Получить бэкап БД"
BTN_MANAGE_APP_RETURN = "🔙 Вернуться в главное меню"

# меню админа для взаимодействия с песочницей
BTN_SANDBOX_MENU_CHECK_API = "✅ Проверить состояние API"
BTN_SANDBOX_MENU_RETURN = "🔙 Вернуться в главное меню"

# отправка файлов на проверку
BTN_SANDBOX_MENU_SEND_FILE = "📁 Отправить файл на проверку"
BTN_SANDBOX_MENU_SEND_URL = "🔗 Отправить ссылку на проверку"

# общее взаимодействие с песочницей
BTN_SANDBOX_MENU_GET_STATS = "📊 Получить сведения о проверках"
BTN_SANDBOX_MENU_SEND_TO_SCAN = "⏫ Отправить на проверку"
BTN_SANDBOX_MENU_SCAN_RESULT = "🔄 Обновить статус задания"

# клавиатура "проверить свое состояние"
check_status_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_CHECK_STATUS)]],
    resize_keyboard=True
)

# клавиатура root меню для админа
admin_root_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_ADMIN_MENU_MANAGE_USERS)],
        [KeyboardButton(text=BTN_ADMIN_MENU_GO_TO_SANDBOX)],
        [KeyboardButton(text=BTN_ADMIN_MENU_MANAGE_APP)]
    ],
    resize_keyboard=True
)

# клавиатура управления пользователями в меню админа
manage_users_menu_keyboard = ReplyKeyboardMarkup(
    keyboard= [
        [KeyboardButton(text=BTN_MANAGE_USERS_LIST_ALL)],
        [KeyboardButton(text=BTN_MANAGE_USERS_INFO)],
        [KeyboardButton(text=BTN_MANAGE_USERS_ADD)],
        [KeyboardButton(text=BTN_MANAGE_USERS_BAN)],
        [KeyboardButton(text=BTN_MANAGE_USERS_UNBAN)],
        [KeyboardButton(text=BTN_MANAGE_USERS_DELETE)],
        [KeyboardButton(text=BTN_MANAGE_USERS_RETURN)]
    ],
    resize_keyboard=True
)

# клавиатура вывести пользователей без фильтрации
list_users_no_filter_keyboard = ReplyKeyboardMarkup(
    keyboard= [
        [KeyboardButton(text=BTN_MANAGE_USERS_NO_FILTER)]
    ],
    resize_keyboard=True
)

# клавиатура управления приложением для админа
admin_manage_app_keyboard = ReplyKeyboardMarkup(
    keyboard= [
        [KeyboardButton(text=BTN_MANAGE_APP_GET_DB_BACKUP)],
        [KeyboardButton(text=BTN_MANAGE_APP_RETURN)]
    ],
    resize_keyboard=True
)

# клавиатура мейн меню песочницы для админа
admin_main_sandbox_keyboard = ReplyKeyboardMarkup(
    keyboard= [
        [KeyboardButton(text=BTN_SANDBOX_MENU_CHECK_API)],
        [KeyboardButton(text=BTN_SANDBOX_MENU_SEND_FILE)],
        [KeyboardButton(text=BTN_SANDBOX_MENU_SEND_URL)],
        [KeyboardButton(text=BTN_SANDBOX_MENU_GET_STATS)],
        [KeyboardButton(text=BTN_SANDBOX_MENU_RETURN)]
    ],
    resize_keyboard=True
)

# клавиатура мейн меню для обычного пользователя
user_main_sandbox_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_SANDBOX_MENU_SEND_FILE)],
        [KeyboardButton(text=BTN_SANDBOX_MENU_SEND_URL)],
        [KeyboardButton(text=BTN_SANDBOX_MENU_GET_STATS)]
    ],
    resize_keyboard=True
)

# клавиатура "отправить на проверку" не важно файл или ссылка
send_to_scan_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_SANDBOX_MENU_SEND_TO_SCAN)]
    ],
    resize_keyboard=True
)

# клавиатура "получить результаты проверки" задания
get_scan_results_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_SANDBOX_MENU_SCAN_RESULT)]
    ],
    resize_keyboard=True
)