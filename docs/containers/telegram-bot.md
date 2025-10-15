# 🤖 Telegram Bot

## Описание
Telegram бот для мониторинга системы виртуального контроллера и отправки уведомлений о критических ситуациях.

## Функции
- Отправка уведомлений о критических событиях
- Мониторинг состояния системы
- Интерактивные команды для управления
- Система подписки на уведомления
- Фильтрация уведомлений по уровню важности

## Конфигурация
- **Токен**: Получается от @BotFather
- **Admin Chat ID**: ID чата администратора
- **База данных**: PostgreSQL для хранения подписчиков
- **Логирование**: INFO уровень

## Переменные окружения
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
ADMIN_CHAT_ID=your_chat_id
DB_HOST=database
DB_PORT=5432
DB_NAME=digital_twin_db
DB_USER=process_user
DB_PASSWORD=process_password
LOGGING_LEVEL=INFO
DEBUG_MODE=false
HEALTH_CHECK_INTERVAL=30.0
```

## Команды бота

### Основные команды
- `/start` - Начать работу с ботом
- `/help` - Список всех команд
- `/subscribe` - Подписаться на уведомления
- `/unsubscribe` - Отписаться от уведомлений
- `/status` - Получить отчет о состоянии системы

### Команды мониторинга
- `/params` - Все параметры системы
- `/tank` - Состояние резервуара
- `/valve` - Состояние клапана
- `/pid` - Параметры PID контроллера
- `/opcua` - Статус OPC UA сервера
- `/database` - Статус базы данных
- `/analytics` - Статус аналитики
- `/controllers` - Статус контроллеров
- `/system` - Общее состояние системы
- `/alerts` - Активные предупреждения
- `/history` - История событий
- `/logs` - Последние логи

### Команды фильтров
- `/filters` - Информация о фильтрах
- `/filter_level LEVEL` - Установить минимальный уровень уведомлений
- `/filter_components COMPONENTS` - Установить отслеживаемые компоненты

## Уровни важности
- **DEBUG** - Отладочная информация
- **INFO** - Информационные сообщения
- **WARNING** - Предупреждения
- **ERROR** - Ошибки
- **CRITICAL** - Критические ошибки

## Запуск
```bash
docker-compose up -d telegram-bot
```

## Проверка состояния
```bash
# Статус контейнера
docker-compose ps telegram-bot

# Логи бота
docker-compose logs telegram-bot

# Проверка подписчиков
docker-compose exec telegram-bot cat /app/telegram_subscribers.json
```

## Настройка бота

### 1. Создание бота
1. Напишите @BotFather в Telegram
2. Отправьте команду `/newbot`
3. Следуйте инструкциям для создания бота
4. Сохраните полученный токен

### 2. Получение Chat ID
1. Напишите боту команду `/start`
2. Отправьте любое сообщение боту
3. Используйте API для получения Chat ID:
```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates"
```

### 3. Настройка переменных
```bash
# В файле .env
TELEGRAM_BOT_TOKEN=your_bot_token_here
ADMIN_CHAT_ID=your_chat_id_here
```

## Тестирование уведомлений
```bash
# Отправка тестового уведомления
docker-compose exec telegram-bot python3 -c "
import asyncio
import os
from telegram_bot import TelegramNotifier

async def test():
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    notifier = TelegramNotifier(bot_token)
    await notifier.send_notification(
        'CRITICAL', 
        'test', 
        '🧪 Тестовое уведомление!'
    )
    print('✅ Тестовое уведомление отправлено')

asyncio.run(test())
"
```

## Мониторинг
- Health check каждые 30 секунд
- Автоматический перезапуск при сбоях
- Логирование всех операций

## Логи
```bash
docker-compose logs -f telegram-bot
```

## Интеграция
- Получает уведомления от контроллеров
- Получает уведомления от модели процесса
- Сохраняет подписчиков в файл
- Интегрирован со всеми компонентами системы
