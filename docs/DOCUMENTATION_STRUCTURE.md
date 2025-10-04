# 📁 Структура документации

## Корневая директория
- `README.md` - Основной README с быстрым стартом
- `CLEANUP_SUMMARY.md` - Отчет об очистке проекта

## 📚 Папка docs/
Содержит всю документацию системы:

### Основные файлы
- `INDEX.md` - Индекс всей документации
- `README.md` - Основная документация
- `QUICK_START.md` - Быстрый старт
- `ARCHITECTURE.md` - Архитектура системы
- `PROJECT_SUMMARY.md` - Описание проекта
- `CONNECTION_SETTINGS.md` - Настройки подключений
- `SETPOINT_API.md` - API уставок
- `LOGGING_DOCUMENTATION.md` - Документация по логированию

### 📦 docs/containers/
Документация для каждого контейнера:
- `analytics.md` - Сервис аналитики
- `controller.md` - PID контроллеры
- `database.md` - База данных PostgreSQL
- `model.md` - Модель процесса
- `opcua-server.md` - OPC UA сервер
- `telegram-bot.md` - Telegram бот
- `watchdog.md` - Сервис мониторинга

### 🧪 docs/tests/
Тестирование и диагностика:
- `test-commands.md` - Команды для тестирования

## 🎯 Навигация по документации

### Для новых пользователей:
1. `README.md` (корень) - Быстрый обзор
2. `docs/QUICK_START.md` - Пошаговый запуск
3. `docs/containers/` - Документация компонентов

### Для разработчиков:
1. `docs/ARCHITECTURE.md` - Архитектура системы
2. `docs/containers/` - Детальная документация компонентов
3. `docs/tests/test-commands.md` - Команды тестирования

### Для администраторов:
1. `docs/CONNECTION_SETTINGS.md` - Настройки подключений
2. `docs/LOGGING_DOCUMENTATION.md` - Логирование
3. `docs/SETPOINT_API.md` - API интерфейсы

## 📋 Быстрый доступ

| Задача | Файл |
|--------|------|
| Запуск системы | `docs/QUICK_START.md` |
| Тестирование | `docs/tests/test-commands.md` |
| API документация | `docs/SETPOINT_API.md` |
| Архитектура | `docs/ARCHITECTURE.md` |
| Telegram бот | `docs/containers/telegram-bot.md` |
| Контроллеры | `docs/containers/controller.md` |
| База данных | `docs/containers/database.md` |
| OPC UA | `docs/containers/opcua-server.md` |

## 🔍 Поиск информации

### По компонентам:
- **Analytics** → `docs/containers/analytics.md`
- **Controller** → `docs/containers/controller.md`
- **Database** → `docs/containers/database.md`
- **Model** → `docs/containers/model.md`
- **OPC UA** → `docs/containers/opcua-server.md`
- **Telegram** → `docs/containers/telegram-bot.md`
- **Watchdog** → `docs/containers/watchdog.md`

### По задачам:
- **Запуск** → `docs/QUICK_START.md`
- **Тестирование** → `docs/tests/test-commands.md`
- **API** → `docs/SETPOINT_API.md`
- **Логирование** → `docs/LOGGING_DOCUMENTATION.md`
- **Подключения** → `docs/CONNECTION_SETTINGS.md`

---

*Структура создана для удобной навигации и быстрого поиска информации*
