FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
	gcc \
	g++ \
	&& rm -rf /var/lib/apt/lists/*

# Установка рабочей директории
WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=120
# Копирование requirements.txt и установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir --retries 10 --timeout 120 -r requirements.txt

# Копирование исходного кода
COPY . .

# Создание пользователя
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Переключение на пользователя
USER appuser

# Команда запуска
CMD ["python", "controller_watchdog.py"]
