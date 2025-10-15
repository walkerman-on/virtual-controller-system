# База данных PostgreSQL

## Описание
PostgreSQL база данных для хранения данных процесса, PID параметров и логов.

## Контейнер
- **Имя**: digital-twin-db
- **Образ**: postgres:15-alpine
- **Порт**: 5432

## Переменные окружения
- `POSTGRES_DB` - имя базы данных (из DB_NAME)
- `POSTGRES_USER` - пользователь (из DB_USER)
- `POSTGRES_PASSWORD` - пароль (из DB_PASSWORD)

## Volumes
- `postgres_data` - данные PostgreSQL
- `./database/init` - скрипты инициализации

## Health Check
```bash
pg_isready -U ${DB_USER} -d ${DB_NAME}
```

## Подключение
```bash
# Из контейнера
psql -h digital-twin-db -U postgres -d digital_twin_db

# С хоста
psql -h localhost -p 5432 -U postgres -d digital_twin_db
```

## Логи
```bash
docker-compose logs database
```
