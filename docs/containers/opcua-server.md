# 🔌 OPC UA Server

## Описание
OPC UA сервер для предоставления данных модели процесса и контроллеров через стандартный протокол OPC UA.

## Функции
- Предоставление данных процесса через OPC UA
- Управление переменными контроллера
- Синхронизация данных между компонентами
- Поддержка чтения и записи переменных

## Конфигурация
- **Порт**: 4840
- **Endpoint**: opc.tcp://opcua-server:4840/freeopcua/server/
- **Namespace**: 2
- **Таймаут**: 10.0 секунд

## Переменные окружения
```bash
OPCUA_SERVER_HOST=opcua-server
OPCUA_SERVER_PORT=4840
OPCUA_SERVER_ENDPOINT=opc.tcp://opcua-server:4840/freeopcua/server/
OPCUA_SERVER_TIMEOUT=10.0
OPCUA_SERVER_RETRY_ATTEMPTS=3
OPCUA_SERVER_RETRY_DELAY=1.0
```

## OPC UA Переменные

### Переменные процесса (ns=2)
- `i=1` - `liquid_level` (Float) - Уровень жидкости
- `i=2` - `setpoint` (Float) - Уставка контроллера
- `i=3` - `control_output` (Float) - Выход управления
- `i=4` - `tank_volume` (Float) - Объем жидкости
- `i=5` - `tank_mass` (Float) - Масса жидкости
- `i=6` - `tank_pressure` (Float) - Давление
- `i=7` - `valve_opening` (Float) - Открытие клапана
- `i=8` - `flow_rate` (Float) - Расход жидкости

### Переменные контроллера (ns=2)
- `i=10` - `primary_controller_status` (Boolean) - Статус основного контроллера
- `i=11` - `backup_controller_status` (Boolean) - Статус резервного контроллера
- `i=12` - `primary_controller_heartbeat` (Float) - Heartbeat основного контроллера
- `i=13` - `backup_controller_heartbeat` (Float) - Heartbeat резервного контроллера

## Запуск
```bash
docker-compose up -d opcua-server
```

## Проверка состояния
```bash
# Статус контейнера
docker-compose ps opcua-server

# Логи сервера
docker-compose logs opcua-server

# Проверка подключения
python3 -c "
from opcua import Client
client = Client('opc.tcp://localhost:4840/freeopcua/server/')
client.connect()
print('✅ Подключение к OPC UA серверу успешно')
client.disconnect()
"
```

## Подключение клиентов
```python
from opcua import Client

# Подключение
client = Client('opc.tcp://localhost:4840/freeopcua/server/')
client.connect()

# Чтение переменной
level = client.get_node('ns=2;i=1').get_value()
print(f'Уровень жидкости: {level:.3f}м')

# Запись переменной
client.get_node('ns=2;i=2').set_value(1.5)  # Установка уставки

# Отключение
client.disconnect()
```

## Тестирование
```bash
# Тест чтения всех переменных
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

## Мониторинг
- Health check подключения
- Автоматический перезапуск при сбоях
- Логирование всех операций

## Логи
```bash
docker-compose logs -f opcua-server
```

## Интеграция
- Модель процесса записывает данные
- Контроллеры читают и записывают переменные
- Аналитика собирает метрики
- Telegram бот мониторит состояние
