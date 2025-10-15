# Документация системы виртуального контроллера

## Обзор системы
- [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) - Общий обзор системы и архитектуры

## Конфигурация
- [CONFIGURATION_SYSTEM.md](CONFIGURATION_SYSTEM.md) - Система конфигурации (.env + config.json)

## Контейнеры

### Основные сервисы
- [DATABASE.md](CONTAINERS/DATABASE.md) - База данных PostgreSQL
- [OPCUA_SERVER.md](CONTAINERS/OPCUA_SERVER.md) - OPC UA сервер
- [PROCESS_MODEL.md](CONTAINERS/PROCESS_MODEL.md) - Модель процесса

### Контроллеры
- [CONTROLLERS.md](CONTAINERS/CONTROLLERS.md) - PID контроллеры (основной и резервный)

### Дополнительные сервисы
- [ANALYTICS.md](CONTAINERS/ANALYTICS.md) - Сервис аналитики
- [TELEGRAM_BOT.md](CONTAINERS/TELEGRAM_BOT.md) - Telegram бот
- [WATCHDOG.md](CONTAINERS/WATCHDOG.md) - Watchdog сервисы

## Быстрый старт

### 1. Настройка
```bash
# Скопировать пример конфигурации
cp env.example .env

# Отредактировать .env файл
nano .env
```

### 2. Запуск
```bash
# Запустить все сервисы
docker-compose up -d

# Проверить статус
docker-compose ps
```

### 3. Мониторинг
```bash
# Просмотр логов
docker-compose logs -f

# Просмотр логов конкретного сервиса
docker-compose logs -f telegram-bot
```

### 4. Telegram бот
1. Получите токен от @BotFather
2. Добавьте токен в `.env` файл
3. Найдите бота в Telegram
4. Отправьте `/start` для подписки на уведомления

## Порты
- **5432** - PostgreSQL
- **4840** - OPC UA Server
- **8080** - Analytics Service

## Переменные окружения
Все настройки в `.env` файле:
- `TELEGRAM_BOT_TOKEN` - токен Telegram бота
- `DB_PASSWORD` - пароль базы данных
- `OPCUA_SERVER_PORT` - порт OPC UA сервера
- `ANALYTICS_PORT` - порт сервиса аналитики

## Структура проекта
```
├── .env                    # Переменные окружения
├── config.json             # Параметры системы
├── docker-compose.yml      # Оркестрация контейнеров
├── docs/                   # Документация
│   ├── INDEX.md           # Этот файл
│   ├── SYSTEM_OVERVIEW.md # Обзор системы
│   ├── CONFIGURATION_SYSTEM.md # Конфигурация
│   └── CONTAINERS/        # Документация контейнеров
│       ├── DATABASE.md     # База данных
│       ├── OPCUA_SERVER.md # OPC UA сервер
│       ├── PROCESS_MODEL.md # Модель процесса
│       ├── CONTROLLERS.md  # PID контроллеры
│       ├── ANALYTICS.md    # Сервис аналитики
│       ├── TELEGRAM_BOT.md # Telegram бот
│       └── WATCHDOG.md     # Watchdog сервисы
├── database/              # Скрипты БД
├── controller/            # PID контроллеры
├── opcua-server/         # OPC UA сервер
├── model/                # Модель процесса
├── analytics/            # Сервис аналитики
├── telegram/             # Telegram бот
└── utils/                # Утилиты
```

## Поддержка
При возникновении проблем:
1. Проверьте логи: `docker-compose logs`
2. Проверьте статус: `docker-compose ps`
3. Проверьте конфигурацию: `python3 utils/config_loader.py`
4. Обратитесь к документации конкретного контейнера
