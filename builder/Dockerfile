FROM python:3.13-slim

# Установка зависимостей системы
RUN apt-get update && apt-get install -y && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# устанавливаем рабочую директорию внутри контейнера
WORKDIR /opt/ptsb-checkbot

# копируем содержимое проекта в контейнер
COPY ptsb-checkbot/ .

# Установка зависимостей Python
RUN pip install --no-cache-dir -r requirements.txt

# стартуем сука!
CMD [ "python", "tg_bot_kernel.py"]