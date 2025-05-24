# встроенные либы
import os

# встроенные классы
from datetime import date
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
TABLE_NAME = "users"

# самописные классы
@dataclass
class AppUserFromDb:
    """
    Классс, создающий объект-пользователя, параметры которого достаются из таблицы `users` приложения.
    """
    tg_user_id: int
    user_role: str
    comment: str
    created_by: int
    creation_date: str
    update_date: str
    is_blocked: bool


# функция инициализации таблицы пользователей, если ее еще не существует в БД
async def create_table_if_not_exists() -> None:
    """
    Создает таблицу `users`, если ее не существует в БД
    """
    
    # подключаемся к БД и создаем таблицу если ее не существует
    async with aiosqlite.connect(FULL_PATH_TO_KERNEL_DB) as db:
        await db.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                tg_user_id INTEGER,
                user_role TEXT,
                comment TEXT,
                created_by INTEGER,
                creation_date TEXT,
                update_date TEXT,
                is_blocked INTEGER
            )
        """)


# фукнция добавления нового пользователя в таблицу пользователей:
async def add_new_user(
    tg_user_id: int,
    user_role: str,
    comment: str,
    created_by: int
    ) -> None:
    """
    Добавляет нового пользователя в таблицу `users` базы данных приложения

    Принимает:
        - `tg_user_id` (int): ID пользователя, который будет добавлен
        - `user_role` (str): Роль (права) пользователя в приложении
        - `comment` (str): Примечание насчет пользователя
        - `created_by` (int): TG ID создателя пользователя
    """

    # текущая дата
    current_date = f"{date.today().strftime('%d-%B-%Y')}"

    async with aiosqlite.connect(FULL_PATH_TO_KERNEL_DB) as users_db:
        await users_db.execute(f"""
            INSERT INTO {TABLE_NAME} (
                tg_user_id,
                user_role,
                comment,
                created_by,
                creation_date,
                update_date,
                is_blocked
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (tg_user_id, user_role, comment, created_by, current_date, current_date, 0)
        )
        await users_db.commit()


# функция возвращающая пользователя как объект класса AppUserFromDb по результату выполнения SQL запроса
async def get_user_entity(
        tg_user_id: int
    ) -> Union[None, AppUserFromDb]:
    """
    Выполняет запрос в БД с пользователями, чтобы постараться вернуть пользователя как объект класса `AppUserFromDb`

    Принимает:
        - `tg_user_id` (int): TG ID пользователя, данные по которому нужно достать
    
    Возвращает:
        - `AppUserFromDb` (object of custom class): пользователя как объект класса с параметрами пользователя из БД в данный момент
        - `None`, если пользователя с `tg_user_id` не существует 
    """
    
    # подключаемся к БД, пытаемся получить фидбек по tg id
    async with aiosqlite.connect(FULL_PATH_TO_KERNEL_DB) as users_db:
        cursor = await users_db.execute(f'SELECT * FROM {TABLE_NAME} WHERE tg_user_id = ?', (tg_user_id,))
        data = await cursor.fetchone()
        if data is not None:
            return AppUserFromDb(
                tg_user_id=data[0],
                user_role=data[1],
                comment=data[2],
                created_by=data[3],
                creation_date=data[4],
                update_date=data[5],
                is_blocked=bool(data[6])
            )
        else:
            return None
        

# функция, возвращающая список пользователей, описание которых подходит под match
async def fetch_all_users_with_filter(comment_filter: str = "") -> list[AppUserFromDb]:
    """
    Возвращает список пользователей, которые созданы в БД приложения. Если указывается фильтр при запросе, возвращет только пользователей, подходящих по описанию.

    Принимает:
        - `comment_filter` (str): часть текста, которая может содержаться в описании пользователя (поле `comment`)
    
    Возвращает:
        - `list[AppUserFromDb]` (list): набор пользователей как объекты класса с параметрами пользователя из БД в данный момент. В случае, если нет пользователей, подходящих под фильтр, вернет пустой список.
    """
    # итоговый список пользователей
    list_of_users: list[AppUserFromDb] = []

    # подключаемся к БД
    async with aiosqlite.connect(FULL_PATH_TO_KERNEL_DB) as users_db:
        # меняем выборку в зависимости от того, есть ли фильтр
        if comment_filter:
            cursor = await users_db.execute(
                f"SELECT * FROM {TABLE_NAME} WHERE comment like ?",
                (f"%{comment_filter}%",)
            )
        else:
            cursor = await users_db.execute(f"SELECT * FROM {TABLE_NAME}")
            
        raws_of_users = await cursor.fetchall()
        for row_user in raws_of_users:
            list_of_users.append(
                AppUserFromDb(
                    tg_user_id=row_user[0],
                    user_role=row_user[1],
                    comment=row_user[2],
                    created_by=row_user[3],
                    creation_date=row_user[4],
                    update_date=row_user[5],
                    is_blocked=bool(row_user[6])
                )
            )
            
        return list_of_users


# функция блокировки/разблокировки пользователя по tg id
async def change_user_state_by_id(
        tg_user_id: int,
        new_state: int
    ) -> None:
    """
    Выполняет запрос в БД с пользователями, чтобы изменить статус пользователя по ID (заблокирован/разблокирован).

    Принимает:
        - `tg_user_id` (int): TG ID пользователя, статус которого нужно поменять.
        - `new_state` (int): 0 - разбанен, 1 - забанен.
    """
    
    # текущая дата
    current_date = f"{date.today().strftime('%d-%B-%Y')}"

    # подключаемся к БД, пытаемся обновить статус пользователя = забанить/разбанить
    async with aiosqlite.connect(FULL_PATH_TO_KERNEL_DB) as users_db:
        await users_db.execute(f"""
            UPDATE {TABLE_NAME}
            SET is_blocked = ?, update_date = ?
            WHERE tg_user_id = ?
        """, (new_state, current_date, tg_user_id)
        )
        await users_db.commit()


# функция удаления пользователя по tg id
async def delete_user_by_id(
        tg_user_id: int
    ) -> None:
    """
    Выполняет запрос в таблицу с пользователями, чтобы удалить пользователя по TG ID

    Принимает:
        - `tg_user_id` (int): TG ID пользователя, которого нужно удалить
    """

    # подключаемся к БД, пытаемся удалить пользователя
    async with aiosqlite.connect(FULL_PATH_TO_KERNEL_DB) as users_db:
        await users_db.execute(f"DELETE FROM {TABLE_NAME} WHERE tg_user_id = ?", (tg_user_id,))
        await users_db.commit()