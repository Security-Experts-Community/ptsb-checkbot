# встроенные либы
import aiofiles
import asyncio
import os
import logging
import sys

## классы из устанавливаемых либ
# для работы с ТГ
from aiogram import Bot, Dispatcher, F                      # ядро бота
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode                         # для обработки сообщений в html вёрстке
from aiogram.filters import CommandStart                    # обработка команды /start
from aiogram.filters import StateFilter                     # работа сразу с несколькими состояниями
from aiogram.types import Message, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import Document                          # для обработки загрузки файлов в бота
from aiogram.fsm.storage.memory import MemoryStorage        # для механизма состояний логин -> меню -> проверка -> etc
from aiogram.fsm.context import FSMContext                  # для механизма состояний логин -> меню -> проверка -> etc
from aiogram.filters import BaseFilter                      # для фильтра на личные сообщения/группы
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError, TelegramRetryAfter # ошибки работы с ТГ
from aiogram.types import FSInputFile                       # отправка файлов из бота
# для шедулера на регулярное обновление БД
from apscheduler.schedulers.asyncio import AsyncIOScheduler     # выполнение обновления проверок пользователей по расписанию
from apscheduler.triggers.cron import CronTrigger


# самописные либы
from app.db import users_functions              # взаимодействие с таблицей юзерочков
from app.db import sandbox_profiles_functions   # взаимодействие с таблицей профилей ptsb
from app.bot import custom_keyboars             # клавиатуры для менюшек бота
from app.api import ptsb_client                 # взаимодейсвие с песочницей по API


# самописные классы
from app.db.users_functions import AppUserFromDb
from app.db.sandbox_profiles_functions import UserProfileFromDb
from app.api.ptsb_client import ApiHeathCheck, SendScanRequest, GetScanResust
from app.bot.custom_states import *
from app.bot.custom_users_parameters import *
from app.bot.custom_roles import *


### константы
# адрес песочницы PTSB
from app.api.ptsb_client import PTSB_ROOT_ADDR

# токен доступа к ТГ боту
TG_BOT_TOKEN = str(os.getenv('TG_BOT_TOKEN'))

# TG id первого администратора ТГ бота
FIRST_BOT_ADMIN_ID = int(os.getenv('FIRST_BOT_ADMIN_ID'))

## загрузка файлов
MAX_DOWNLOAD_RETRIES: int = 3           # максимальное количество попыток перезапуска бота #TODO: вынести в переменную?
DOWNLOAD_TIMEOUT: int = 300             # таймаут на попытку загрузки на весь файл (секунд)
DOWNLOAD_CHUNCK_SIZE: int = 64 * 1024   # максимальный размер чанка, который скачиваем за установленный таймаут (байт)
DOWNLOAD_PROGRESS_UPD_SECS: int = 1     # интервал, через который обновлять пользователю инфо о том, что его файл загрузился в бота (секунд) 
DOWNLOADL_RETRY_TIME: int = 5           # время через которое будет осуществлена повторная попытка загрузки файла (секунд)

# минимально возможное время паузы между ответами пользователю, если можно отрпавить не более 60 сообщений в секунду
TG_RPL_MIN_INTERVAL: float = 60 / 50    # 50 сообщений в минуту (секунд)

### логирование
# создание логгера
logger = logging.getLogger("ptsb_checkbot")
logger.setLevel(logging.INFO)
log_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(name)s [%(funcName)s]: %(message)s")

# хэндлер для обычного вывода stdout
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.INFO)
stdout_handler.setFormatter(log_formatter)

# хэндлер для WARNING и выше
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.WARNING)
stderr_handler.setFormatter(log_formatter)

# регистрация хэндлеров
logger.addHandler(stdout_handler)
logger.addHandler(stderr_handler)


# диспетчер всех хэндлеров для ТГ бота
dp = Dispatcher(storage=MemoryStorage())

# глобальный фильтр, чтобы бот работал только в личке
class PrivateChatsOnlyFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.chat.type == "private"

# применяем фильтр для локальных чатов глобально
dp.message.filter(PrivateChatsOnlyFilter())


# директория куда скачивать файлы
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DOWNLODAD_DIR = os.path.join(PROJECT_ROOT, "downloads")
if not os.path.exists(DOWNLODAD_DIR):
    os.mkdir(DOWNLODAD_DIR)

# возможные действия админа при вводе user_id для какого-то одного действия
class AdminSingleActionWithId:
    GET_USER_INFO = "get_one_user_info"     # информация о юзере по ID
    BAN_ONE_USER = "ban_one_user"           # бан юзера по ID
    UNBAN_ONE_USER = "unban_one_user"       # разбан юзера по ID
    DELETE_ONE_USER = "delete_one_user"     # удаление юзера по ID


# функция вывода информации о пользователе
async def handle_get_user_info(message: Message, user_entity: AppUserFromDb) -> None:
    """"
    Функция вывода информации по одному пользователю, если пользователь был найден в БД

    Принимает:
        - `message` (Message): Сообщение от админа
        - `user_entity` (object of custom class): Пользователь с информацией о нем
    """

    # в дополнение получаем профиль пользователя взаимодействия с песком
    logger.info(f"Trying to get info about user: {user_entity.tg_user_id}")
    user_sandbox_profile: UserProfileFromDb = await sandbox_profiles_functions.get_profile_entity(user_entity.tg_user_id)

    await message.answer(
        f"🧾 <b>Информация о пользователе</b> <code>{user_entity.tg_user_id}</code>:\n\n"
        "<b>Профиль пользователя</b>\n"
        f"Роль: {user_entity.user_role}\n"
        f"Комментарий: {user_entity.comment}\n"
        f"Создан пользователем: <code>{user_entity.created_by}</code>\n"
        f"Статус: {'заблокирован' if user_entity.is_blocked else 'разблокирован'}\n"
        f"Дата создания: {user_entity.creation_date}\n"
        f"Дата изменения: {user_entity.update_date}\n\n"
        "<b>Профиль песочницы</b>\n"
        f"Разрешно проверок в день: {user_sandbox_profile.max_available_checks}\n"
        f"Осталось проверок сегодня: {user_sandbox_profile.remaining_checks}\n"
        f"Всего создал заданий: {user_sandbox_profile.total_checks}\n"
        f"Приоритет проверки пользователя: {user_sandbox_profile.check_priority}\n"
        f"Получает ссылки на задания: {'да' if user_sandbox_profile.can_get_links else  'нет'}"
    )
    logger.info(f"Info about user: {user_entity.tg_user_id} was printed")

# функция забанить пользователя по id
async def handle_ban_user(message: Message, user_entity: AppUserFromDb) -> None:
    """"
    Функция бана одного пользователя, если пользователь был найден в БД

    Принимает:
        - `message` (Message): Сообщение от админа
        - `user_entity` (object of custom class): Пользователь с информацией о нем
    """
    
    logger.info(f"Trying to ban user {user_entity.tg_user_id} by user {message.from_user.id}")

    if user_entity.tg_user_id == message.from_user.id:
        await message.answer(
            "⚠️ <b>Не удалось выполнить действие!</b>\n\n"
            "Нельзя стрелять себе в колени и блокировать самого себя."
        )
        logger.info(f"User {message.from_user.id} was not banned by himself")
    
    else:
        await users_functions.change_user_state_by_id(user_entity.tg_user_id, 1)
        await message.answer(f"✅ Пользователь <code>{user_entity.tg_user_id}</code> заблокирован.")

        logger.info(f"User {user_entity.tg_user_id} was banned")

# функция разбранить пользователя по id
async def handle_unban_user(message: Message, user_entity: AppUserFromDb) -> None:
    """"
    Функция разбана одного пользователя, если пользователь был найден в БД

    Принимает:
        - `message` (Message): Сообщение от админа
        - `user_entity` (object of custom class): Пользователь с информацией о нем
    """

    logger.info(f"Trying to unban user {user_entity.tg_user_id} by user {message.from_user.id}")
    
    await users_functions.change_user_state_by_id(user_entity.tg_user_id, 0)
    await message.answer(f"✅ Пользователь <code>{user_entity.tg_user_id}</code> разблокирован.")
    
    logger.info(f"User {user_entity.tg_user_id} was unbanned")

# функция удаления юзера из БД
async def handle_delete_user(message: Message, user_entity: AppUserFromDb) -> None:
    """"
    Функция удаления одного пользователя, если пользователь был найден в БД

    Принимает:
        - `message` (Message): Сообщение от админа
        - `user_entity` (object of custom class): Пользователь с информацией о нем
    """

    logger.info(f"Trying to delete user {user_entity.tg_user_id} by user {message.from_user.id}")

    if user_entity.tg_user_id == message.from_user.id:
        await message.answer(
            "⚠️ <b>Не удалось выполнить действие!</b>\n\n"
            "Нельзя стрелять себе в колени и удалять самого себя."
        )
        logger.info(f"User {message.from_user.id} was not deleted by himself")

    else:
        # удаляем базовый профиль пользователя и профиль взаимодействия с песком
        await users_functions.delete_user_by_id(user_entity.tg_user_id)
        await sandbox_profiles_functions.delete_profile_by_id(user_entity.tg_user_id)
        await message.answer(f"✅ Пользователь <code>{user_entity.tg_user_id}</code> удалён.")

        logger.info(f"User {user_entity.tg_user_id} was deleted")

# регистрация маппинга действий на функции (хэндлеры)
ADMIN_SINGLE_ACTIONS_HANDLER = {
    AdminSingleActionWithId.GET_USER_INFO: handle_get_user_info,
    AdminSingleActionWithId.BAN_ONE_USER: handle_ban_user,
    AdminSingleActionWithId.UNBAN_ONE_USER: handle_unban_user,
    AdminSingleActionWithId.DELETE_ONE_USER: handle_delete_user,
}


############################## все хэндлеры бота ##############################
# работа с командой старт
@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    """
    Обработчик события для команды /start с проверкой прав, статуса блокировки,
    проверкой наличия пользователя в БД и выбором интерфейса на основе роли
    """

    # получаем ID текущего пользователя, который отправил запрос в БД и получаем данные по нему по ID
    current_user_id = message.from_user.id
    current_user_data: AppUserFromDb = await users_functions.get_user_entity(current_user_id)
    
    logger.info(f"User {current_user_id} started interaction with bot")
    
    # Проверяем, что пользователь существует в БД
    if current_user_data is None:
        logger.info(f"User {current_user_id} was not found in app database")
        
        await message.answer(
            f"⚠️ <b>Вы не зарегистрированы</b>!\n\n"
            f"Для получения доступа перешлите Администратору бота это сообщение.\n\n"
            f"Ваш TG ID: <code>{current_user_id}</code>.",
            reply_markup=custom_keyboars.check_status_keyboard            
        )
        await state.set_state(UserStates.check_user_status)
        return
    
    # проверяем что юзер в блек листе
    if current_user_data.is_blocked:
        logger.info(f"User {current_user_id} is banned in app and has no access")
        
        await message.answer(
            f"❌ <b>Доступ для Вас запрещён!</b>\n\n"
            f"Если Вы считаете, что это ошибка, то сообщите об этом Администратору бота.\n\n"
            f"Ваш TG ID: <code>{current_user_id}</code>",
            reply_markup=custom_keyboars.check_status_keyboard
        )
        await state.set_state(UserStates.check_user_status)
        return

    # Во всех прочих случаях определяем меню в зависимости от роли
    if current_user_data.user_role == UsersRolesInBot.main_admin:
        logger.info(f"User {current_user_id} was authorized and got role of {current_user_data.user_role}")
        
        await message.answer(
            f"👑 Добро пожаловать, Администратор!\n\n"
            f"Выберите действие из доступных в списке ниже:",
            reply_markup=custom_keyboars.admin_root_menu_keyboard
        )
        await state.set_state(AdminStates.root_admin_menu)
        return
    
    elif current_user_data.user_role == UsersRolesInBot.user:
        logger.info(f"User {current_user_id} was authorized and got role of {current_user_data.user_role}")
        
        await message.answer(
            f"👋 Добро пожаловать!\n\n"
            f"Выберите действие из доступных в списке ниже:",
            reply_markup=custom_keyboars.user_main_sandbox_keyboard
        )
        await state.set_state(SandboxInteractionStates.sandbox_user_menu)
        return


############################## административные простые хэндлеры ##############################
# хэндлеры, связанные с пользователями
# хэндлер для root_admin_menu -> manage_users_menu // переход в управление пользователями
@dp.message(AdminStates.root_admin_menu, F.text == custom_keyboars.BTN_ADMIN_MENU_MANAGE_USERS)
async def manage_users_admin_menu(message: Message, state: FSMContext) -> None:
    await message.answer(
        "📋 Меню управления пользователями.\n\nВыберите действие:",
        reply_markup=custom_keyboars.manage_users_menu_keyboard
    )
    await state.set_state(AdminStates.manage_users_menu)
    return


# хэндлер для manage_users_menu -> root_admin_menu // вернуться в главное меню админа
@dp.message(AdminStates.manage_users_menu, F.text == custom_keyboars.BTN_MANAGE_USERS_RETURN)
async def return_to_main_admin_menu(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Выберите действие из доступных в списке ниже:",
        reply_markup=custom_keyboars.admin_root_menu_keyboard
    )
    await state.set_state(AdminStates.root_admin_menu)
    return


# хэндлер для root_admin_menu -> sandbox_admin_menu // переход во взаимодейсвтие с песочницей
@dp.message(AdminStates.root_admin_menu, F.text == custom_keyboars.BTN_ADMIN_MENU_GO_TO_SANDBOX)
async def sandbox_admin_menu(message: Message, state: FSMContext) -> None:
    await message.answer(
        "📋 Меню взаимодействия с песочницей.\n\nВыберите действие:",
        reply_markup=custom_keyboars.admin_main_sandbox_keyboard
    )
    await state.set_state(SandboxInteractionStates.sandbox_admin_menu)
    return


# хэндлер для sandbox_admin_menu -> root_admin_menu // переход в root menu у админа
@dp.message(SandboxInteractionStates.sandbox_admin_menu, F.text == custom_keyboars.BTN_SANDBOX_MENU_RETURN)
async def return_to_main_admin_menu(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Выберите действие из доступных в списке ниже:",
        reply_markup=custom_keyboars.admin_root_menu_keyboard
    )
    await state.set_state(AdminStates.root_admin_menu)
    return


# универсальный хэндлер для действий админа, когда он делает единичное действие с юзером по ID
@dp.message(AdminStates.manage_users_menu, F.text.in_({
    custom_keyboars.BTN_MANAGE_USERS_INFO,
    custom_keyboars.BTN_MANAGE_USERS_BAN,
    custom_keyboars.BTN_MANAGE_USERS_UNBAN,
    custom_keyboars.BTN_MANAGE_USERS_DELETE
}))
async def handle_user_id_action_prompt(message: Message, state: FSMContext) -> None:
    text_to_action = {
        custom_keyboars.BTN_MANAGE_USERS_INFO: (
            AdminSingleActionWithId.GET_USER_INFO,
            "Введите <code>user_id</code>, по которому нужно получить информацию:"
        ),
        custom_keyboars.BTN_MANAGE_USERS_BAN: (
            AdminSingleActionWithId.BAN_ONE_USER,
            "Введите <code>user_id</code>, которого нужно заблокировать:"
        ),
        custom_keyboars.BTN_MANAGE_USERS_UNBAN: (
            AdminSingleActionWithId.UNBAN_ONE_USER,
            "Введите <code>user_id</code>, которого нужно разблокировать:"
        ),
        custom_keyboars.BTN_MANAGE_USERS_DELETE: (
            AdminSingleActionWithId.DELETE_ONE_USER,
            "Введите <code>user_id</code>, которого нужно удалить:"
        )
    }

    action, prompt = text_to_action[message.text]

    await state.update_data(admin_action=action)
    await message.answer(prompt)
    await state.set_state(AdminStates.input_user_id)
    return


# хэндлер для input_user_id -> manage_users_menu // обработка введенного TG ID для:
# 1. получения информации по одному пользователю по id
# 2. удаления пользователя по id 
# 3. бана пользователя по id
# 4. разбана пользователя по id 
@dp.message(AdminStates.input_user_id)
async def make_single_action_with_user_id(message: Message, state: FSMContext) -> None:
    
    # получаем контекст состояния, чтобы узнать admin_action из предыдущего шага
    admin_data = await state.get_data()
    admin_action_type = admin_data.get("admin_action") 
    
    logger.info(f"Admin user {message.from_user.id} trying to perform action: {admin_action_type}")
    
    try:
        
        # обрабатываем ввод и запрашиваем его из БД
        user_id_to_get = int(message.text)
        user_entity: AppUserFromDb = await users_functions.get_user_entity(user_id_to_get)

        # если юзера в БД не существует
        if user_entity is None:
            logger.info(f"User {user_id_to_get} was not found in app db to perform action by admin user {message.from_user.id}")

            await message.answer(
                "⚠️ <b>Не удалось выполнить действие!</b>\n\n"
                "Пользователь не найден в базе."
            )
        
        # если существует
        else:
            handler_func = ADMIN_SINGLE_ACTIONS_HANDLER.get(admin_action_type)
            await handler_func(message, user_entity)

    # ошибка ввода TG id от админа
    except ValueError:
        logger.info("Action by admin user was nor perfromed, becouse of incorrect int() input")

        await message.answer(
            "⚠️ <b>Не удалось выполнить действие!</b>\n\n"
            "Не получилось преобразовать ввод в число."
        )
    
    # в любом случае возвращаем админа в меню управления пользователями
    await state.update_data(admin_action="")
    await state.set_state(AdminStates.manage_users_menu)
    await message.answer(
        "Выберите дальнейшее действие:",
        reply_markup=custom_keyboars.manage_users_menu_keyboard
    )
    return


############################## административные хэндлеры создание юзеров ##############################
# хэндлер для перехода к созданию пользователя в боте
@dp.message(AdminStates.manage_users_menu, F.text == custom_keyboars.BTN_MANAGE_USERS_ADD)
async def handle_promt_to_create_user(message: Message, state: FSMContext) -> None:
    
    logger.info(f"Admin user {message.from_user.id} started process of new user creation")

    # обнуляем все переменные в контексте админа перед созданием нового пользователя. для безопасности
    for parameter in vars(InputUserParameters).values():
        if isinstance(parameter, str):
            await state.update_data({parameter: ""})
    
    for parameter in vars(InputSandboxProfileParameters).values():
        if isinstance(parameter, str):
            await state.update_data({parameter: ""})

    await message.answer("Введите <code>telegram id</code> пользователя, которого нужно создать:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AppUserCreation.CREATE_user_id)
    return


# хэндлер для ввода tg id для создания пользователя 
@dp.message(AppUserCreation.CREATE_user_id)
async def process_user_id_to_create(message: Message, state: FSMContext) -> None:

    # пытаемся преобразовать введенный TG ID в текст, если не получается - кидаем ворнинг и возращаем в меню управления юзерами
    try:
        user_id_to_create = int(message.text)
    except ValueError:
        logger.info(f"Creation of user by admin user {message.from_user.id} was interrupted becouse of incorrect int(tg_user_id) input")

        await message.answer(
            "⚠️ <b>Не удалось выполнить действие!</b>\n\n"
            "Не получилось преобразовать ввод в число."
        )
        await message.answer(
            "Выберите дальнейшее действие:",
            reply_markup=custom_keyboars.manage_users_menu_keyboard
        )
        await state.set_state(AdminStates.manage_users_menu)
        return
    
    # проверяем, что пользователь еще не существует в боте.
    user_entity: AppUserFromDb = await users_functions.get_user_entity(user_id_to_create)
    if user_entity is not None:
        logger.info(f"Creation of user {user_entity.tg_user_id} by admin user {message.from_user.id} was interrupted becouse user already exists")

        await message.answer(
            "⚠️ <b>Не удалось выполнить действие!</b>\n\n"
            f"Пользователь с id <code>{user_id_to_create}</code> уже существует."
        )
        await message.answer(
            "Выберите дальнейшее действие:",
            reply_markup=custom_keyboars.manage_users_menu_keyboard
        )
        await state.set_state(AdminStates.manage_users_menu)
        return
    
    # если всё ок, то записываем user_id и запрашиваем роль для будущего юзера:
    await state.update_data({InputUserParameters.tg_user_id: user_id_to_create})
    await message.answer(
        "Введите роль для будущего пользователя:\n" +
        f"1. <code>{UsersRolesInBot.user}</code> - обычный пользователь бота. Имеет права только на проверку файлов.\n"
    )
    await state.set_state(AppUserCreation.CREATE_user_role)
    return


# хэндлер для ввода роли для создания пользователя 
@dp.message(AppUserCreation.CREATE_user_role, F.text)
async def process_user_role_to_create(message: Message, state: FSMContext) -> None:

    user_role_to_create = message.text

    # проверяем, что ввод соответствует названиям ролей в приложении
    if user_role_to_create != UsersRolesInBot.user:
        logger.info(f"Creation of user by admin user {message.from_user.id} was interrupted becouse of incorrect user_role input")

        await message.answer(
            "⚠️ <b>Не удалось выполнить действие!</b>"
            f"Введено значение, отличное от <code>{UsersRolesInBot.user}</code>."
        )
        await message.answer(
            "Выберите дальнейшее действие:",
            reply_markup=custom_keyboars.manage_users_menu_keyboard
        )
        await state.set_state(AdminStates.manage_users_menu)
        return
    
    # если всё ок, то запрашиваем количество проверок в день
    await state.update_data({InputUserParameters.user_role: user_role_to_create})
    await message.answer("Введите комментарий (примечание к пользователю).\nПолезно будет указать ФИО или другую информацию о юзере. Не более 255 символов.")
    await state.set_state(AppUserCreation.CREATE_comment)
    return


# хэндлер для ввода комментария для создания пользователя 
@dp.message(AppUserCreation.CREATE_comment, F.text)
async def process_user_comment_to_create(message: Message, state: FSMContext) -> None:

    # получаем комментарий по юзеру и проверяем, что он соответстует длине не более 255
    user_comment = message.text
    if len(user_comment) > 255:
        logger.info(f"Creation of user by admin user {message.from_user.id} was interrupted becouse of large user_comment input")

        await message.answer(
            "⚠️ <b>Не удалось выполнить действие!</b>\n\n"
            "Длина комментария получилась больше 255 символов."
        )
        await message.answer(
            "Выберите дальнейшее действие:",
            reply_markup=custom_keyboars.manage_users_menu_keyboard
        )
        await state.set_state(AdminStates.manage_users_menu)
        return
    
    # если все ок, то завершаем создание профиля пользователя и переходим к созданию профиля песка
    await state.update_data({InputUserParameters.comment: user_comment})
    await message.answer("Введена базовая информация по пользователю.\nПереход к заполнению профиля взаимодействия с песочницей.")
    await message.answer("Введите количество проверок в день, которые доступы пользователю (целое число):")
    await state.set_state(SandboxProfileCreation.CREATE_max_checks)
    return



# хэндлер для ввода max количества проверок для создания пользователя 
@dp.message(SandboxProfileCreation.CREATE_max_checks, F.text)
async def process_user_max_cheks_to_create(message: Message, state: FSMContext) -> None:

    # пытаемся преобразовать полученное значение в целое число и проверяем, что число строго > 0
    try:
        max_user_checks = int(message.text)
        if max_user_checks <= 0:
            raise ValueError()
    except ValueError:
        logger.info(f"Creation of user by admin user {message.from_user.id} was interrupted becouse of incorrect 0 < int(max_user_cheks) input")
        
        await message.answer(
            "⚠️ <b>Не удалось выполнить действие!</b>\n\n"
            "Не получилось преобразовать ввод в целое число большее 0."
        )
        await message.answer(
            "Выберите дальнейшее действие:",
            reply_markup=custom_keyboars.manage_users_menu_keyboard
        )
        await state.set_state(AdminStates.manage_users_menu)
        return
    
    # если всё ок, то записываем полученное значение и запрашиваем приоритет проверки от пользователя
    await state.update_data({InputSandboxProfileParameters.max_available_checks: max_user_checks})
    await message.answer(
        "Укажите приоритет проверки заданий от этого пользователя от 1 до 4:\n"
        "<code>1</code> - минимальный приоритет.\n"
        "<code>4</code> - максимальный приоритет."
    )
    await state.set_state(SandboxProfileCreation.CREATE_check_priority)
    return


# хэндлер для ввода приоритета проверки для создания пользователя 
@dp.message(SandboxProfileCreation.CREATE_check_priority)
async def process_user_priority_to_create(message: Message, state: FSMContext) -> None:
    
    # пытаемся преобразовать введенный текст в число от 1 до 4
    try:
        user_check_priority = int(message.text)
        if user_check_priority not in range(1,5):
            raise ValueError
    except ValueError:
        logger.info(f"Creation of user by admin user {message.from_user.id} was interrupted becouse of incorrect 1 <= int(user_check_priority) <= 4 input")

        await message.answer(
            "⚠️ <b>Не удалось выполнить действие!</b>\n\n"
            "Не удалось преобразовать ввод в целое число от 1 до 4."
        )
        await message.answer(
            "Выберите дальнейшее действие:",
            reply_markup=custom_keyboars.manage_users_menu_keyboard
        )
        await state.set_state(AdminStates.manage_users_menu)
        return

    # если всё ок, то записываем полученное значение и запрашиваем комментарий по пользователю
    await state.update_data({InputSandboxProfileParameters.check_priority: user_check_priority})
    await message.answer(
        "Укажите будет ли пользователь получать ссылки на задания:\n"
        "<code>1</code> - бот будет отправлять пользователю ссылку на задание, которое пользователь запустил на проверку.\n"
        "<code>0</code> - пользователь будет получать от бота только <code>scan_id</code> своего задания" 
    )
    await state.set_state(SandboxProfileCreation.CREATE_can_get_links)
    return


# хэндлер для ввода может ли пользователь получать ссылки на проверки и final создание пользователя
@dp.message(SandboxProfileCreation.CREATE_can_get_links)
async def process_user_comment_to_create(message: Message, state: FSMContext) -> None:

    # получаем ответ и пытаемся преобразовать в число 0 или 1
    try:
        can_user_get_links = int(message.text)
        if can_user_get_links not in [0, 1]:
            raise ValueError
        
    except ValueError:
        logger.info(f"Creation of user by admin user {message.from_user.id} was interrupted becouse of incorrect 0 <= int(can_user_get_links) <= 1 input")

        await message.answer(
            "⚠️ <b>Не удалось выполнить действие!</b>\n\n"
            "Не удалось преобразовать ввод в целое число 0 или 1."
        )
        await message.answer(
            "Выберите дальнейшее действие:",
            reply_markup=custom_keyboars.manage_users_menu_keyboard
        )
        await state.set_state(AdminStates.manage_users_menu)
        return

    
    # если всё ок, то переходим к созданию пользователя в БД
    data = await state.get_data()

    # основаная информация по юзеру
    tg_user_id = data.get(InputUserParameters.tg_user_id)
    user_role = data.get(InputUserParameters.user_role)
    user_comment = data.get(InputUserParameters.comment)

    # профиль взаимодействия с песочницей
    max_available_checks = data.get(InputSandboxProfileParameters.max_available_checks)
    user_check_priority = data.get(InputSandboxProfileParameters.check_priority)

    # создаем базовый профиль пользователя
    await users_functions.add_new_user(
        tg_user_id=tg_user_id,
        user_role=user_role,
        comment=user_comment,
        created_by=message.from_user.id
    )
    logger.info(f"Base app profile for user {tg_user_id} was created")

    # создаем профиль взаимодействия с песочницей
    await sandbox_profiles_functions.add_new_profile(
        tg_user_id=tg_user_id,
        max_available_checks=max_available_checks,
        check_priority=user_check_priority,
        can_get_links=can_user_get_links
    )
    logger.info(f"Sandbox interaction profile for user {tg_user_id} was created")
    
    # возвращаемся в manage users menu
    await message.answer(f"✅ Пользователь с id <code>{tg_user_id}</code> добавлен.")
    await message.answer(
        "Выберите дальнейшее действие:",
        reply_markup=custom_keyboars.manage_users_menu_keyboard
    )
    await state.set_state(AdminStates.manage_users_menu)
    return

############################## административные хэндлеры вывод всех пользователей ##############################
# хэндлер для перехода к выводу всех пользователей
@dp.message(AdminStates.manage_users_menu, F.text == custom_keyboars.BTN_MANAGE_USERS_LIST_ALL)
async def handle_list_all_users(message: Message, state: FSMContext) -> None:

    await message.answer(
        "При необходимости укажите фильтр для поиска среди всех пользователей. "
        "Он будет применен к полю <code>комментарий</code>, которое Вы указывали при создании пользователя.\n\n"
        "Если фильтрация не требуется, нажмите кнопку ниже:",
        reply_markup=custom_keyboars.list_users_no_filter_keyboard
    )
    await state.set_state(AdminStates.list_app_users)
    return

# хэндлер для вывода всех пользователей, опционально с фильтром
@dp.message(AdminStates.list_app_users, F.text)
async def process_list_all_users(message: Message, state: FSMContext) -> None:

    # получаем ответ от пользователя
    filter_from_admin: str = message.text
    list_of_users_fromm_app_db: list[AppUserFromDb] = []
    
    if filter_from_admin == custom_keyboars.BTN_MANAGE_USERS_NO_FILTER:
        logger.info(f"Admin user {message.from_user.id} is going to list app users with no filter")
        list_of_users_fromm_app_db = await users_functions.fetch_all_users_with_filter()
    else:
        logger.info(f"Admin user {message.from_user.id} is going to list app users with filter")
        list_of_users_fromm_app_db = await users_functions.fetch_all_users_with_filter(comment_filter=filter_from_admin)

    # если список пустой
    if len(list_of_users_fromm_app_db) == 0:
        await message.answer(
            "⚠️ <b>Не удалось выполнить действие!</b>\n\n"
            "Нет пользователей, подходящих под критерии поиска."
        )
    
    # если не пустой, то выводим
    else:
        for user in list_of_users_fromm_app_db:
            await message.answer(
                f"🧾 <b>Информация о пользователе</b> <code>{user.tg_user_id}</code>:\n\n"
                "<b>Профиль пользователя</b>\n"
                f"Роль: {user.user_role}\n"
                f"Комментарий: {user.comment}\n"
                f"Статус: {'заблокирован' if user.is_blocked else 'разблокирован'}\n"
                f"Дата создания: {user.creation_date}\n"
                f"Дата изменения: {user.update_date}\n\n"
            )
    
    # ну и идем дальше 
    await message.answer(
        "Выберите дальнейшее действие:",
        reply_markup=custom_keyboars.manage_users_menu_keyboard
    )
    await state.set_state(AdminStates.manage_users_menu)
    return


############################## административные хэндлеры ##############################
# хэндлеры связанные с управлением приложением
# хэндлер для перехода в меню управления приложением
@dp.message(AdminStates.root_admin_menu, F.text == custom_keyboars.BTN_ADMIN_MENU_MANAGE_APP)
async def go_to_manage_app_menu(message: Message, state: FSMContext) -> None:
    
    await message.answer(
        "📋 Меню управления приложением.\n\nВыберите действие:",
        reply_markup=custom_keyboars.admin_manage_app_keyboard
    )
    await state.set_state(AdminStates.manage_app_menu)
    return

# хэндлер обработки дейсвтий админа по управлению приложением в зависимости от выбранного им дейсвтия
@dp.message(
    AdminStates.manage_app_menu,
    F.text.in_([custom_keyboars.BTN_MANAGE_APP_GET_DB_BACKUP, custom_keyboars.BTN_MANAGE_APP_RETURN])
)
async def process_manage_app_action(message: Message, state: FSMContext) -> None:

    # если нужен бекап БД
    if message.text == custom_keyboars.BTN_MANAGE_APP_GET_DB_BACKUP:
        # открываем и отправляем
        logger.info(f"Admin user {message.from_user.id} is getting db backup of application")

        db_file = FSInputFile(users_functions.FULL_PATH_TO_KERNEL_DB, filename=users_functions.DB_NAME)
        await message.answer_document(db_file, caption="Файл с БД пользователей:")
        await message.answer(
            "Выберите дальнейшее дейсвтие:",
            reply_markup=custom_keyboars.admin_manage_app_keyboard
        )
        await state.set_state(AdminStates.manage_app_menu)
        return

    # если выйти из меню
    if message.text == custom_keyboars.BTN_MANAGE_APP_RETURN:
        await message.answer(
            "Выберите дальнейшее дейсвтие:",
            reply_markup=custom_keyboars.admin_root_menu_keyboard
        )
        await state.set_state(AdminStates.root_admin_menu)
        return

    

############################## пользовательские хэндлеры ##############################
# хэндлер для проверки состояния пользователя
@dp.message(UserStates.check_user_status, F.text == custom_keyboars.BTN_CHECK_STATUS)
async def process_user_comment_to_create(message: Message, state: FSMContext) -> None:
    
    # получаем информацию по юзеру
    logger.info(f"User {message.from_user.id} is trying to get his status")
    user_entity: AppUserFromDb = await users_functions.get_user_entity(message.from_user.id)

    # если всё еще не создали
    if user_entity is None:
        logger.info(f"User {message.from_user.id} is still not registred")

        await message.answer(
            "⚠️ <b>Вы не зарегистрированы!</b>\n\n"
            "Для получения доступа перешлите Администратору бота это сообщение.\n\n"
            f"Ваш TG ID: <code>{message.from_user.id}</code>.",
            reply_markup=custom_keyboars.check_status_keyboard
        )
        await state.set_state(UserStates.check_user_status)
        return

    # проверяем что юзер в блек листе
    if user_entity.is_blocked:
        logger.info(f"User {message.from_user.id} is banned in application")

        await message.answer(
            f"❌ <b>Доступ для Вас запрещён!</b>\n\n"
            f"Если Вы считаете, что это ошибка, то сообщите об этом Администратору бота.\n\n"
            f"Ваш TG ID: <code>{user_entity.tg_user_id}</code>.",
            reply_markup=custom_keyboars.check_status_keyboard
        )
        await state.set_state(UserStates.check_user_status)
        return

    # Во всех прочих случаях определяем меню в зависимости от роли
    if user_entity.user_role == UsersRolesInBot.user:
        logger.info(f"User {user_entity.tg_user_id} was authorized and got role of {user_entity.user_role}")

        await message.answer(
            f"👋 Добро пожаловать!\n\n"
            f"Выберите действие из доступных в списке ниже:",
            reply_markup=custom_keyboars.user_main_sandbox_keyboard 
        )
        await state.set_state(SandboxInteractionStates.sandbox_user_menu)
        return


############################## песочнические хэндлеры взаимодействия с ptsb ##############################
# хэндлер для проверки состояния API PTSB
@dp.message(SandboxInteractionStates.sandbox_admin_menu, F.text == custom_keyboars.BTN_SANDBOX_MENU_CHECK_API)
async def process_user_comment_to_create(message: Message, state: FSMContext) -> None:
    
    logger.info(f"Admin user {message.from_user.id} sent API healtcheck request to PTSB")

    # получаем состояние API 
    await message.answer("Отпрвлен API запрос на проверку. Проверка может занять до 10 секунд.")
    api_health_check: ApiHeathCheck = await ptsb_client.make_api_healthcheck()

    # обрабатываем статус
    if api_health_check.is_ok:
        logger.info("API healtcheck request is OK")
        await message.answer("✅ API PTSB доступен.")
    else:
        logger.warning(f"Error acquired while sending API healthck request. Error text: {api_health_check.error_message}")
        await message.answer(
            f"⚠️ При проврке API возникла ошибка.\n\n{api_health_check.error_message}"
        )
    
    # в любом случае в мейн меню
    await message.answer(
        "Выберите дальнейшее действие:",
        reply_markup=custom_keyboars.admin_main_sandbox_keyboard
    )
    await state.set_state(SandboxInteractionStates.sandbox_admin_menu)
    return


# хэндлер для получения информации статистики о себе
@dp.message(
    StateFilter(SandboxInteractionStates.sandbox_admin_menu, SandboxInteractionStates.sandbox_user_menu),
    F.text == custom_keyboars.BTN_SANDBOX_MENU_GET_STATS
)
async def get_sandbox_checks_stats(message: Message, state: FSMContext) -> None:
    
    # получаем профиль пользователя для взаимодействия с песком
    user_sandbox_profile: UserProfileFromDb = await sandbox_profiles_functions.get_profile_entity(message.from_user.id)
    # получаем профиль пользователя, чтобы понять какая у него роль
    user_entity: AppUserFromDb = await users_functions.get_user_entity(message.from_user.id)

    if (user_sandbox_profile is None) or (user_entity is None) or user_entity.is_blocked:
        logger.info(f"User {message.from_user.id} tried to get sandbox profile status, but had lost his access earlier")
        
        await message.answer(
            "⚠️ Кажется, доступ для Вас прекращен.",
            reply_markup=custom_keyboars.check_status_keyboard
        )
        await state.set_state(UserStates.check_user_status)
        return

    await message.answer(
        f"<b>Статистика пользователя</b>\n\n"
        f"Доступно проверок в сутки: {user_sandbox_profile.max_available_checks}\n"
        f"Осталось сегодня: {user_sandbox_profile.remaining_checks}\n"
    )
    await message.answer("Выберите дальнейшее действие из списка ниже:")
    
    if user_entity.user_role == UsersRolesInBot.main_admin:
        await state.set_state(SandboxInteractionStates.sandbox_admin_menu)
        return
    elif user_entity.user_role == UsersRolesInBot.user:
        await state.set_state(SandboxInteractionStates.sandbox_user_menu)
        return


# хэндел для нажатия кнопки "отправить ссылку на проверку"
@dp.message(
    StateFilter(SandboxInteractionStates.sandbox_admin_menu, SandboxInteractionStates.sandbox_user_menu),
    F.text == custom_keyboars.BTN_SANDBOX_MENU_SEND_URL
)
async def handle_send_url_to_scan(message: Message, state: FSMContext) -> None:
    
    # получаем профиль пользователя, чтобы понять можно ли ему взаимодействовать с ботом
    user_entity: AppUserFromDb = await users_functions.get_user_entity(message.from_user.id)

    # если юзер больше не существует или заблокирован
    if (user_entity is None) or user_entity.is_blocked:
        logger.info(f"User {message.from_user.id} tried to send link to check, but had lost his access earlier")
        
        await message.answer(
            "⚠️ Кажется, доступ для Вас прекращен.",
            reply_markup=custom_keyboars.check_status_keyboard)
        await state.set_state(UserStates.check_user_status)
        return

    # если юзер закончил на сегодня все свои проверки
    user_sandbox_profile: UserProfileFromDb = await sandbox_profiles_functions.get_profile_entity(message.from_user.id)
    if user_sandbox_profile.remaining_checks == 0:
        logger.info(f"User {message.from_user.id} tried to send link to check, but has no available checks today")

        await message.answer(
            "⚠️ У Вас закончились проверки на сегодня.\n\n"
            "Обновление проверок происходит каждый день. Повторите попытку завтра."
        )
        return
    
    # если с юзером все окей то запоминаем параметры, которые помогут в будущем
    await state.update_data({SandboxInteractionsParameters.user_role: user_entity.user_role})
    await state.update_data({SandboxInteractionsParameters.scan_priority: user_sandbox_profile.check_priority})
    await state.update_data({SandboxInteractionsParameters.can_get_links: user_sandbox_profile.can_get_links})
    await state.update_data({SandboxInteractionsParameters.scan_type: "url"})

    # и просим ввести ссылку на проверку
    await message.answer(
        "Введите текст ссылки, которую нужно проверить (не больше одной ссылки):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(SandboxInteractionStates.input_url_to_scan)
    return


# хэндлер ввода ссылки для отправки на проверку
@dp.message(SandboxInteractionStates.input_url_to_scan)
async def process_url_input_to_scan(message: Message, state: FSMContext) -> None:
    
    # проверяем, что пользователь отправил именно текст
    if message.text is None:
        await message.answer(
            "⚠️ <b>Ожидался ввод ссылки.</b>\n\n"
            "Сообщение не содержит текста."
        )
        await message.answer("Введите ссылку для проверки:")
        await state.set_state(SandboxInteractionStates.input_url_to_scan)
        return
    
    # получаем URL + заносим ее в контекст состояния пользователя
    url_to_scan: str = message.text
    url_to_scan.strip().split()[0]
    await state.update_data({SandboxInteractionsParameters.url_to_scan: url_to_scan})

    # запрашиваем ввод паролей для отправки ссылку на проверку, в любом случае в это состояние
    await message.answer(
        "Если Вы знаете, что файлы зашифрованы паролем, укажите их сейчас, каждый с новой строки. Всего не более 5 паролей.\n"
        "Если паролей нет, нажмите кнопку ниже.",
        reply_markup=custom_keyboars.send_to_scan_keyboard
    )
    await state.set_state(SandboxInteractionStates.send_req_for_scan)
    return


# хэндлер для нажатия кнопки "отправить файл на проверку"
@dp.message(
    StateFilter(SandboxInteractionStates.sandbox_admin_menu, SandboxInteractionStates.sandbox_user_menu),
    F.text == custom_keyboars.BTN_SANDBOX_MENU_SEND_FILE
)
async def hadle_send_file_to_scan(message: Message, state: FSMContext) -> None:

    # получаем профиль пользователя, чтобы понять можно ли ему взаимодействовать с ботом
    user_entity: AppUserFromDb = await users_functions.get_user_entity(message.from_user.id)

    # если юзер больше не существует или заблокирован
    if (user_entity is None) or user_entity.is_blocked:
        logger.info(f"User {message.from_user.id} tried to send file to check, but had lost his access earlier")

        await message.answer(
            "⚠️ Кажется, доступ для Вас прекращен.",
            reply_markup=custom_keyboars.check_status_keyboard)
        await state.set_state(UserStates.check_user_status)
        return

    # если юзер закончил на сегодня все свои проверки
    user_sandbox_profile: UserProfileFromDb = await sandbox_profiles_functions.get_profile_entity(message.from_user.id)
    if user_sandbox_profile.remaining_checks == 0:
        logger.info(f"User {message.from_user.id} tried to send file to check, but has no available checks today")
        
        await message.answer(
            "⚠️ У Вас закончились проверки на сегодня.\n\n"
            "Обновление проверок происходит каждый день."
        )
        return
    
    # если с юзером все окей то задаем параметры, которые помогут в будущем
    await state.update_data({SandboxInteractionsParameters.user_role: user_entity.user_role})
    await state.update_data({SandboxInteractionsParameters.scan_priority: user_sandbox_profile.check_priority})
    await state.update_data({SandboxInteractionsParameters.can_get_links: user_sandbox_profile.can_get_links})
    await state.update_data({SandboxInteractionsParameters.scan_type: "file"})
    await state.update_data({SandboxInteractionsParameters.file_uploaded: False})

    # и отправить файл на проверку
    await message.answer(
        "Отправьте файл, который нужно проверить.\n\n"
        "Не более одного файла, не более 20 мбайт (ограничение телеграма). Если Вы отправите несколько файлов, бот возьмет только один из них.",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(SandboxInteractionStates.upload_file_to_scan)
    return  


# хэндер для загрузки файла для последующей его проверки
@dp.message(SandboxInteractionStates.upload_file_to_scan, F.document)
async def upload_file_to_bot(message: Message, state: FSMContext) -> None:

    # проверка на то, чтобы было не больше одного файла
    user_data = await state.get_data()
    if user_data.get(SandboxInteractionsParameters.file_uploaded):
        return
    await state.update_data({SandboxInteractionsParameters.file_uploaded: True})
    
    # получаем файл и проверяем, что файл существует
    file_from_user: Document = message.document
    if not file_from_user:
        await message.answer(
            "⚠️ <b>Ожидалась отправка файла.</b>\n\n"
            "Сообщение не содержит файлов."
        )
        await message.answer("Загрузите файл для проверки:")
        await state.set_state(upload_file_to_bot)
        return

    try:
        # получаем объект бота через апи
        bot = message.bot
        
        telegram_file_id = await bot.get_file(file_from_user.file_id)       # получаем id файла
        file_path_on_server = telegram_file_id.file_path                    # берем полный путь к файлу на серверах ТГ
        file_name = f"TG-{message.from_user.id}-{file_from_user.file_name}" # имя файла который мы создадим локально = TG+<user_id>+<имя файла от юзера>
        save_path = os.path.join(DOWNLODAD_DIR, file_name)                  # устанавливаем полный путь к файлу, который сохраняем в папку DOWNLOAD_DIR

        # информируем пользователя о том, что собираемся начать процесс загрузки файла
        # информирование нужно, т.к. процесс загрузки может занять значительное время из-за блокировок ТГ
        info_message_for_download = await message.answer(
            "📥 <b>Выполняю загрузку файла</b>\n"
            f"<code>{file_from_user.file_name}</code>\n\n"
            "Прогресс: 0%"
        )

        # начинаем процесс скачивания файла с попытками перезапуска в случае ошибок
        for download_attempt in range(MAX_DOWNLOAD_RETRIES):
            try:
                logger.info(f"Starting attempt №{download_attempt + 1} downloading file {file_from_user.file_name} from user {message.from_user.id}")
                
                # скачиваем файл как байты с серверов телеграма используя путь к файлу на сервере тг
                file_bytes_data = await bot.download_file(
                    file_path=file_path_on_server,
                    timeout=DOWNLOAD_TIMEOUT,
                    chunk_size=DOWNLOAD_CHUNCK_SIZE
                )

                # сохраняем файл чанками
                async with aiofiles.open(save_path,"wb") as downloaded_file:
                    total_bytes_downloaded: int = 0 # объем скачанного файла
                    last_update_time: float = 0     # момент времени, когда последний раз обновляли информацию о статусе загрузки
                    # читаем файл порциями
                    while True:
                        one_file_chunk = file_bytes_data.read(DOWNLOAD_CHUNCK_SIZE)
                        if not one_file_chunk:
                            break
                        
                        await downloaded_file.write(one_file_chunk)
                        total_bytes_downloaded += len(one_file_chunk)

                        # # Получаем текущее время
                        # current_time = asyncio.get_event_loop().time()

                        # # обновляем текст только если прошло TG_RPL_MIN_INTERVAL секунд
                        # if current_time - last_update_time >= TG_RPL_MIN_INTERVAL:
                        #     download_percent = int(total_bytes_downloaded / file_from_user.file_size * 100)
                        #     await info_message_for_download.edit_text(
                        #         "📥 <b>Выполняю загрузку файла</b>\n"
                        #         f"<code>{file_from_user.file_name}</code>\n\n"
                        #         f"Загружно {total_bytes_downloaded / 1024 / 1024:.2f} МБ из {file_from_user.file_size / 1024 / 1024:.2f} МБ\n"
                        #         f"Прогресс: {download_percent}%\n"
                        #         f"last_update_time {last_update_time}\n"
                        #         f"current_time {current_time}"
                        #     )
                        # last_update_time = current_time

                # закончили загрузку
                await info_message_for_download.delete()

                # заносим путь к загруженному файлу в контекст текущего пользователя
                await state.update_data({SandboxInteractionsParameters.file_to_scan: save_path})

                # отвечаем юзеру и идем дальше
                logger.info(f"File {file_from_user.file_name} was succesfully downloaded to bot from user {message.from_user.id}")
                await message.answer(
                    f"✅ Файл <code>{file_from_user.file_name}</code> успешно загружен в бота!"
                )

                # запрашиваем ввод паролей для отправки задания на проверку, в любом случае в это состояние
                await message.answer(
                    "Если Вы знаете, что файлы зашифрованы паролем, укажите их сейчас, каждый с новой строки. Всего не более 5 паролей.\n"
                    "Если паролей нет, нажмите кнопку ниже.",
                    reply_markup=custom_keyboars.send_to_scan_keyboard
                )
                await state.set_state(SandboxInteractionStates.send_req_for_scan)
                return
            
            # ошибки, связанные с таймаутом ожидания загрузки файла пользователем
            except (TimeoutError, TelegramNetworkError) as download_error:
                # пытаемся сначала через указанное время секунд, если попытка не крайняя
                if download_attempt < MAX_DOWNLOAD_RETRIES - 1:
                    logger.warning(f"Attempt №{download_attempt + 1} to download file {file_from_user.file_name} from user {message.from_user.id} failed. Retrying in {DOWNLOADL_RETRY_TIME}.")
                    await asyncio.sleep(DOWNLOADL_RETRY_TIME)
                
                # если попытка всё таки крайняя - кидаем excpetrion выше
                else:
                    logger.error(f"Final attempt to download file {file_from_user.file_name} from user {message.from_user.id} failed.")
                    raise download_error
    
    # обработка если пользователь будет пытаться слишком часто загрузить файл
    except TelegramRetryAfter as e:
        logger.warning(f"Flood detected from user ID {message.from_user.id}. Retry in {e.retry_after} seconds")
        await message.answer(
            "⚠️ <b>Слишком много запросов!</b>\n\n"
            f"Пожалуйста, подождите {e.retry_after} секунд и попробуйте снова."
        )
        # отправляем юзера ждать
        await asyncio.sleep(e.retry_after)
        await message.answer("Можете попробовать снова отправить файл на проверку.")
        await state.set_state(SandboxInteractionStates.upload_file_to_scan)
        await state.update_data({SandboxInteractionsParameters.file_uploaded: False})
        return

    # обработка ошибок загрузки файла по таймауту
    except (TimeoutError, TelegramNetworkError) as e:
        user_data = await state.get_data()
        user_role = user_data.get(SandboxInteractionsParameters.user_role)
        reply_keyboard = custom_keyboars.admin_main_sandbox_keyboard if user_role == UsersRolesInBot.main_admin else custom_keyboars.user_main_sandbox_keyboard
        new_state = SandboxInteractionStates.sandbox_admin_menu if user_role == UsersRolesInBot.main_admin else SandboxInteractionStates.sandbox_user_menu
        
        logger.error(f"Network error while downloading file {file_from_user.file_name} from user {message.from_user.id}: {str(e)}")
        await message.answer(
            "⚠️ <b>Ошибка сети при загрузке файла!</b>\n\n"
            "Проблемы с соединением. Пожалуйста, попробуйте позже, отправьте файл меньшего размера или отправьте его через ссылку на скачивание из внешнего ресурса.",
            reply_markup=reply_keyboard
        )
        await state.set_state(new_state)
        await state.update_data({SandboxInteractionsParameters.file_uploaded: False})
        return

    # Прочие ошибки, которые не удалось отловить
    except TelegramBadRequest as e:
        user_data = await state.get_data()
        user_role = user_data.get(SandboxInteractionsParameters.user_role)
        reply_keyboard = custom_keyboars.admin_main_sandbox_keyboard if user_role == UsersRolesInBot.main_admin else custom_keyboars.user_main_sandbox_keyboard
        new_state = SandboxInteractionStates.sandbox_admin_menu if user_role == UsersRolesInBot.main_admin else SandboxInteractionStates.sandbox_user_menu

        if "file is too big" in str(e):
            logger.info(f"File {file_from_user.file_name} wasn't succesfully downloaded to bot from user {message.from_user.id} becouse of its large size")
            await message.answer(
                "⚠️ <b>Ошибка при загрузке файла!</b>\n\n"
                "Файл слишком большой",
                reply_markup=reply_keyboard
            )
        else:
            logger.error(f"File {file_from_user.file_name} wasn't succesfully downloaded to bot from user {message.from_user.id}", exc_info=True)
            await message.answer(
                f"⚠️ <b>Неожиданная ошибка при загрузке файла:</b> {str(e)}\n\n"
                "Свяжитесь с Администратором и перешлите ему это сообщение.",
                reply_markup=reply_keyboard
            )
        
        await message.answer("Выберите дальнейшее действие:")
        await state.set_state(new_state)
        return


# хэндлер обработки ввода паролей для распаковки
@dp.message(SandboxInteractionStates.send_req_for_scan)
async def send_data_to_scan(message: Message, state: FSMContext) -> None:
    
    # получаем пользовательский ввод паролей
    user_passwords_input: str = message.text

    if user_passwords_input is None:
        await message.answer(
            "⚠️ <b>Ожидался ввод паролей.</b>\n\n"
            "Сообщение не содержит текста."
        )
        await message.answer(
            "Напишите пароли повторно или отправьте задание на проверку без указания паролей.",
            reply_markup=custom_keyboars.send_to_scan_keyboard
        )
        await state.set_state(SandboxInteractionStates.send_req_for_scan)
        return

    # если ввод не равен "отправить сейчас на проверку" причем берем только первые 5 паролей
    list_of_pwds: list = []
    if user_passwords_input != custom_keyboars.BTN_SANDBOX_MENU_SEND_TO_SCAN:
        list_of_pwds = user_passwords_input.split('\n')[:5]
        await state.update_data({SandboxInteractionsParameters.list_of_pwds: list_of_pwds})
    
    # предварительно получаем параметры юзерочка из его же данных
    user_data = await state.get_data()
    user_role = user_data.get(SandboxInteractionsParameters.user_role)
    scan_priority = user_data.get(SandboxInteractionsParameters.scan_priority)
    can_get_links = user_data.get(SandboxInteractionsParameters.can_get_links)

    # определяем, что именно пользователь хочет отправить на проверку ссылку или файл
    scan_type = user_data.get(SandboxInteractionsParameters.scan_type)

    # если сканит ссылку
    if scan_type == "url":
        logger.info(f"User {message.from_user.id} sent link to scan")

        url_to_scan = user_data.get(SandboxInteractionsParameters.url_to_scan)
        # грузим это наконец то в песочницу
        scan_req: SendScanRequest = await ptsb_client.send_link_to_scan(
            checking_link=url_to_scan,
            check_priority=scan_priority,
            passwords=list_of_pwds
        )
    
    # если сканит файл
    elif scan_type == "file":
        logger.info(f"User {message.from_user.id} sent file to scan")

        file_to_scan = user_data.get(SandboxInteractionsParameters.file_to_scan)
        # опять грузим это в песочницу
        scan_req: SendScanRequest = await ptsb_client.send_file_to_scan(
            path_to_file_to_upload=file_to_scan,
            check_priority=scan_priority,
            passwords=list_of_pwds
        )
        
        # и в любом случае удалям файл от пользака
        if os.path.exists(file_to_scan):
            os.remove(file_to_scan)
            logger.info(f"File {file_to_scan} from user {message.from_user.id} was deleted from local storage")
        

    # если загрузилось не совсем удачно
    if not scan_req.is_ok:
        logger.warning(f"Scan request from user {message.from_user.id} was unsuccessful. Error: {scan_req.error_message}")

        reply_keyboard = custom_keyboars.admin_main_sandbox_keyboard if user_role == UsersRolesInBot.main_admin else custom_keyboars.user_main_sandbox_keyboard
        new_state = SandboxInteractionStates.sandbox_admin_menu if user_role == UsersRolesInBot.main_admin else SandboxInteractionStates.sandbox_user_menu

        await message.answer(
            "⚠️ Не удалось отправить запрос на проверку.\n\n"
            "Свяжитесь с администратором и передайте ему эту информацию:\n"
            f"{scan_req.error_message}",
            reply_markup=reply_keyboard
        )
        await state.set_state(new_state)
        return
    
    # если все таки удачно
    else:
        logger.info(f"Scan request from user {message.from_user.id} was successful")

        # уменьшаем количество проверок + увеличиваем общий счетчик
        decrease = await sandbox_profiles_functions.decrease_remaining_checks(
            tg_user_id=message.from_user.id,
            decrease_amount=1
        )
        increase = await sandbox_profiles_functions.increase_total_checks(
            tg_user_id=message.from_user.id,
            increase_amount=1
        )
        
        # проверка на то, что юзер существует
        if not decrease or not increase:
            logger.info(f"Tried to lower remaining checks for user {message.from_user.id}, but his profile was not found. Set state check_user_status for user")

            await state.clear()
            await state.set_state(UserStates.check_user_status)
            await message.answer(
                "⚠️ Кажется, доступ для Вас прекращен.",
                reply_markup=custom_keyboars.check_status_keyboard
            )
            return

        # отправляем сообщение что всё удалось с учетом того, можно ли юзеру получать результаты проверки или нет
        if can_get_links:
            # кнопка
            scan_button = InlineKeyboardButton(
                text = "Перейти к заданию",
                url = f"https://{PTSB_ROOT_ADDR}/tasks/{scan_req.scan_id}"
            )
            # клавиатура
            scan_keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[scan_button]]
            )
            await message.answer(
                "✅ <b>Задание успешно создано!</b>\n\n"
                f"Его ID: <code>{scan_req.scan_id}</code>.",
                reply_markup=scan_keyboard
            )

        else:
            await message.answer(
                "✅ <b>Задание успешно создано!</b>\n\n"
                f"Его ID: <code>{scan_req.scan_id}</code>.\n\n"
                "С ID задания Вы можете впоследствии обратиться к администратору, если потребуется уточнение по результатам проверки."
            )
        
        # заносим scan_id в параметры пользователя
        await state.update_data({SandboxInteractionsParameters.scan_id: scan_req.scan_id})
        
        # и говорим, чтоб пользователь проверял результаты сканирования
        await message.answer(
            "Для получения результатов проверки периодически обновляйте статус задания через кнопку ниже:",
            reply_markup=custom_keyboars.get_scan_results_keyboard
        )
        await state.set_state(SandboxInteractionStates.get_scan_results)
        return
    

# хэндлер для обновления статуса проверки задания
@dp.message(SandboxInteractionStates.get_scan_results, F.text == custom_keyboars.BTN_SANDBOX_MENU_SCAN_RESULT)
async def process_get_scan_result(message: Message, state: FSMContext) -> None:
    
    # получаем данные по scan_id, который нужно проверить
    user_data = await state.get_data()
    scan_id_to_get = user_data.get(SandboxInteractionsParameters.scan_id)
    scan_results: GetScanResust = await ptsb_client.get_scan_results(
        scan_id=scan_id_to_get
    )

    # а также клавиатуру, и состояние, которую нужно будет отрисовать на основании роли
    user_role = user_data.get(SandboxInteractionsParameters.user_role)
    reply_keyboard = custom_keyboars.admin_main_sandbox_keyboard if user_role == UsersRolesInBot.main_admin else custom_keyboars.user_main_sandbox_keyboard
    new_state = SandboxInteractionStates.sandbox_admin_menu if user_role == UsersRolesInBot.main_admin else SandboxInteractionStates.sandbox_user_menu

    # если API запрос неуспешный
    if scan_results.is_ok == False:
        logger.warning(f"User {message.from_user.id} tried to get status for scan_id={scan_id_to_get}, but was unsuccessful. Error: {scan_results.error_message}")

        await message.answer(
            "⚠️ Не удалось получить результаты.\n\n"
            "Свяжитесь с администратором и передайте ему эту информацию:\n"
            f"{scan_results.error_message}",
            reply_markup=reply_keyboard
        )
        await state.set_state(new_state)
        return
    
    else:
        if scan_results.is_scan_ready == False:
            await message.answer(
                "⏳ Результаты еще не получены.\n\nПовторная попытка доступна через 10 секунд.",
                reply_markup=ReplyKeyboardRemove()
            )
            await asyncio.sleep(10)
            await message.answer(
                "Вы можете снова получить результаты проверки:",
                reply_markup=custom_keyboars.get_scan_results_keyboard
            )
            await state.set_state(SandboxInteractionStates.get_scan_results)
            return
        
        else:
            # клавиатура на будущее, будем ли использовать зависит от роли пользователя
            scan_keyboard = None
            can_get_links = user_data.get(SandboxInteractionsParameters.can_get_links) 

            # создаем кнопку под сообщением, мол перейди к заданию
            if can_get_links:
                # кнопка
                scan_button = InlineKeyboardButton(
                    text = "Перейти к заданию",
                    url = f"https://{PTSB_ROOT_ADDR}/tasks/{scan_id_to_get}"
                )
                # клавиатура
                scan_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[[scan_button]]
                )

            # в любом случае возвращаем результаты проверки
            await message.answer(
                "✅ <b>Проверка завершена!</b>\n\n"
                f"<b>Статус:</b> {scan_results.scan_state}\n"
                f"<b>Вердикт</b>: {scan_results.verdict}\n"
                f"<b>Тип ВПО</b>: {scan_results.threat}\n",
                reply_markup=scan_keyboard
            )

            await message.answer(
                "Выберите дайльнейшее действие:",
                reply_markup=reply_keyboard
            )
            await state.set_state(new_state)
            return


# заглушка 
@dp.message()
async def echo_handler(message: Message, state: FSMContext) -> None:
    
    # получаем состояние пользователя
    user_state = await state.get_state()

    # проверяем, что state не существует
    if user_state is None:
        await message.answer(
            "⚠️ <b>Что-то пошло не так!</b>\n\n"
            "Либо ты новенький, либо бот перезапускался администратором.\n\nДля перехода к начальному меню отправь мне /start.",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        logger.info(f"User {message.from_user.id} made something, that putted him to default echo_handler")
        await message.answer(
            "⚠️ <b>Что-то пошло не так!</b>\n\n"
            "Если ты видишь это сообщение, ты сделал что-то не так, как я попросил тебя на предыдущем шаге. Повтори, пожалуйста, действие и сделай это так, как я тебя попросил."
        )
        await state.set_state(user_state)
        return


# главный мейн цикл, где запускается бот, с которым дальше будет идти работа
async def main() -> None:

    # создаем таблицу пользователей, если таблцы пользователей не существует
    await users_functions.create_table_if_not_exists()
    await sandbox_profiles_functions.create_table_if_not_exists()

    logger.info("Default app db was created and all needed tables in it")

    # добавляем первого админа бота в БД перед тем, как бот запустится, если он НЕ существует в БД
    first_admin_entity: AppUserFromDb = await users_functions.get_user_entity(FIRST_BOT_ADMIN_ID)
    if first_admin_entity is None:
        logger.info(f"Main admin {FIRST_BOT_ADMIN_ID} was not in app db, so adding him to db")    
    
        # базовый профиль пользователя
        await users_functions.add_new_user(
            tg_user_id=FIRST_BOT_ADMIN_ID,
            user_role=UsersRolesInBot.main_admin,
            comment="Владелец бота, созданный автоматически",
            created_by=FIRST_BOT_ADMIN_ID
        )

        # профиль взаимодействия с песочницей
        await sandbox_profiles_functions.add_new_profile(
            FIRST_BOT_ADMIN_ID,
            1_000_000,
            4,
            1
        )
    
    # шэдулер на обновление количества попыток
    logger.info("Setting up scheduler to renew amount of remaining_checks for all users")
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")  # TODO можно указать нужный TZ
    scheduler.add_job(
        sandbox_profiles_functions.daily_reset_remaining_checks,
        CronTrigger(hour=0, minute=0),
        misfire_grace_time=60 * 60,
        coalesce=True,
        max_instances=1
    )
    scheduler.start()
    
    # инициализация бота через апи токен бота
    logger.info("Initializing tg bot entity")
    bot = Bot(
        token=TG_BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML)
        )

    # And the run events dispatching
    logger.info("Starting tg bot entity")
    await dp.start_polling(bot)


# INT MAIN() дань классике
if __name__ == "__main__":
    
    # запуск мейна в асинке, т.к. бот выполняется асинхронно, а мейн по умолчанию запускается синхронно
    logger.info("Starting up application")
    asyncio.run(main())