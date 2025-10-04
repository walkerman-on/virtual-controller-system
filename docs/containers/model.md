# 🏭 Process Model

## Описание
Модель технологического процесса, имитирующая работу резервуара с жидкостью и клапана управления.

## Функции
- Имитация резервуара с жидкостью
- Моделирование клапана управления
- Расчет уровня, объема, массы и давления
- Интеграция с OPC UA сервером
- Telegram уведомления о критических ситуациях

## Компоненты модели

### Резервуар (Tank)
- **Диаметр**: 2.0 метра
- **Высота**: 3.0 метра
- **Максимальный объем**: ~9.42 м³
- **Плотность жидкости**: 1000 кг/м³
- **Гравитация**: 9.81 м/с²

### Клапан (Valve)
- **Диапазон открытия**: 0-100%
- **Максимальный расход**: 0.5 м³/с
- **Время реакции**: мгновенное

## Физические расчеты
- **Объем**: V = π × (D/2)² × h
- **Масса**: m = ρ × V
- **Давление**: P = ρ × g × h
- **Расход**: Q = Cv × √(ΔP) × opening%

## Конфигурация
- **Интервал обновления**: 1.0 секунда
- **OPC UA сервер**: opc.tcp://opcua-server:4840/freeopcua/server/
- **Логирование**: INFO уровень

## Переменные окружения
```bash
MODEL_UPDATE_INTERVAL=1.0
MODEL_LOG_LEVEL=INFO
OPCUA_SERVER_URL=opc.tcp://opcua-server:4840/freeopcua/server/
TELEGRAM_BOT_TOKEN=your_bot_token
```

## OPC UA Переменные
- `liquid_level` - Уровень жидкости (м)
- `tank_volume` - Объем жидкости (м³)
- `tank_mass` - Масса жидкости (кг)
- `tank_pressure` - Давление (Па)
- `valve_opening` - Открытие клапана (%)
- `flow_rate` - Расход жидкости (м³/с)

## Запуск
```bash
docker-compose up -d model
```

## Проверка состояния
```bash
# Статус контейнера
docker-compose ps model

# Логи модели
docker-compose logs model

# Проверка OPC UA переменных
python3 -c "
from opcua import Client
client = Client('opc.tcp://localhost:4840/freeopcua/server/')
client.connect()
level = client.get_node('ns=2;i=1').get_value()
print(f'Уровень жидкости: {level:.3f}м')
client.disconnect()
"
```

## Тестирование модели
```bash
# Изменение уставки через OPC UA
python3 -c "
from opcua import Client
client = Client('opc.tcp://localhost:4840/freeopcua/server/')
client.connect()
client.get_node('ns=2;i=2').set_value(1.5)  # Установка уставки 1.5м
print('Уставка установлена на 1.5м')
client.disconnect()
"
```

## Критические ситуации
- **Перелив**: Уровень > 2.8м (CRITICAL)
- **Недостаток**: Уровень < 0.2м (CRITICAL)
- **Высокое давление**: > 25000 Па (WARNING)
- **Критическое открытие клапана**: < 5% или > 95% (WARNING)

## Логирование
- Все критические события отправляются в Telegram
- Детальное логирование расчетов
- Сохранение состояния в OPC UA

## Мониторинг
- Health check подключения к OPC UA
- Автоматический перезапуск при сбоях
- Интеграция с контроллерами
