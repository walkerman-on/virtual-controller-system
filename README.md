# 🎛️ Система виртуального контроллера

> Современная система управления технологическим процессом с PID-регулятором, OPC UA сервером и Telegram уведомлениями

## 🚀 Быстрый старт

```bash
# Клонирование и запуск
git clone <repository-url>
cd virtual-controller-system
cp env.example .env
# Отредактируйте .env файл, установив TELEGRAM_BOT_TOKEN
./start_system.sh
```

## 📚 Документация

**📖 [Полная документация](docs/INDEX.md)**

### Основные разделы:
- [🚀 Быстрый старт](docs/QUICK_START.md)
- [🏗️ Архитектура](docs/ARCHITECTURE.md)
- [📦 Контейнеры](docs/containers/)
- [🧪 Тестирование](docs/tests/test-commands.md)

## 🏗️ Компоненты системы

| Компонент | Описание | Статус |
|-----------|----------|--------|
| 🏭 **Process Model** | Модель резервуара с жидкостью | ✅ |
| 🎛️ **Controllers** | PID регуляторы (primary/backup) | ✅ |
| 🔌 **OPC UA Server** | Сервер данных через OPC UA | ✅ |
| 🗄️ **Database** | PostgreSQL для данных и логов | ✅ |
| 🤖 **Telegram Bot** | Уведомления и мониторинг | ✅ |
| 📊 **Analytics** | Сбор метрик и аналитика | ✅ |
| 🐕 **Watchdog** | Мониторинг системы | ✅ |

## 🔧 Основные команды

```bash
# Запуск системы
./start_system.sh

# Проверка состояния
docker-compose ps

# Логи системы
docker-compose logs

# Тест API
./test_setpoint_api.sh
```

## 📱 Telegram Bot

**Команды:**
- `/start` - Начать работу
- `/subscribe` - Подписаться на уведомления
- `/status` - Статус системы
- `/params` - Параметры системы
- `/help` - Список команд

## 🔌 OPC UA

**Endpoint:** `opc.tcp://localhost:4840/freeopcua/server/`

**Основные переменные:**
- `liquid_level` - Уровень жидкости
- `setpoint` - Уставка контроллера
- `control_output` - Выход управления

## 📊 API

**Analytics API:** `http://localhost:8080`
- `GET /health` - Проверка состояния
- `GET /metrics` - Получение метрик
- `GET /api/setpoint` - Получение уставки
- `POST /api/setpoint` - Установка уставки

## 🧪 Тестирование

```bash
# Тест failover
docker-compose stop controller-primary
docker-compose logs controller-backup | grep "ПЕРЕКЛЮЧЕНИЕ"

# Тест OPC UA
python3 -c "
from opcua import Client
client = Client('opc.tcp://localhost:4840/freeopcua/server/')
client.connect()
print('✅ OPC UA подключение успешно')
client.disconnect()
"
```

## 📋 Требования

- **Docker** и **Docker Compose**
- **Python 3.8+** (для тестирования)
- **Telegram Bot Token** (от @BotFather)

## 🆘 Поддержка

1. **Начните с** [QUICK_START.md](docs/QUICK_START.md)
2. **Для тестирования** используйте [Тестовые команды](docs/tests/test-commands.md)
3. **Для конкретного компонента** смотрите [Документацию контейнеров](docs/containers/)
4. **Для API** смотрите [SETPOINT_API.md](docs/SETPOINT_API.md)

## 📄 Лицензия

Проект разработан для образовательных и исследовательских целей.

---

**📚 [Полная документация](docs/INDEX.md) | 🚀 [Быстрый старт](docs/QUICK_START.md) | 🧪 [Тестирование](docs/tests/test-commands.md)**
