### либы
## встроенные
import os


### классы
## устанавливаемые
# для настройки работы прокси
from aiogram.client.session.aiohttp import AiohttpSession   # сессия через проксю
from aiohttp import BasicAuth                               # авторизация на проксе


### константы
# использование прокси
PROXY_ADDR = str(os.getenv('PROXY_ADDR'))           # адрес прокси сервера
PROXY_PORT = str(os.getenv('PROXY_PORT'))           # порт подключения
PROXY_USER = str(os.getenv('PROXY_USER'))           # пользователь подключения
PROXY_PASSWORD = str(os.getenv('PROXY_PASSWORD'))   # пароль для авторизации


# создание сессии с серверами ТГ #TODO поддержка доп протоколов
def create_session_to_tg() -> AiohttpSession:
    """
    Функция создания подключения к серверам ТГ. Может определять прокси сервер для подключения.

    Возвращает:
        `AiohttpSession`: Сессия с настроенными параметрами подключения.
    """
    
    session_kwargs = {}
    
    # поддержка использования прокси при подключении к ТГ
    if PROXY_ADDR:
        # формируем url
        proxy_url = f"socks5://{PROXY_ADDR}:{PROXY_PORT}/"
        
        # добавляем авторизацию при необходимости
        if PROXY_USER:
            proxy_auth = BasicAuth(login=PROXY_USER, password=PROXY_PASSWORD) if PROXY_USER else None
            session_kwargs['proxy'] = (proxy_url, proxy_auth)
        else:
            session_kwargs['proxy'] = proxy_url

    return AiohttpSession(**session_kwargs)