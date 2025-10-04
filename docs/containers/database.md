# 🗄️ Database (PostgreSQL)

## Описание
База данных PostgreSQL для хранения данных системы виртуального контроллера.

## Функции
- Хранение данных процесса
- Логирование событий
- Сохранение состояния PID регулятора
- История failover событий
- Метрики производительности

## Конфигурация
- **Порт**: 5432
- **База данных**: digital_twin_db
- **Пользователь**: process_user
- **Пароль**: process_password
- **Админ**: postgres

## Переменные окружения
```bash
DB_HOST=database
DB_PORT=5432
DB_NAME=digital_twin_db
DB_USER=process_user
DB_PASSWORD=process_password
DB_ADMIN_USER=postgres
DB_ADMIN_PASSWORD=postgres_password
DB_CONNECTION_TIMEOUT=30.0
DB_POOL_MIN_SIZE=2
DB_POOL_MAX_SIZE=10
```

## Схема базы данных
- **process_data** - Данные процесса
- **controller_logs** - Логи контроллеров
- **failover_events** - События переключения
- **system_metrics** - Метрики системы

## Запуск
```bash
docker-compose up -d database
```

## Проверка состояния
```bash
# Статус контейнера
docker-compose ps database

# Подключение к базе
docker-compose exec database psql -U process_user -d digital_twin_db

# Проверка подключения
docker-compose exec database pg_isready -U process_user
```

## Резервное копирование
```bash
# Создание бэкапа
docker-compose exec database pg_dump -U process_user digital_twin_db > backup.sql

# Восстановление
docker-compose exec -T database psql -U process_user digital_twin_db < backup.sql
```

## Мониторинг
- Health check каждые 30 секунд
- Автоматический перезапуск при сбоях
- Логирование подключений

## Подключение извне
```bash
# Из хоста
psql -h localhost -p 5432 -U process_user -d digital_twin_db

# Из другого контейнера
psql -h database -p 5432 -U process_user -d digital_twin_db
```

## Логи
```bash
docker-compose logs -f database
```
