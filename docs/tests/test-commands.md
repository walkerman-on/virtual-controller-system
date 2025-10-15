# 🧪 Тестовые команды для системы виртуального контроллера

## Общие команды

### Проверка состояния системы
```bash
# Статус всех контейнеров
docker-compose ps

# Логи всех сервисов
docker-compose logs

# Проверка здоровья системы
docker-compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
```

### Управление системой
```bash
# Запуск всей системы
docker-compose up -d

# Остановка всей системы
docker-compose down

# Перезапуск системы
docker-compose restart

# Пересборка и запуск
docker-compose up --build -d
```

## Тестирование контроллеров

### Проверка failover
```bash
# Запуск контроллеров
docker-compose up -d controller-primary controller-backup

# Остановка основного контроллера
docker-compose stop controller-primary

# Проверка переключения на резервный
docker-compose logs controller-backup | grep "ПЕРЕКЛЮЧЕНИЕ"

# Восстановление основного контроллера
docker-compose up -d controller-primary
```

### Проверка PID регулятора
```bash
# Логи основного контроллера
docker-compose logs controller-primary | grep "PID"

# Логи резервного контроллера
docker-compose logs controller-backup | grep "PID"

# Проверка ошибок PID
docker-compose logs controller-primary | grep -E "(ERROR|WARNING)"
```

## Тестирование OPC UA

### Подключение к серверу
```bash
# Проверка подключения
python3 -c "
from opcua import Client
client = Client('opc.tcp://localhost:4840/freeopcua/server/')
client.connect()
print('✅ Подключение к OPC UA серверу успешно')
client.disconnect()
"
```

### Чтение переменных
```bash
# Чтение всех переменных процесса
python3 -c "
from opcua import Client
client = Client('opc.tcp://localhost:4840/freeopcua/server/')
client.connect()

variables = {
    'liquid_level': 'ns=2;i=1',
    'setpoint': 'ns=2;i=2', 
    'control_output': 'ns=2;i=3',
    'tank_volume': 'ns=2;i=4',
    'valve_opening': 'ns=2;i=7'
}

for name, node_id in variables.items():
    value = client.get_node(node_id).get_value()
    print(f'{name}: {value}')

client.disconnect()
"
```

### Запись переменных
```bash
# Изменение уставки
python3 -c "
from opcua import Client
client = Client('opc.tcp://localhost:4840/freeopcua/server/')
client.connect()
client.get_node('ns=2;i=2').set_value(1.5)  # Установка уставки 1.5м
print('✅ Уставка установлена на 1.5м')
client.disconnect()
"
```

## Тестирование Telegram бота

### Проверка работы бота
```bash
# Логи Telegram бота
docker-compose logs telegram-bot

# Проверка подписчиков
docker-compose exec telegram-bot cat /app/telegram_subscribers.json

# Проверка переменных окружения
docker-compose exec telegram-bot env | grep TELEGRAM
```

### Отправка тестового уведомления
```bash
# Тестовое уведомление
docker-compose exec telegram-bot python3 -c "
import asyncio
import os
from telegram_bot import TelegramNotifier

async def test():
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    notifier = TelegramNotifier(bot_token)
    await notifier.send_notification(
        'CRITICAL', 
        'test_system', 
        '🧪 Тестовое уведомление от системы!'
    )
    print('✅ Тестовое уведомление отправлено')

asyncio.run(test())
"
```

## Тестирование базы данных

### Подключение к базе
```bash
# Подключение к PostgreSQL
docker-compose exec database psql -U process_user -d digital_twin_db

# Проверка подключения
docker-compose exec database pg_isready -U process_user

# Список таблиц
docker-compose exec database psql -U process_user -d digital_twin_db -c "\dt"
```

### Проверка данных
```bash
# Проверка таблицы process_data
docker-compose exec database psql -U process_user -d digital_twin_db -c "SELECT * FROM process_data LIMIT 5;"

# Проверка таблицы controller_logs
docker-compose exec database psql -U process_user -d digital_twin_db -c "SELECT * FROM controller_logs LIMIT 5;"

# Проверка таблицы failover_events
docker-compose exec database psql -U process_user -d digital_twin_db -c "SELECT * FROM failover_events LIMIT 5;"
```

## Тестирование модели процесса

### Проверка работы модели
```bash
# Логи модели
docker-compose logs model

# Проверка критических ситуаций
docker-compose logs model | grep -E "(CRITICAL|WARNING)"

# Проверка расчетов
docker-compose logs model | grep -E "(уровень|объем|давление)"
```

### Тестирование критических ситуаций
```bash
# Установка критически высокой уставки
python3 -c "
from opcua import Client
client = Client('opc.tcp://localhost:4840/freeopcua/server/')
client.connect()
client.get_node('ns=2;i=2').set_value(2.9)  # Критически высокая уставка
print('✅ Установлена критически высокая уставка')
client.disconnect()
"

# Проверка уведомлений в Telegram
docker-compose logs telegram-bot | grep "CRITICAL"
```

## Тестирование аналитики

### Проверка сервиса аналитики
```bash
# Логи аналитики
docker-compose logs analytics

# Проверка HTTP endpoints
curl http://localhost:8080/health

# Проверка метрик
curl http://localhost:8080/metrics
```

## Тестирование watchdog

### Проверка мониторинга
```bash
# Логи watchdog
docker-compose logs watchdog

# Проверка мониторинга компонентов
docker-compose logs watchdog | grep -E "(ERROR|WARNING|CRITICAL)"

# Проверка интервала мониторинга
docker-compose logs watchdog | grep "мониторинг"
```

## Команды диагностики

### Проверка ресурсов
```bash
# Использование ресурсов контейнерами
docker stats

# Проверка дискового пространства
docker system df

# Очистка неиспользуемых ресурсов
docker system prune -f
```

### Проверка сети
```bash
# Проверка сетей Docker
docker network ls

# Проверка подключения между контейнерами
docker-compose exec controller-primary ping opcua-server
docker-compose exec controller-primary ping database
```

### Проверка логов
```bash
# Логи с фильтрацией по уровню
docker-compose logs | grep -E "(ERROR|WARNING|CRITICAL)"

# Логи конкретного сервиса
docker-compose logs -f controller-primary

# Логи за последние 10 минут
docker-compose logs --since 10m
```

## Команды восстановления

### Перезапуск проблемного сервиса
```bash
# Перезапуск конкретного сервиса
docker-compose restart controller-primary

# Пересоздание контейнера
docker-compose up -d --force-recreate controller-primary

# Полная пересборка сервиса
docker-compose build controller-primary
docker-compose up -d controller-primary
```

### Восстановление после сбоя
```bash
# Остановка всех сервисов
docker-compose down

# Очистка volumes (ОСТОРОЖНО!)
docker-compose down -v

# Запуск с нуля
docker-compose up --build -d
```
