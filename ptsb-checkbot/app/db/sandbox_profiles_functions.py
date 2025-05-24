# встроенные либы
import os

# встроенные классы
from dataclasses import dataclass
from typing import Union

# устанавливаемые либы
import aiosqlite


# задаем путь до БД приложения
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_DIR = os.path.join(PROJECT_ROOT, "database")
DB_NAME = "kernel_base.db"
FULL_PATH_TO_KERNEL_DB = os.path.join(DB_DIR, DB_NAME)

# инициализируем директорию к БД и саму по себе БД
if not os.path.exists(DB_DIR):
    os.mkdir(DB_DIR)
if not os.path.exists(FULL_PATH_TO_KERNEL_DB):
    with open(FULL_PATH_TO_KERNEL_DB, "w"):
        pass

# название таблицы для этого модуля
TABLE_NAME = "sandbox_profiles"

# самописные классы
@dataclass
class UserProfileFromDb:
    """
    Классс, возвращающий профиль пользователя при работе с ptsb из таблицы `sandbox_profiles`
    """
    tg_user_id: int
    max_available_checks: int
    remaining_checks: int
    total_checks: int
    check_priority: int
    can_get_links: bool


# функция инициализации таблицы с профилями подключения к песочнице и бла бла бла
async def create_table_if_not_exists() -> None:
    """
    Создает таблицу `sandbox_profiles` если ее еще не существует в БД приложения
    """

    async with aiosqlite.connect(FULL_PATH_TO_KERNEL_DB) as db:
        await db.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                tg_user_id INTEGER,
                max_available_checks INTEGER,
                remaining_checks INTEGER,
                total_checks INTEGER,
                check_priority INTEGER,
                can_get_links INTEGER
            )
        """)


# функция создания профиля пользователя для работы с ptsb
async def add_new_profile(
    tg_user_id: int,
    max_available_checks: int,
    check_priority: int,
    can_get_links: int
    ) -> None:
    """
    Добавляет новый профиль пользователя в таблицу `sandbox_profiles` у БД приложения

    Принимает:
        - `tg_user_id` (int): TG ID пользователя
        - `max_available_checks` (int): Количество проверок, доступное в один день 
        - `check_priority` (int): Приоритет проверки пользователя [1, 4]
        - `can_get_links` (int): Может ли получать ссылки на проверенные задания `0` - нет, `1` - да
    """

    async with aiosqlite.connect(FULL_PATH_TO_KERNEL_DB) as profiles_db:
        await profiles_db.execute(f"""
            INSERT INTO {TABLE_NAME} (
                tg_user_id,
                max_available_checks,
                remaining_checks,
                total_checks,
                check_priority,
                can_get_links
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (tg_user_id,  max_available_checks, max_available_checks, 0, check_priority, can_get_links)
        )
        
        await profiles_db.commit()


# функция получения профиля пользователя взаимодействия с песочницей
async def get_profile_entity(
        tg_user_id: int
    ) -> Union[None, UserProfileFromDb]:
    """
    Выполняет запрос к БД приложения, чтобы получить профиль пользователя взаимодействия с песочницей.

    Принимает:
        - `tg_user_id` (int): TG ID пользователя, данные по которому нужно достать
    
    Возвращает:
        - `UserProfileFromDb` (object of custom class): профиль как объект класса
        - `None`, если профиля с `tg_user_id` не существует 
    """

    async with aiosqlite.connect(FULL_PATH_TO_KERNEL_DB) as profiles_db:
        cursor = await profiles_db.execute(f'SELECT * FROM {TABLE_NAME} WHERE tg_user_id = ?', (tg_user_id,))
        data = await cursor.fetchone()

        if data is not None:
            return UserProfileFromDb(
                tg_user_id=data[0],
                max_available_checks=data[1],
                remaining_checks=data[2],
                total_checks=data[3],
                check_priority=data[4],
                can_get_links=bool(data[5])
            )
        else:
            return None


# функция удаления профиля пользователя взаимодействия с песком
async def delete_profile_by_id(tg_user_id: int) -> None:
    """
    Выполняет запрос в таблицу `sandbox_profiles`, чтобы удалить профиль по TG ID

    Принимает:
        - `tg_user_id` (int): TG ID пользователя, которого нужно удалить
    """

    async with aiosqlite.connect(FULL_PATH_TO_KERNEL_DB) as profiles_db:
        await profiles_db.execute(f'DELETE FROM {TABLE_NAME} WHERE tg_user_id = ?', (tg_user_id,))
        await profiles_db.commit()


# функция для уменьшения remaining_cheks на 1 в результате успешной загрузки чего-либо на проверку
async def decrease_remaining_checks(tg_user_id: int, decrease_amount: int) -> bool:
    """
    Уменьшает количество оставшихся проверок для конкретноого пользователя из таблицы `sandbox_profiles`

    Принимает:
        - `tg_user_id` (int): TG ID пользователя для профиля которого нужно уменьшить 
        - `decrease_amount` (int): на сколько нужно уменьшить кол-во проверок для юзера

    Возвращает:
        `bool`: удалось ли выполнить операцию или нет.
    """
    async with aiosqlite.connect(FULL_PATH_TO_KERNEL_DB) as profiles_db:
        # получаем юзера, для которого уменьшаем количество проверок
        row = await profiles_db.execute(
            f'SELECT remaining_checks FROM {TABLE_NAME} WHERE tg_user_id = ?',
            (tg_user_id,)
        )
        data = await row.fetchone()

        if data is None:
            return False

        # уменьшаем количество проверок, но если уходим ниже 0, на всякий случай делаем 0. защита.
        new_checks = max(data[0] - decrease_amount, 0)

        # уменьшаем количество проверок
        await profiles_db.execute(
            f'UPDATE {TABLE_NAME} SET remaining_checks = ? WHERE tg_user_id = ?',
            (new_checks, tg_user_id)
        )
        await profiles_db.commit()

    return True
    

# функция увеличения общего количества проверок
async def increase_total_checks(tg_user_id: int, increase_amount: int) -> bool:
    """
    Увеличивает суммарное количество проверок для конкретноого пользователя из таблицы `sandbox_profiles`

    Принимает:
        - `tg_user_id` (int): TG ID пользователя для профиля которого нужно уменьшить 
        - `increase_amount` (int): на сколько нужно увеличить общее кол-во

    Возвращает:
        `bool`: удалось ли выполнить операцию или нет.
    """

    async with aiosqlite.connect(FULL_PATH_TO_KERNEL_DB) as profiles_db:
        row = await profiles_db.execute(
            f'SELECT total_checks FROM {TABLE_NAME} WHERE tg_user_id = ?',
            (tg_user_id,)
        )
        data = await row.fetchone()

        if data is None:
            return False
        
        new_value = data[0] + 1

        await profiles_db.execute(
            f'UPDATE {TABLE_NAME} SET total_checks = ? WHERE tg_user_id = ?',
            (new_value,tg_user_id)
        )
        await profiles_db.commit()
    
    return True


# функция восстановления количества попыток каждый день
async def daily_reset_remaining_checks() -> None:
    """
    Раз в `UPDATE_TIME` секунд восстанавливает всем попытки
    """

    try:
        async with aiosqlite.connect(FULL_PATH_TO_KERNEL_DB) as profiles_db:
            await profiles_db.execute(f"""
                UPDATE {TABLE_NAME}
                set remaining_checks = max_available_checks
            """)
            
            await profiles_db.commit()

    except Exception as e:
        print(f"Возникла ошибка при обновлении статусов пользователям: {e}")