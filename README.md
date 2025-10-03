# Цифровой двойник технологического процесса с API управления

Система цифрового двойника технологического процесса с использованием Python, Docker и OPC UA для моделирования и управления уровнем жидкости в баке. Включает отказоустойчивую архитектуру с автоматическим переключением между основным и резервным контроллерами, PostgreSQL базу данных для хранения исторических данных и REST API сервис для аналитики, отчетности и управления уставкой.

## Описание проекта

Данный проект представляет собой реализацию цифрового двойника технологического процесса управления уровнем жидкости в резервуаре с **отказоустойчивой системой управления**. Система построена на основе микросервисной архитектуры с использованием Docker контейнеров и протокола OPC UA для межсервисного взаимодействия.

### Основные возможности

- 🏭 **Моделирование технологического процесса** - реалистичная модель бака с жидкостью
- 🎛️ **ПИД-регулирование** - автоматическое управление уровнем жидкости по ГОСТ формулам
- 🔄 **Замкнутый контур управления** - непрерывная работа системы
- 🛡️ **Отказоустойчивость** - автоматическое переключение на резервный контроллер
- 💾 **Сохранение состояния PID** - восстановление интегральной составляющей при переключениях
- 📊 **База данных PostgreSQL** - хранение исторических данных процесса и контроллеров
- 🔍 **REST API аналитики** - получение статистики, отчетов и метрик производительности
- 🎯 **API управления уставкой** - изменение уставки уровня через REST API
- 📡 **OPC UA интеграция** - стандартный промышленный протокол
- 🐳 **Контейнеризация** - легкое развертывание и масштабирование
- 🔧 **Модульная архитектура** - возможность расширения функциональности
- ⚡ **Горячий резерв** - резервный контроллер работает в режиме мониторинга
- 🐕 **Watchdog мониторинг** - отдельный контейнер для мониторинга состояния контроллеров

## Архитектура системы

Система состоит из семи основных компонентов:

1. **OPC UA Server** - центральный сервер для обмена данными между компонентами
2. **Process Model** - модель технологического процесса (бак с жидкостью)
3. **Primary Controller** - основной ПИД-контроллер для управления процессом
4. **Backup Controller** - резервный ПИД-контроллер (горячий резерв)
5. **Watchdog** - мониторинг состояния контроллеров через OPC UA heartbeat
6. **PostgreSQL Database** - база данных для хранения исторических данных
7. **Analytics Service** - REST API сервис для аналитики и отчетности

### Схема взаимодействия

```
                    ┌─────────────────┐
                    │   OPC UA Server │
                    │                 │
                    │  ┌─────────────┐│
                    │  │ PV_level    ││
                    │  │ SP_level    ││
                    │  │ OP_valve    ││
                    │  │ primary_st  ││
                    │  │ backup_st   ││
                    │  │ active_ctrl ││
                    │  └─────────────┘│
                    └─────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼───────┐   ┌────────▼────────┐   ┌──────▼──────┐
│ Process Model │   │ Primary Control │   │Backup Control│
│               │   │                 │   │             │
│ ┌───────────┐ │   │ ┌─────────────┐ │   │┌───────────┐│
│ │   Tank    │ │   │ │ PID Logic   │ │   ││PID Logic  ││
│ │   Valve   │ │◄──┤ │  (ACTIVE)   │ │   ││(MONITOR)  ││
│ │           │ │   │ │             │ │   ││           ││
│ └───────────┘ │   │ └─────────────┘ │   │└───────────┘│
└───────────────┘   └─────────────────┘   └─────────────┘
        │                    │                    │
        │                    │                    │
        ▼                    ▼                    ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ PostgreSQL  │    │ PostgreSQL  │    │ PostgreSQL  │
│   Database  │    │   Database  │    │   Database  │
│             │    │             │    │             │
│ Process     │    │ PID States  │    │ Failover    │
│ Data        │    │             │    │ Events      │
└─────────────┘    └─────────────┘    └─────────────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
                    ┌────────▼────────┐
                    │ Analytics API   │
                    │                 │
                    │ ┌─────────────┐ │
                    │ │ REST API    │ │
                    │ │ Endpoints   │ │
                    │ │             │ │
                    │ └─────────────┘ │
                    └─────────────────┘
```

### Отказоустойчивость

- **Нормальная работа:** Основной контроллер активен, резервный мониторит
- **При отказе основного:** Резервный автоматически активируется через 2 секунды
- **При восстановлении:** Управление автоматически возвращается основному
- **Сохранение состояния:** PID состояние сохраняется в OPC UA и восстанавливается при переключениях
- **Непрерывность управления:** Интегральная составляющая не теряется при переключениях

### Технологический процесс

Моделируется бак с жидкостью со следующими характеристиками:
- **Высота бака:** 3.0 м
- **Диаметр бака:** 2.0 м  
- **Плотность жидкости:** 1000 кг/м³
- **Постоянный входной расход:** 100 м³/ч
- **Начальный уровень:** 1.5 м
- **Управляемый параметр:** уровень жидкости
- **Целевой расход при Kv100:** 160-200 м³/ч

## Структура проекта

```
├── docker-compose.yml          # Конфигурация Docker Compose
├── config.json                 # Конфигурация системы
├── docker.env                  # Переменные окружения Docker
├── CONNECTION_SETTINGS.md      # Документация по настройкам подключения
├── start_system.sh             # Скрипт запуска системы
├── test_setpoint_api.sh        # Скрипт тестирования API уставки
├── SETPOINT_API.md             # Документация API управления уставкой
├── opcua-server/               # OPC UA сервер
│   ├── Dockerfile
│   ├── requirements.txt
│   └── server.py
├── model/                      # Модель процесса
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── process_model.py        # Базовые классы модели
│   └── model_client.py         # Клиент модели
├── controller/                 # Универсальный контроллер
│   ├── Dockerfile
│   ├── requirements.txt
│   └── universal_controller.py # Основной + резервный
├── watchdog/                   # Мониторинг контроллеров
│   ├── Dockerfile
│   ├── requirements.txt
│   └── simple_watchdog.py     # Простой watchdog
├── database/                   # База данных PostgreSQL
│   ├── Dockerfile
│   ├── init/
│   │   └── 01_init_schema.sql # Скрипт инициализации БД
│   └── database_manager.py    # Менеджер базы данных
└── analytics/                  # Сервис аналитики и API
    ├── Dockerfile
    ├── requirements.txt
    └── analytics_service.py    # REST API сервис с управлением уставкой
```

## Конфигурация

### Параметры модели (config.json)

```json
{
  "model_parameters": {
    "tank_height": 3.0,           // Высота бака (м)
    "tank_diameter": 2.0,         // Диаметр бака (м)
    "liquid_density": 1000.0,     // Плотность жидкости (кг/м³)
    "constant_inlet_flow": 100.0, // Постоянный входной расход (м³/ч)
    "initial_liquid_level": 1.5,  // Начальный уровень жидкости (м)
    "initial_valve_opening": 50.0, // Начальное открытие клапана (%)
    "simulation_time_step": 0.1   // Временной шаг симуляции (с)
  }
}
```

### Параметры PID-регулятора

```json
{
  "pid_controller": {
    "kp": 15.0,                   // Пропорциональный коэффициент
    "ki": 0.1,                    // Интегральный коэффициент
    "kd": 1.0,                    // Дифференциальный коэффициент
    "setpoint": 1.6,              // Уставка уровня (м)
    "output_min": 0.0,            // Минимальное выходное значение (%)
    "output_max": 100.0,          // Максимальное выходное значение (%)
    "integral_limit": 5.0,        // Ограничение интегральной составляющей
    "derivative_filter_time": 0.1  // Время фильтрации производной (с)
  }
}
```

### Параметры отказоустойчивости

```json
{
  "system_settings": {
    "controller_heartbeat_timeout": 5.0,  // Таймаут heartbeat (с)
    "controller_failover_delay": 2.0      // Задержка переключения (с)
  }
}
```

## Настройки подключения

### 🔗 URL и Endpoints

**OPC UA Server:**
- Endpoint: `opc.tcp://localhost:4840/freeopcua/server/`
- Namespace: `ProcessVariables`

**PostgreSQL Database:**
- Host: `localhost`
- Port: `5432`
- Database: `digital_twin_db`
- User: `process_user`
- Password: `process_password`

**Analytics API:**
- Base URL: `http://localhost:8080`
- Health Check: `http://localhost:8080/health`
- Latest Data: `http://localhost:8080/api/process/latest`
- Statistics: `http://localhost:8080/api/process/statistics`

### 📁 Файлы конфигурации

- **`config.json`** - Основная конфигурация системы
- **`docker.env`** - Переменные окружения для Docker Compose
- **`CONNECTION_SETTINGS.md`** - Подробная документация по настройкам подключения

### 🚀 Быстрый просмотр настроек

```bash
# Проверить состояние API
curl http://localhost:8080/health

# Последние данные процесса
curl http://localhost:8080/api/process/latest?limit=5

# Получить текущую уставку
curl http://localhost:8080/api/setpoint/current
```

## Установка и запуск

### Предварительные требования

- Docker
- Docker Compose

### Быстрый запуск

1. **Клонирование и подготовка:**
   ```bash
   git clone <repository-url>
   cd digital-twin-process
   ```

2. **Запуск системы одной командой:**
   ```bash
   ./start_system.sh
   ```

### Ручной запуск

1. **Запуск всех сервисов:**
   ```bash
   docker-compose up --build -d
   ```

2. **Проверка статуса:**
   ```bash
   docker-compose ps
   ```

3. **Просмотр логов:**
   ```bash
   # Основной контроллер
   docker-compose logs controller-primary -f
   
   # Резервный контроллер
   docker-compose logs controller-backup -f
   
   # Модель процесса
   docker-compose logs model -f
   
   # База данных
   docker-compose logs database -f
   
   # Сервис аналитики
   docker-compose logs analytics -f
   
   # Все сервисы
   docker-compose logs -f
   ```

4. **Остановка системы:**
   ```bash
   docker-compose down
   ```

### Порядок запуска сервисов

1. **PostgreSQL Database** запускается первым и инициализирует схему
2. **OPC UA Server** запускается вторым и создает переменные
3. **Process Model** подключается к серверу и начинает симуляцию
4. **Primary Controller** подключается и начинает управление
5. **Backup Controller** подключается и начинает мониторинг
6. **Watchdog** запускается для мониторинга контроллеров
7. **Analytics Service** запускается для предоставления API

## Мониторинг системы

### OPC UA переменные

Система создает следующие переменные на OPC UA сервере:

**Переменные процесса:**
- `PV_level` (ns=2;i=4) - текущий уровень жидкости в баке (м)
- `SP_level` (ns=2;i=5) - уставка уровня жидкости (м)
- `OP_valve` (ns=2;i=6) - управляющее воздействие на клапан (%)
- `outlet_flow` (ns=2;i=7) - расход через выходной клапан (м³/ч)
- `inlet_flow` (ns=2;i=8) - постоянный входной расход (м³/ч)

**Переменные отказоустойчивости:**
- `primary_controller_status` (ns=2;i=9) - статус основного контроллера
- `backup_controller_status` (ns=2;i=10) - статус резервного контроллера
- `active_controller` (ns=2;i=11) - активный контроллер (1=основной, 2=резервный)
- `primary_controller_heartbeat` (ns=2;i=12) - heartbeat основного контроллера
- `backup_controller_heartbeat` (ns=2;i=13) - heartbeat резервного контроллера

**Переменные состояния PID:**
- `pid_integral` (ns=2;i=14) - интегральная составляющая ПИД-регулятора
- `pid_previous_error` (ns=2;i=15) - предыдущая ошибка ПИД-регулятора
- `pid_previous_derivative` (ns=2;i=16) - предыдущая производная ПИД-регулятора

### Подключение к OPC UA серверу

Для мониторинга системы можно использовать OPC UA клиент:

- **Endpoint:** `opc.tcp://localhost:4840/freeopcua/server/`
- **Namespace:** `ProcessVariables`

### Примеры OPC UA клиентов

1. **UaExpert** - бесплатный OPC UA клиент
2. **Prosys OPC UA Browser** - веб-клиент
3. **Python OPC UA клиент:**

```python
from opcua import Client

client = Client("opc.tcp://localhost:4840/freeopcua/server/")
client.connect()

# Получение значения уровня
level_node = client.get_node("ns=2;i=4")
current_level = level_node.get_value()
print(f"Текущий уровень: {current_level} м")

# Проверка активного контроллера
active_controller_node = client.get_node("ns=2;i=11")
active_controller = active_controller_node.get_value()
controller_name = "Основной" if active_controller == 1 else "Резервный"
print(f"Активный контроллер: {controller_name}")

client.disconnect()
```

## База данных и аналитика

### PostgreSQL база данных

Система использует PostgreSQL для хранения исторических данных:

**Схемы базы данных:**
- `process_data` - данные технологического процесса
- `controller_data` - состояния PID контроллеров и события переключения
- `system_logs` - системные логи и алармы
- `configurations` - конфигурации системы

**Основные таблицы:**
- `process_data.process_variables` - переменные процесса (уровень, расходы, давление)
- `controller_data.pid_states` - состояния PID контроллеров
- `controller_data.failover_events` - события переключения контроллеров
- `process_data.performance_metrics` - метрики производительности

### REST API сервис аналитики

Сервис аналитики предоставляет REST API на порту 8080 для получения данных:

**Основные endpoints:**

#### Проверка состояния
```bash
GET /health
```

#### Данные процесса
```bash
# Последние данные процесса
GET /api/process/latest?limit=10

# Статистика за период
GET /api/process/statistics?hours=24
```

#### Данные контроллеров
```bash
# История PID контроллера
GET /api/controller/pid-history?limit=50&controller_id=primary

# События переключения
GET /api/system/failover-events?limit=20
```

#### Метрики и конфигурация
```bash
# Метрики производительности
GET /api/system/performance?hours=24

# Текущая конфигурация
GET /api/config/current
```

#### API управления уставкой
```bash
# Получение текущей уставки
GET /api/setpoint/current

# Установка новой уставки
POST /api/setpoint
Content-Type: application/json
{
  "setpoint": 1.6,
  "reason": "Оптимизация процесса"
}

# История изменений уставки
GET /api/setpoint/history?limit=10
```

### Примеры использования API

#### Получение последних данных процесса
```bash
curl -s "http://localhost:8080/api/process/latest?limit=5" | python3 -m json.tool
```

#### Получение статистики за час
```bash
curl -s "http://localhost:8080/api/process/statistics?hours=1" | python3 -m json.tool
```

#### Проверка истории PID контроллера
```bash
curl -s "http://localhost:8080/api/controller/pid-history?limit=3" | python3 -m json.tool
```

#### Управление уставкой
```bash
# Получить текущую уставку
curl -s "http://localhost:8080/api/setpoint/current" | python3 -m json.tool

# Установить новую уставку
curl -X POST "http://localhost:8080/api/setpoint" \
  -H "Content-Type: application/json" \
  -d '{"setpoint": 1.6, "reason": "Оптимизация процесса"}' | python3 -m json.tool

# Посмотреть историю изменений
curl -s "http://localhost:8080/api/setpoint/history?limit=5" | python3 -m json.tool
```

### Мониторинг системы

Для тестирования API управления уставкой используйте предоставленный скрипт:

```bash
# Автоматическое тестирование API уставки
./test_setpoint_api.sh
```

Скрипт автоматически:
- Проверяет доступность API
- Тестирует получение текущей уставки
- Тестирует установку различных значений
- Проверяет обработку некорректных значений
- Просматривает историю изменений
- Возвращает исходную уставку

### Прямая работа с базой данных

Для прямого доступа к базе данных:

```bash
# Подключение к базе данных
docker exec -it digital-twin-db psql -U postgres -d digital_twin_db

# Проверка количества записей
SELECT 
    'process_data.process_variables' as table_name, 
    COUNT(*) as record_count
FROM process_data.process_variables
UNION ALL
SELECT 
    'controller_data.pid_states' as table_name, 
    COUNT(*) as record_count
FROM controller_data.pid_states;

# Последние записи процесса
SELECT timestamp, pv_level, sp_level, op_valve, outlet_flow
FROM process_data.process_variables 
ORDER BY timestamp DESC 
LIMIT 5;
```

## Сохранение состояния PID

### Автоматическое сохранение

Система автоматически сохраняет состояние PID-регулятора в OPC UA переменные:
- После каждого успешного расчета управляющего воздействия
- Интегральная составляющая, предыдущая ошибка и производная сохраняются
- При восстановлении контроллера состояние автоматически восстанавливается

### Преимущества

- **Плавное переключение:** Нет скачков управляющего воздействия при переключениях
- **Сохранение качества управления:** Интегральная составляющая не теряется
- **Автоматическое восстановление:** Без вмешательства оператора
- **Непрерывность процесса:** Система продолжает работу с текущего состояния

### Логи восстановления

```bash
# Пример логов при восстановлении состояния
pid-controller-primary | ПИД-регулятор инициализирован: Kp=15.0, Ki=0.1, Kd=1.0
pid-controller-primary | Состояние ПИД-регулятора восстановлено: integral=0.407, prev_error=0.058
pid-controller-primary | ОСНОВНОЙ контроллер восстановил состояние PID из OPC UA
```

## Тестирование отказоустойчивости

### Тестирование переключения на резервный

```bash
# 1. Запуск системы
docker-compose up -d

# 2. Проверка нормальной работы
docker-compose logs controller-primary --tail=5
docker-compose logs controller-backup --tail=5

# 3. Остановка основного контроллера
docker-compose stop controller-primary

# 4. Проверка активации резервного (подождать 2-5 секунд)
docker-compose logs controller-backup --tail=10

# 5. Восстановление основного контроллера
docker-compose start controller-primary

# 6. Проверка возврата управления основному
docker-compose logs controller-backup --tail=10
```

### Индикаторы переключения

**В логах резервного контроллера:**
- `РЕЗЕРВНЫЙ (мониторинг)` - нормальный режим мониторинга
- `⚠️ Основной контроллер недоступен` - обнаружение отказа
- `🚨 ПЕРЕКЛЮЧЕНИЕ НА РЕЗЕРВНЫЙ КОНТРОЛЛЕР!` - активация резервного
- `РЕЗЕРВНЫЙ ПИ расчет` - активное управление резервным контроллером
- `✅ Основной контроллер восстановлен` - возврат к мониторингу

## Настройка параметров

### Изменение параметров модели

Отредактируйте файл `config.json` и перезапустите модель:

```bash
docker-compose restart model
```

### Изменение параметров PID-регулятора

Отредактируйте файл `config.json` и перезапустите контроллеры:

```bash
docker-compose restart controller-primary controller-backup
```

### Настройка отказоустойчивости

В `config.json` можно настроить:
- `controller_heartbeat_timeout` - время ожидания heartbeat (по умолчанию 5.0 сек)
- `controller_failover_delay` - задержка переключения (по умолчанию 2.0 сек)

### Изменение уставки

Уставку можно изменить несколькими способами:

1. **Через REST API (рекомендуется):**
   ```bash
   curl -X POST "http://localhost:8080/api/setpoint" \
     -H "Content-Type: application/json" \
     -d '{"setpoint": 1.6, "reason": "Оптимизация процесса"}'
   ```

2. **Через OPC UA клиент:**
   ```python
   from opcua import Client
   
   client = Client("opc.tcp://localhost:4840/freeopcua/server/")
   client.connect()
   
   setpoint_node = client.get_node("ns=2;i=5")
   setpoint_node.set_value(1.6)
   
   client.disconnect()
   ```

3. **Через редактирование config.json:**
   Отредактируйте файл `config.json` и перезапустите контроллеры:
   ```bash
   docker-compose restart controller-primary controller-backup
   ```

## Расширение системы

### Добавление новых компонентов модели

1. Создайте новый класс, наследующий от `ProcessComponent`
2. Реализуйте метод `calculate()`
3. Добавьте компонент в `ProcessModel`

### Пример нового компонента

```python
class HeatExchanger(ProcessComponent):
    def __init__(self, name: str, parameters: Dict[str, Any]):
        super().__init__(name, parameters)
        self.heat_transfer_coefficient = parameters.get('htc', 1000.0)
    
    def calculate(self, inputs: Dict[str, float], dt: float) -> Dict[str, float]:
        # Реализация расчета теплообменника
        return {'outlet_temperature': calculated_temp}
```

### Добавление новых переменных OPC UA

1. Добавьте переменную в `config.json` в секцию `opcua_variables`
2. Обновите код сервера для создания переменной
3. Обновите клиенты для работы с новой переменной

## Отладка

### Просмотр логов

```bash
# Детальные логи всех сервисов
docker-compose logs -f --tail=100

# Логи конкретного сервиса
docker-compose logs -f controller-primary
docker-compose logs -f controller-backup
docker-compose logs -f model
docker-compose logs -f opcua-server
```

### Проверка состояния контейнеров

```bash
docker-compose ps
```

### Подключение к контейнеру

```bash
# Подключение к контейнеру модели
docker-compose exec model bash

# Подключение к основному контроллеру
docker-compose exec controller-primary bash

# Подключение к резервному контроллеру
docker-compose exec controller-backup bash

# Подключение к базе данных
docker-compose exec database psql -U postgres -d digital_twin_db

# Подключение к сервису аналитики
docker-compose exec analytics bash
```

### Диагностика отказоустойчивости

```bash
# Проверка heartbeat переменных через OPC UA
python3 -c "
from opcua import Client
client = Client('opc.tcp://localhost:4840/freeopcua/server/')
client.connect()
primary_hb = client.get_node('ns=2;i=12').get_value()
backup_hb = client.get_node('ns=2;i=13').get_value()
active = client.get_node('ns=2;i=11').get_value()
print(f'Primary HB: {primary_hb}, Backup HB: {backup_hb}, Active: {active}')
client.disconnect()
"
```

## Производительность

### Оптимизация временных шагов

- **Модель:** `simulation_time_step` - влияет на точность симуляции
- **Контроллеры:** `controller_update_interval` - влияет на скорость реакции
- **Отказоустойчивость:** `controller_failover_delay` - влияет на время переключения

### Масштабирование

Система спроектирована для горизонтального масштабирования:

- Каждый компонент работает в отдельном контейнере
- OPC UA сервер обеспечивает централизованное управление данными
- PostgreSQL база данных обеспечивает надежное хранение данных
- REST API сервис позволяет легко интегрироваться с внешними системами
- Модель продолжает работу даже при недоступности контроллеров
- Резервный контроллер обеспечивает непрерывность управления

## Безопасность

- Все контейнеры запускаются под непривилегированным пользователем
- Сетевое взаимодействие ограничено внутренней сетью Docker
- PostgreSQL база данных использует отдельные пользователи с ограниченными правами
- REST API сервис работает только внутри Docker сети
- OPC UA сервер использует стандартные механизмы безопасности
- Отказоустойчивость обеспечивает непрерывность работы при сбоях

## Лицензия

MIT License

## Поддержка

Для вопросов и предложений создавайте Issues в репозитории проекта.