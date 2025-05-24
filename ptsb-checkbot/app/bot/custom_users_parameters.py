# вводимые админом параметры при создании нового пользователя для пользования ботом
class InputUserParameters:
    """
    Параметры вводимые админом при создании базового профиля пользователя
    """
    tg_user_id = "tg_user_id"
    user_role = "user_role"
    comment = "comment"

# вводимые админом параметры при создании нового пользователя для взаимодействия с песочницей
class InputSandboxProfileParameters:
    """
    Параметры вводимые админом при создании профиля взаимодействия с песком
    """
    max_available_checks = "max_available_checks"
    check_priority = "check_priority"
    can_get_links = "can_get_links"

# параметры пользователей при взаимодействии с функционалом песочницы
class SandboxInteractionsParameters:
    """
    Параметры, которые задаются для пользователя при взаимодействии с песочницей
    """
    user_role = "user_role"
    scan_priority = "scan_priority"
    url_to_scan = "url_to_scan"
    file_to_scan = "file_to_scan"
    scan_type = "scan_type"
    list_of_pwds = "list_of_pwds"
    scan_id = "scan_id"
    can_get_links = "can_get_links"
    file_uploaded = "file_uploaded"