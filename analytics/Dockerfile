# Dockerfile для сервиса аналитики
FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
	gcc \
	libpq-dev \
	&& rm -rf /var/lib/apt/lists/*

# Создание пользователя
RUN useradd -m -u 1000 appuser

# Установка рабочей директории
WORKDIR /app

# Копирование requirements
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY analytics_service.py .
COPY database_manager.py .

# Смена пользователя
USER appuser

# Экспорт порта
EXPOSE 8080

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
	CMD curl -f http://localhost:8080/health || exit 1

# Команда запуска
CMD ["python", "analytics_service.py"]
