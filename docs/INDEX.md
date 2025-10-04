# 📚 Полная документация системы виртуального контроллера

## 🚀 Быстрый старт
- [**QUICK_START.md**](QUICK_START.md) - Быстрый старт системы

## 🏗️ Архитектура и проектирование
- [**ARCHITECTURE.md**](ARCHITECTURE.md) - Архитектура системы
- [**PROJECT_SUMMARY.md**](PROJECT_SUMMARY.md) - Описание проекта
- [**CONNECTION_SETTINGS.md**](CONNECTION_SETTINGS.md) - Настройки подключений

## 📦 Документация контейнеров
- [**Analytics Service**](containers/analytics.md) - Сервис аналитики
- [**Controller**](containers/controller.md) - PID контроллеры
- [**Database**](containers/database.md) - База данных PostgreSQL
- [**Process Model**](containers/model.md) - Модель процесса
- [**OPC UA Server**](containers/opcua-server.md) - OPC UA сервер
- [**Telegram Bot**](containers/telegram-bot.md) - Telegram бот
- [**Watchdog**](containers/watchdog.md) - Сервис мониторинга

## 🧪 Тестирование и диагностика
- [**Тестовые команды**](tests/test-commands.md) - Команды для тестирования

## 📋 API и интерфейсы
- [**SETPOINT_API.md**](SETPOINT_API.md) - API уставок
- [**LOGGING_DOCUMENTATION.md**](LOGGING_DOCUMENTATION.md) - Документация по логированию

## 📖 Общая информация
- [**README.md**](README.md) - Основная документация

---

## 🔍 Поиск по документации

### По компонентам:
- **Analytics** → [Analytics Service](containers/analytics.md)
- **Controller** → [Controller](containers/controller.md)
- **Database** → [Database](containers/database.md)
- **Model** → [Process Model](containers/model.md)
- **OPC UA** → [OPC UA Server](containers/opcua-server.md)
- **Telegram** → [Telegram Bot](containers/telegram-bot.md)
- **Watchdog** → [Watchdog](containers/watchdog.md)

### По задачам:
- **Запуск системы** → [QUICK_START.md](QUICK_START.md)
- **Тестирование** → [Тестовые команды](tests/test-commands.md)
- **API** → [SETPOINT_API.md](SETPOINT_API.md)
- **Логирование** → [LOGGING_DOCUMENTATION.md](LOGGING_DOCUMENTATION.md)
- **Подключения** → [CONNECTION_SETTINGS.md](CONNECTION_SETTINGS.md)

### По проблемам:
- **Не запускается** → [QUICK_START.md](QUICK_START.md) + [Тестовые команды](tests/test-commands.md)
- **Нет уведомлений** → [Telegram Bot](containers/telegram-bot.md)
- **Ошибки контроллера** → [Controller](containers/controller.md)
- **Проблемы с БД** → [Database](containers/database.md)
- **OPC UA не работает** → [OPC UA Server](containers/opcua-server.md)

---

## 📝 Структура документации

```
docs/
├── README.md                    # Основная документация
├── QUICK_START.md              # Быстрый старт
├── ARCHITECTURE.md             # Архитектура
├── PROJECT_SUMMARY.md          # Описание проекта
├── CONNECTION_SETTINGS.md      # Настройки подключений
├── SETPOINT_API.md             # API уставок
├── LOGGING_DOCUMENTATION.md    # Документация по логированию
├── containers/                 # Документация контейнеров
│   ├── analytics.md
│   ├── controller.md
│   ├── database.md
│   ├── model.md
│   ├── opcua-server.md
│   ├── telegram-bot.md
│   └── watchdog.md
└── tests/                      # Тестирование
    └── test-commands.md
```

---

## 🆘 Получение помощи

1. **Начните с** [QUICK_START.md](QUICK_START.md)
2. **Для тестирования** используйте [Тестовые команды](tests/test-commands.md)
3. **Для конкретного компонента** смотрите документацию в папке `containers/`
4. **Для API** смотрите [SETPOINT_API.md](SETPOINT_API.md)
5. **Для архитектуры** смотрите [ARCHITECTURE.md](ARCHITECTURE.md)

---

*Последнее обновление: $(date)*
