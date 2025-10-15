# Сервис аналитики

## Описание
Сервис для анализа данных процесса и предоставления метрик.

## Контейнер
- **Имя**: analytics-service
- **Порт**: 8080

## Переменные окружения
- `DB_HOST` - хост базы данных
- `DB_PORT` - порт базы данных
- `DB_NAME` - имя базы данных
- `DB_USER` - пользователь БД
- `DB_PASSWORD` - пароль БД
- `ANALYTICS_PORT` - порт сервиса
- `ANALYTICS_HOST` - хост сервиса

## Volumes
- `./database/database_manager.py` - менеджер БД

## API Endpoints
- `GET /health` - проверка здоровья
- `GET /metrics` - метрики процесса
- `GET /analytics` - аналитические данные

## Health Check
```bash
curl -f http://localhost:8080/health
```

## Логи
```bash
docker-compose logs analytics
```
