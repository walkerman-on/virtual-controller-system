FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY telegram_bot.py .

# Создание директории для данных
RUN mkdir -p /app/data

# Переменные окружения
ENV TELEGRAM_BOT_TOKEN="8499179904:AAGfcyftDeJlFjw5VVom5UvljFHDhYidCEw"
ENV ADMIN_CHAT_ID=""

# Команда запуска
CMD ["python", "telegram_bot.py"]
