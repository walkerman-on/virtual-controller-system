# Система виртуального контроллера

Комплексная система управления промышленным процессом с использованием PID-регуляторов, OPC UA сервера, базы данных PostgreSQL и Telegram бота для мониторинга.

## 🚀 Быстрый старт

### 1. Настройка
```bash
# Скопировать пример конфигурации
cp env.example .env

# Отредактировать .env файл с вашими настройками
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

## 📋 Компоненты системы

- **PostgreSQL** (5432) - База данных
- **OPC UA Server** (4840) - Сервер данных процесса
- **Process Model** - Симуляция промышленного процесса
- **PID Controllers** - Основной и резервный контроллеры
- **Analytics Service** (8080) - Сервис аналитики
- **Telegram Bot** - Мониторинг и уведомления
- **Watchdog Services** - Мониторинг и перезапуск

## 🔧 Конфигурация

### .env файл
Содержит все переменные окружения:
- `TELEGRAM_BOT_TOKEN` - токен Telegram бота
- `DB_PASSWORD` - пароль базы данных
- `OPCUA_SERVER_PORT` - порт OPC UA сервера
- `ANALYTICS_PORT` - порт сервиса аналитики

### config.json файл
Содержит параметры системы:
- Параметры модели процесса
- PID коэффициенты
- OPC UA переменные

## 📱 Telegram бот

1. Получите токен от @BotFather
2. Добавьте токен в `.env` файл
3. Найдите бота в Telegram
4. Отправьте `/start` для подписки на уведомления

### Команды бота
- `/start` - подписка на уведомления
- `/status` - статус системы
- `/valve` - данные клапана
- `/tank` - данные бака
- `/pid` - параметры PID
- `/controllers` - статус контроллеров

## 📚 Документация

Полная документация находится в папке `docs/`:

- [docs/INDEX.md](docs/INDEX.md) - Главный индекс документации
- [docs/SYSTEM_OVERVIEW.md](docs/SYSTEM_OVERVIEW.md) - Обзор системы
- [docs/CONFIGURATION_SYSTEM.md](docs/CONFIGURATION_SYSTEM.md) - Система конфигурации
- [docs/CONTAINERS/](docs/CONTAINERS/) - Документация по контейнерам
- [docs/LOAD_TEST_GUIDE.md](docs/LOAD_TEST_GUIDE.md) - Экспресс нагрузочное тестирование (10-15 минут)

## 🏗️ Архитектура

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │   OPC UA Server │    │  Process Model  │
│   Database      │◄──►│   (4840)        │◄──►│   Simulation    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         ▲                       ▲                       ▲
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Primary        │    │  Backup         │    │  Analytics      │
│  Controller     │◄──►│  Controller     │    │  Service (8080) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         ▲                       ▲                       ▲
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Controller      │    │ System          │    │ Telegram        │
│ Watchdog        │    │ Watchdog        │    │ Bot             │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔍 Мониторинг

- **Логи**: `docker-compose logs [service_name]`
- **Статус**: `docker-compose ps`
- **Telegram**: Отправьте `/start` боту для подписки на уведомления
- **Нагрузочное тестирование**: `./load-test/run_profiles.sh` (генерирует `load-test/results/LOAD_TEST_REPORT.md`)

## 🛠️ Разработка

### Структура проекта
```
├── .env                    # Переменные окружения
├── config.json             # Параметры системы
├── docker-compose.yml      # Оркестрация контейнеров
├── docs/                   # Документация
├── database/              # Скрипты БД
├── controller/            # PID контроллеры
├── opcua-server/         # OPC UA сервер
├── model/                # Модель процесса
├── analytics/            # Сервис аналитики
├── telegram/             # Telegram бот
└── utils/                # Утилиты
```

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи: `docker-compose logs`
2. Проверьте статус: `docker-compose ps`
3. Обратитесь к документации в папке `docs/`

## 📄 Лицензия

MIT License
