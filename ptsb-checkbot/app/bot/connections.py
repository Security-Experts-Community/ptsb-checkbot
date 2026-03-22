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
PROXY_ADDR = str(os.getenv('PROXY_ADDR')) if os.getenv('PROXY_ADDR') else None  # адрес прокси серверa
PROXY_PORT = str(os.getenv('PROXY_PORT')) if os.getenv('PROXY_PORT') else None  # порт подключения
PROXY_USER = str(os.getenv('PROXY_USER')) if os.getenv('PROXY_USER') else None  # пользователь подключения
PROXY_PASS = str(os.getenv('PROXY_PASS')) if os.getenv('PROXY_PASS') else None  # пароль для авторизации


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
            proxy_auth = BasicAuth(login=PROXY_USER, password=PROXY_PASS) if PROXY_USER else None
            session_kwargs['proxy'] = (proxy_url, proxy_auth)
        else:
            session_kwargs['proxy'] = proxy_url

    return AiohttpSession(**session_kwargs)