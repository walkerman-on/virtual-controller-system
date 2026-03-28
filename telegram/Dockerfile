FROM python:3.11-slim

WORKDIR /app

# Медленный/нестабильный PyPI: увеличить таймаут и число повторов
ENV PIP_DEFAULT_TIMEOUT=120
# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir --retries 10 --timeout 120 -r requirements.txt

# Копирование кода
COPY telegram_bot.py .

# Создание директории для данных
RUN mkdir -p /app/data

# Подключение к Telegram — только по токену (переменная окружения, не файл в образе):
#   TELEGRAM_BOT_TOKEN — обязательна (см. env.example, в compose: telegram-bot.environment)
#   ADMIN_CHAT_ID — опционально (тот же блок environment)
# Локально без Docker: python telegram_bot.py <токен> или export TELEGRAM_BOT_TOKEN=...

# Команда запуска
CMD ["python", "telegram_bot.py"]
