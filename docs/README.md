# 📚 Документация системы виртуального контроллера

## Структура документации

### 📦 Контейнеры
Документация для каждого компонента системы:

- [**Analytics Service**](containers/analytics.md) - Сервис аналитики и метрик
- [**Controller**](containers/controller.md) - PID контроллеры (основной и резервный)
- [**Database**](containers/database.md) - База данных PostgreSQL
- [**Process Model**](containers/model.md) - Модель технологического процесса
- [**OPC UA Server**](containers/opcua-server.md) - OPC UA сервер
- [**Telegram Bot**](containers/telegram-bot.md) - Telegram бот для уведомлений
- [**Watchdog**](containers/watchdog.md) - Сервис мониторинга системы

### 🧪 Тестирование
- [**Тестовые команды**](tests/test-commands.md) - Команды для тестирования и диагностики

## Быстрый старт

### 1. Запуск системы
```bash
# Клонирование репозитория
git clone <repository-url>
cd virtual-controller-system

# Настройка переменных окружения
cp env.example .env
# Отредактируйте .env файл, установив TELEGRAM_BOT_TOKEN

# Запуск системы
./start_system.sh
```

### 2. Проверка состояния
```bash
# Статус всех контейнеров
docker-compose ps

# Логи системы
docker-compose logs
```

### 3. Тестирование
```bash
# Тест API уставок
./test_setpoint_api.sh

# Тест OPC UA подключения
python3 -c "
from opcua import Client
client = Client('opc.tcp://localhost:4840/freeopcua/server/')
client.connect()
print('✅ OPC UA подключение успешно')
client.disconnect()
"
```

## Архитектура системы

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Process Model │    │  OPC UA Server  │    │   Controllers   │
│                 │◄──►│                 │◄──►│  (Primary/Backup)│
│  - Tank         │    │  - Variables    │    │  - PID Control  │
│  - Valve        │    │  - Endpoints    │    │  - Failover     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Database      │    │  Telegram Bot   │    │   Analytics     │
│                 │    │                 │    │                 │
│  - Process Data │    │  - Notifications│    │  - Metrics      │
│  - Controller   │    │  - Commands     │    │  - Reports      │
│    Logs         │    │  - Monitoring   │    │  - Analysis     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │    Watchdog     │
                        │                 │
                        │  - Monitoring   │
                        │  - Health Check │
                        │  - Alerts       │
                        └─────────────────┘
```

## Основные компоненты

### 🏭 Process Model
Имитирует технологический процесс с резервуаром и клапаном управления.

### 🎛️ Controllers
PID регуляторы с автоматическим переключением при отказе.

### 🔌 OPC UA Server
Предоставляет данные через стандартный протокол OPC UA.

### 🗄️ Database
PostgreSQL для хранения данных процесса и логов.

### 🤖 Telegram Bot
Отправляет уведомления о критических ситуациях.

### 📊 Analytics
Собирает и анализирует метрики системы.

### 🐕 Watchdog
Мониторит состояние всех компонентов системы.

## Переменные окружения

Основные переменные в файле `.env`:

```bash
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token
ADMIN_CHAT_ID=your_chat_id

# Database
DB_HOST=database
DB_PORT=5432
DB_NAME=digital_twin_db
DB_USER=process_user
DB_PASSWORD=process_password

# OPC UA Server
OPCUA_SERVER_HOST=opcua-server
OPCUA_SERVER_PORT=4840
OPCUA_SERVER_ENDPOINT=opc.tcp://opcua-server:4840/freeopcua/server/

# Controllers
CONTROLLER_HEARTBEAT_TIMEOUT=5.0
CONTROLLER_FAILOVER_DELAY=2.0
CONTROLLER_UPDATE_INTERVAL=0.1
```

## Мониторинг и диагностика

### Логи системы
```bash
# Все логи
docker-compose logs

# Логи конкретного сервиса
docker-compose logs controller-primary

# Логи с фильтрацией
docker-compose logs | grep -E "(ERROR|WARNING|CRITICAL)"
```

### Статус системы
```bash
# Статус контейнеров
docker-compose ps

# Использование ресурсов
docker stats

# Проверка здоровья
docker-compose ps --format "table {{.Name}}\t{{.Status}}"
```

### Telegram команды
- `/start` - Начать работу с ботом
- `/subscribe` - Подписаться на уведомления
- `/status` - Статус системы
- `/params` - Параметры системы
- `/help` - Список команд

## Устранение неполадок

### Проблемы с запуском
1. Проверьте файл `.env`
2. Убедитесь, что порты свободны
3. Проверьте логи: `docker-compose logs`

### Проблемы с Telegram
1. Проверьте токен бота
2. Убедитесь, что подписались: `/subscribe`
3. Проверьте Chat ID

### Проблемы с контроллерами
1. Проверьте подключение к OPC UA
2. Убедитесь, что база данных доступна
3. Проверьте переменные окружения

## Поддержка

Для получения помощи:
1. Проверьте логи системы
2. Используйте команды диагностики
3. Обратитесь к документации компонентов
4. Проверьте Telegram бота для уведомлений

## Лицензия

Проект разработан для образовательных и исследовательских целей.
