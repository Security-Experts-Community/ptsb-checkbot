# встроенные классы
from typing import Union, Optional
from dataclasses import dataclass

# устанавливаемые библиотеки
import httpx

# устанавливаемые классы
from aiogram.exceptions import TelegramRetryAfter


# самописный класс с информацией о том, какой объем файла уже скачался


async def download_file_by_chunks(
        tg_
) -> Union[bool, ]:
    
    pass