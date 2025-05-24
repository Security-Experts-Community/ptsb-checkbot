# встроенные библиотеки
import json
import os
import urllib3

# устанавливаемые библиотеки
import httpx

# встроенные классы
from urllib.parse import urlencode, quote
from dataclasses import dataclass
from typing import Optional


### параметры подключения к песочнице
# использовать или не использовать проверку подлинности SSL
VERIFY_SSL_CONNECTIONS = bool(int(os.getenv('VERIFY_SSL_CONNECTIONS')))
if not VERIFY_SSL_CONNECTIONS:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# адрес песочницы
PTSB_ROOT_ADDR = str(os.getenv('PTSB_ROOT_ADDR'))
PTSB_TOKEN = str(os.getenv('PTSB_TOKEN'))


# кастомный класс для получения результатов загрузки файла на проверку 
@dataclass
class SendScanRequest:
    """
    Класс, применяемый для создания объектов содержащих параметры `response`, полученных в результате отправки API запросов на проверку ссылок или файлов в сторону PTSB.
    """
    is_ok: bool
    scan_id: Optional[str] = None
    error_message: Optional[str] = None


# кастомный класс для получения результатов проверки файла
@dataclass
class GetScanResust:
    """
    Класс, применяемый для получения результатов проверки файла по предварительному запросу на проверку
    """
    is_ok: bool
    is_scan_ready: Optional[bool] = None
    error_message: Optional[str] = None
    scan_state: Optional[str] = None
    threat: Optional[str] = None
    verdict: Optional[str] = None
    scan_error: Optional[str] = None


# кастомный класс для парсинга (маппинга) результатов проверки на описание результатов проверки
@dataclass
class ScanVerdictMapper:
    """
    Класс, применяемый для маппинга результатов проверки файла/ссылки из API ответов на расширенное описание ответов
    """
    SCAN_STATES = {
        "FULL": "Проверка выполнена полностью.",
        "PARTIAL": "Проверка выполнена частично.",
        "UNSCANNED": "Не удалось выполнить проверку."
    }

    VERDICTS = {
        "CLEAN": "Угроз не обнаружено.",
        "UNWANTED": "Потенциально опасный объект.",
        "DANGEROUS": "Опасный объект."
    }

    ERROR_TYPES = {
        "corrupted": "В задании попался повреждённый объект (например, архив).",
        "encrypted": "Зашифрованный объект, не удалось подобрать пароль для расшифровки.",
        "internal": "Внутренняя ошибка средства проверки.",
        "max_depth_exceeded": "Превышена вложенность распаковки архива.",
        "sandbox_run_sample": "Ошибка при запуске поведенческого анализа."
    }

    @classmethod
    def get_state_desc(cls, scan_state: str) -> str:
        return cls.SCAN_STATES.get(scan_state)

    @classmethod
    def get_verdict_desc(cls, verdict: str) -> str:
        return cls.VERDICTS.get(verdict)
    
    @classmethod
    def get_error_desc(cls, error_type: str) -> str:
        return cls.ERROR_TYPES.get(error_type)


# кастомный класс для получения состояния API
@dataclass
class ApiHeathCheck:
    """
    Класс, применяемый для просмотра ответов от хэлсчека API PTSB
    """
    is_ok: bool
    error_message: Optional[str] = None
    

# кастомный класс с известными ошибками в ptsb
class CommonKnownErrors:
    """
    Класс, c описанием ошибок, с которыми можно столкнуться при отправке запросов в API PTSB
    """
    error_401 = "Ошибка 401. Не удалось авторизоваться в PTSB с заданным токеном доступа."
    error_403 = "Ошибка 403. Для переданного в запросе токена доступа среди разрешенных действий не выбрана «Проверка с параметрами источника»."
    error_404 = "Ошибка 404. Задание на проверку файла не найдено; возможно, оно было создано более трех часов назад и завершилось с ошибкой."
    error_405 = "Ошибка 405. Неверно указан метод запроса."
    error_413 = "Ошибка 413. Размер запроса превышает установленное ограничение."
    ssl_error = "Ошибка при проверке подлинности сертификата. Возможно, сертификат PTSB не является доверенным или между ботом и PTSB стоит SSL proxy."
    conn_error = "Ошибка соединения с PTSB. Возможно, сервис недоступен."
    timeout_error = "Таймаут подключения. Не удалось подключиться к PTSB за 10 секунд ожидания."



# функция загрузки файлов на проверку в ptsb TODO переписать парсинг ошибок в соответствии с healthcheck
async def send_file_to_scan(
        path_to_file_to_upload: str,
        check_priority: int,
        passwords: list[str] = None
    ) -> SendScanRequest:
    """
    Отправляет файл на проверку в PTSB. Загружает файл на проверку в асинхронном режиме и дожидается результатов проверки.
    
    Параметры:
        - `path_to_file_to_upload` (str): Полный путь к файлу, который будет отправлен на проверку в PTSB.
        - `check_priority` (int): Приоритет проверки файлов от этого пользователя.
        - `passwords` (list[str]): Набор паролей для распаковки (опциональное), по умолчанию отсутствует.

    Возвращает:
        - `SendScanResust` (object of custom class): Объект класса `SendScanResust`, содержащий информацию о `scan_id` созданного задания на проверку, либо `error_message` с описанием ошибки. 
    """

    # формируем параметры запроса
    request_headers = {
        'X-API-Key': PTSB_TOKEN
    }
    scan_parameters = {
        'async_result': 'true',
        'short_result': 'true',
        'priority': check_priority
    }
    
    #формируем URL для обращения на endpoint метод для запуска проверки файла
    scan_file_url = f"https://{PTSB_ROOT_ADDR}/api/v1/scan/checkFile"

    # добавляем к ней параметры проверки
    full_scan_file_url = f"{scan_file_url}?{urlencode(scan_parameters)}"

    # добавляем к ней пароли
    if passwords:
        passwords_json = json.dumps(passwords)
        passwords_encoded = quote(passwords_json, safe='')
        full_scan_file_url += f"&passwords_for_unpack={passwords_encoded}"

    try:
        async with httpx.AsyncClient(verify=VERIFY_SSL_CONNECTIONS, timeout=60) as async_client:
            with open(path_to_file_to_upload, 'rb') as file_to_upload:
                files = {
                    'file': (file_to_upload)
                }

                response = await async_client.post(
                    full_scan_file_url,
                    headers=request_headers,
                    files=files
                )
            
        # если http статус код 200, то возвращаем результат и не паримся дальше
        if response.status_code == 200:
            response_data = response.json()
            current_scan_id = response_data.get("data", {}).get("scan_id")
            return SendScanRequest(is_ok=True, scan_id=current_scan_id)

        # если http статус код 401
        if response.status_code == 401:
            return SendScanRequest(is_ok=False, error_message=CommonKnownErrors.error_401)
        
        # если http статус код 403:
        if response.status_code == 403:
            return SendScanRequest(is_ok=False, error_message=CommonKnownErrors.error_403)

        # если http статус код 413:
        if response.status_code == 413:
            return SendScanRequest(is_ok=False, error_message=CommonKnownErrors.error_413)

        # если ошибок нет в http, то проверяем, есть ли ошибки в response с запросом на проверку ссылки
        response_data = response.json()
        if response_data.get("errors"):
            error_message = response_data["errors"][0].get("message", f"Не удалось определить причину ошибки.\nОтвет в сыром виде:{response.text}")
            return SendScanRequest(is_ok=False, error_message=error_message)

    # обрабатываем ошибки, которые больше по сетевой части, нежели по состоянию АПИ песка
    except httpx.ConnectError as e:
        if "CERTIFICATE_VERIFY_FAILED" in str(e).upper():
            return SendScanRequest(is_ok=False, error_message=CommonKnownErrors.ssl_error)
        return SendScanRequest(is_ok=False, error_message=CommonKnownErrors.conn_error)
    
    except httpx.ConnectTimeout:
        return SendScanRequest(is_ok=False, error_message=CommonKnownErrors.timeout_error)
    
    except httpx.RequestError as e:
        return SendScanRequest(is_ok=False, error_message=f"Ошибка выполнения запроса: {e}")

    except Exception as e:
        return SendScanRequest(is_ok=False, error_message=f"Неизвестная ошибка: {e}")




# функция загрузки ссылок на проверку в ptsb
async def send_link_to_scan(
        checking_link: str,
        check_priority: int,
        passwords: list[str] = None
    ) -> SendScanRequest:
    """
    Отправляет файл на проверку в PTSB. Загружает файл на проверку в асинхронном режиме и дожидается результатов проверки.
    
    Параметры:
        - `checking_link` (str): Ссылка, которая будет отправлена на проверку в PTSB.
        - `check_priority` (int): Приоритет проверки ссылок для этого пользователя.
        - `passwords` (list[str]): Набор паролей для распаковки (опциональное), по умолчанию отсутствует. 
    Возвращает:
        - `SendScanResust` (object of custom class): Объект класса `SendScanResust`, содержащий информацию о `scan_id` созданного задания на проверку, либо `error_message` с описанием ошибки. 
    """

    try:
        # парметры запроса отправки на проверку
        request_headers = {
            'X-API-Key': PTSB_TOKEN
        }
        scan_parameters = {
            'async_result': 'true',
            'short_result': 'true',
            'priority': check_priority,
            'url': checking_link 
        }

        # формируем ссылку до сервиса проверки ссылок
        check_links_url = f"https://{PTSB_ROOT_ADDR}/api/v1/scan/checkURL"

        # добавляем пароли, если требуется
        if passwords:
            # сериализуем список паролей в JSON и затем URL-кодируем его
            passwords_json = json.dumps(passwords)
            passwords_encoded = quote(passwords_json, safe='')
            check_links_url += f"?passwords_for_unpack={passwords_encoded}"

        # открываем подключение, отправляем запрос
        async with httpx.AsyncClient(verify=VERIFY_SSL_CONNECTIONS, timeout=10) as check_url_conn:
            response = await check_url_conn.post(check_links_url, headers=request_headers, json=scan_parameters)

        # если http статус код 200, то возвращаем результат и не паримся дальше
        if response.status_code == 200:
            response_data = response.json()
            current_scan_id = response_data.get("data", {}).get("scan_id")
            return SendScanRequest(is_ok=True, scan_id=current_scan_id)

        # если http статус код 401
        if response.status_code == 401:
            return SendScanRequest(is_ok=False, error_message=CommonKnownErrors.error_401)
        
        # если http статус код 403:
        if response.status_code == 403:
            return SendScanRequest(is_ok=False, error_message=CommonKnownErrors.error_403)

        # если http статус код 413:
        if response.status_code == 413:
            return SendScanRequest(is_ok=False, error_message=CommonKnownErrors.error_413)

        # если ошибок нет в http, то проверяем, есть ли ошибки в response с запросом на проверку ссылки
        response_data = response.json()
        if response_data.get("errors"):
            error_message = response_data["errors"][0].get("message", f"Не удалось определить причину ошибки.\nОтвет в сыром виде:{response.text}")
            return SendScanRequest(is_ok=False, error_message=error_message)

    # обрабатываем ошибки, которые больше по сетевой части, нежели по состоянию АПИ песка
    except httpx.ConnectError as e:
        if "CERTIFICATE_VERIFY_FAILED" in str(e).upper():
            return SendScanRequest(is_ok=False, error_message=CommonKnownErrors.ssl_error)
        return SendScanRequest(is_ok=False, error_message=CommonKnownErrors.conn_error)
    
    except httpx.ConnectTimeout:
        return SendScanRequest(is_ok=False, error_message=CommonKnownErrors.timeout_error)
    
    except httpx.RequestError as e:
        return SendScanRequest(is_ok=False, error_message=f"Ошибка выполнения запроса: {e}")

    except Exception as e:
        return SendScanRequest(is_ok=False, error_message=f"Неизвестная ошибка: {e}")


# отпрвка запроса на получение результатов сканирования по scan_id
async def get_scan_results(
    scan_id: str
    ) -> GetScanResust:
    """
    Получает результаты проверки задания по его `scan_id`.
    
    Параметры:
        - `scan_id` (str): ID задания, результаты которого нужно получить
    
    Возвращает:
        - `GetScanResust` (object of custom class): Объект класса `GetScanResust` c информацией о результатах запроса
    """
    
    try:
        # параметры запроса для получения вердикта по сканированию по scan_id
        request_headers = {
            'X-API-Key': PTSB_TOKEN
        }
        request_parameters = {
            'scan_id': scan_id
        }

        # формируем ссылку до сервиса получаения результатов
        get_results_url = f"https://{PTSB_ROOT_ADDR}/api/v1/scan/getStatus"

        # отправляем запрос
        async with httpx.AsyncClient(verify=VERIFY_SSL_CONNECTIONS, timeout=10) as get_res_conn:
            response = await get_res_conn.post(get_results_url, headers=request_headers, json=request_parameters)
        
        # смотрим, что пришел ответ со статус кодом 200
        if response.status_code == 200:
            response_data = response.json()
            # проверяем, что блок данных result существует
            result_data = response_data.get("data", {}).get("result") 
            if result_data:
                # получаем статус проведенного сканирования
                scan_state = result_data.get("scan_state")
                scan_state = ScanVerdictMapper.get_state_desc(scan_state)
                # получаем вердикт по заданию
                verdict = result_data.get("verdict")
                verdict = ScanVerdictMapper.get_verdict_desc(verdict)
                # угрозу тоже получаем, но ни на что не маппим
                threat = result_data.get("threat") if result_data.get("threat") else "Безопасный."
                errors = response_data.get("data", {}).get("result", {}).get("errors")
                #  если есть информация про ошибки в результатах сканирования
                if errors:
                    # и ошибки тоже маппим
                    scan_error = errors.get("type")
                    scan_error = ScanVerdictMapper.get_error_desc(scan_error)

                    return GetScanResust(is_ok=True, is_scan_ready=True, scan_state=scan_state, threat=threat, verdict=verdict, scan_error=scan_error)
                return GetScanResust(is_ok=True, is_scan_ready=True, scan_state=scan_state, threat=threat, verdict=verdict)
            else:
                # оповещаем, что результатов сканирования еще нет
                return GetScanResust(is_ok=True, is_scan_ready=False)
            
        # если какой угодно ответ, но не 200
        # если ошибка 401
        if response.status_code == 401:
            return GetScanResust(is_ok=False, error_message=CommonKnownErrors.error_401)

        # если ошибка 404
        if response.status_code == 404:
            return GetScanResust(is_ok=False, error_message=CommonKnownErrors.error_404)
        
        # если ошибка 405
        if response.status_code == 405:
            return GetScanResust(is_ok=False, error_message=CommonKnownErrors.error_405)
        
        # если мы никуда вообще не попали
        return GetScanResust(is_ok=False, error_message="Неизвестная ошибка.")
    
    # обрабатываем всякие ошибочки
    except httpx.ConnectError as e:
        if "CERTIFICATE_VERIFY_FAILED" in str(e).upper():
            return SendScanRequest(is_ok=False, error_message=CommonKnownErrors.ssl_error)
        return SendScanRequest(is_ok=False, error_message=CommonKnownErrors.conn_error)
    
    except httpx.ConnectTimeout:
        return SendScanRequest(is_ok=False, error_message=CommonKnownErrors.timeout_error)
    
    except httpx.RequestError as e:
        return SendScanRequest(is_ok=False, error_message=f"Ошибка выполнения запроса: {e}")

    except Exception as e:
        return SendScanRequest(is_ok=False, error_message=f"Неизвестная ошибка: {e}") 

    
# проверка состояния API
async def make_api_healthcheck() -> ApiHeathCheck:
    """
    Функция для проверки состояния API PTSB.
    
    Возращает:
        - `ApiHeathCheck`(object of custom class): Объект класса `ApiHeathCheck` с информацией о состоянии API.
    """

    try:
        # заголовки запроса, только токен
        request_headers = {
            'X-API-Key': PTSB_TOKEN
        }
        # health_check_url
        heathcheck_url = f"https://{PTSB_ROOT_ADDR}/api/v1/maintenance/checkHealth"
        # открываем подключение, отправляем запрос
        async with httpx.AsyncClient(verify=VERIFY_SSL_CONNECTIONS, timeout=10) as async_health_client:
            response = await async_health_client.post(heathcheck_url, headers=request_headers)
        
        # проверка на 401ю
        if response.text == "Authorization required" and response.status_code == 401:
            return ApiHeathCheck(is_ok=False, error_message=CommonKnownErrors.error_401)
        
        # если пришла 200я, то дальнейшая обработка бессмысленна
        if response.status_code == 200:
            return ApiHeathCheck(is_ok=True)
        
        # пытаемся распарсить ответ, если не 401я и 200я
        try:
            response_data = response.json()
        except ValueError:
            return ApiHeathCheck(
                is_ok=False,
                error_message=f"Ошибка {response.status_code}. Не удалось распарсить в json текст ошибки: {response.text}"
            )
        
        # отправляем информацию с конкретикой по ошибке, что за ошибка вылезла
        if isinstance(response_data, dict) and response_data.get("errors"):
            error_message = response_data["errors"][0].get("message", "Нет подробностей по ошибке.")
            return ApiHeathCheck(is_ok=False, error_message=f"Ошибка {response.status_code}, {error_message}")
        else:
            return ApiHeathCheck(is_ok=False, error_message=f"Ошибка {response.status_code}. Подробностей по ошибке нет.")

    # обрабатываем ошибки, которые больше по сетевой части, нежели по состоянию АПИ песка
    except httpx.ConnectError as e:
        if "CERTIFICATE_VERIFY_FAILED" in str(e).upper():
            return ApiHeathCheck(
                is_ok=False,
                error_message=CommonKnownErrors.ssl_error
            )
        return ApiHeathCheck(is_ok=False, error_message=CommonKnownErrors.conn_error)
    
    except httpx.ConnectTimeout:
        return ApiHeathCheck(is_ok=False, error_message=CommonKnownErrors.timeout_error)
    
    except httpx.RequestError as e:
        return ApiHeathCheck(is_ok=False, error_message=f"Ошибка выполнения запроса: {e}")

    except Exception as e:
        return ApiHeathCheck(is_ok=False, error_message=f"Неизвестная ошибка: {e}")