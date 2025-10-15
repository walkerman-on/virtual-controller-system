# 📊 Analytics Service

## Описание
Сервис аналитики для сбора и обработки данных системы виртуального контроллера.

## Функции
- Сбор метрик производительности
- Анализ данных процесса
- Генерация отчетов
- Мониторинг состояния системы

## Конфигурация
- **Порт**: 8080
- **Хост**: 0.0.0.0
- **База данных**: PostgreSQL
- **Логирование**: INFO уровень

## Переменные окружения
```bash
ANALYTICS_PORT=8080
ANALYTICS_HOST=0.0.0.0
ANALYTICS_BASE_URL=http://analytics:8080
ANALYTICS_EXTERNAL_URL=http://localhost:8080
ANALYTICS_TIMEOUT=30.0
ANALYTICS_RETRY_ATTEMPTS=3
```

## Запуск
```bash
docker-compose up -d analytics
```

## Проверка состояния
```bash
docker-compose logs analytics
curl http://localhost:8080/health
```

## API Endpoints
- `GET /health` - Проверка состояния
- `GET /metrics` - Получение метрик
- `GET /reports` - Генерация отчетов

## Логи
```bash
docker-compose logs -f analytics
```

## Мониторинг
- Health check каждые 30 секунд
- Автоматический перезапуск при сбоях
- Интеграция с Telegram ботом для уведомлений
