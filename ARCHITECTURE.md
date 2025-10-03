# Архитектура цифрового двойника с отказоустойчивым управлением и базой данных

## Обзор архитектуры

Система представляет собой отказоустойчивый цифровой двойник технологического процесса, построенный на микросервисной архитектуре с использованием Docker контейнеров, протокола OPC UA для межсервисного взаимодействия, PostgreSQL базы данных для хранения исторических данных и REST API сервиса для аналитики, отчетности и управления уставкой.

### Принципы проектирования

1. **Модульность** - каждый компонент системы изолирован в отдельном контейнере
2. **Отказоустойчивость** - система продолжает работу при отказе отдельных компонентов
3. **Масштабируемость** - возможность горизонтального масштабирования компонентов
4. **Стандартизация** - использование промышленного протокола OPC UA
5. **Расширяемость** - модульная архитектура позволяет легко добавлять новые компоненты
6. **Персистентность** - надежное хранение данных в PostgreSQL базе данных
7. **Аналитика** - REST API для получения статистики и отчетов
8. **Управление уставкой** - возможность изменения уставки через REST API

## Схема взаимодействия компонентов

### Архитектура с резервным контроллером и базой данных

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
                    │  │ heartbeats  ││
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
│ │           │ │   │ │ Heartbeat   │ │   ││Heartbeat  ││
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

### Docker контейнеры

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Docker Network                                  │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │opcua-server │  │process-model│  │controller-  │  │controller-  │      │
│  │             │  │             │  │  primary    │  │  backup     │      │
│  │ Port: 4840  │  │             │  │             │  │             │      │
│  │             │  │             │  │             │  │             │      │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘      │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                        │
│  │   database  │  │  watchdog   │  │  analytics  │                        │
│  │             │  │             │  │             │                        │
│  │ Port: 5432  │  │             │  │ Port: 8080  │                        │
│  │             │  │             │  │             │                        │
│  └─────────────┘  └─────────────┘  └─────────────┘                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Компоненты системы

### 1. PostgreSQL Database (База данных)

**Назначение:** Централизованное хранение исторических данных процесса, состояний контроллеров и системных событий.

**Технологии:**
- PostgreSQL 15
- Docker контейнер
- Схемы для организации данных

**Схемы базы данных:**
- `process_data` - данные технологического процесса
- `controller_data` - состояния PID контроллеров и события переключения
- `system_logs` - системные логи и алармы
- `configurations` - конфигурации системы

**Основные таблицы:**
```sql
-- Данные процесса
process_data.process_variables (
    id, timestamp, pv_level, sp_level, op_valve, 
    outlet_flow, inlet_flow, tank_pressure, valve_position
)

-- Состояния PID контроллеров
controller_data.pid_states (
    id, timestamp, controller_id, is_active, kp, ki, kd,
    integral, previous_error, previous_derivative,
    setpoint, process_value, output, error_value
)

-- События переключения
controller_data.failover_events (
    id, timestamp, event_type, from_controller, to_controller,
    reason, duration_seconds, pid_state_before, pid_state_after
)

-- Метрики производительности
process_data.performance_metrics (
    id, timestamp, metric_name, metric_value, unit, service_name, tags
)

-- История изменений уставки
controller_data.setpoint_changes (
    id, timestamp, old_setpoint, new_setpoint, changed_by, change_reason
)
```

**Пользователи и права доступа:**
- `process_user` - полный доступ для записи данных
- `readonly_user` - только чтение для аналитики
- `postgres` - административный доступ

### 2. Analytics Service (Сервис аналитики)

**Назначение:** REST API сервис для получения статистики, отчетов, метрик производительности системы и управления уставкой.

**Технологии:**
- Python 3.11
- Flask web framework
- psycopg2 для работы с PostgreSQL
- opcua library для управления уставкой
- Docker контейнер

**API Endpoints:**

**Проверка состояния:**
```bash
GET /health
```

**Данные процесса:**
```bash
GET /api/process/latest?limit=10
GET /api/process/statistics?hours=24
```

**Данные контроллеров:**
```bash
GET /api/controller/pid-history?limit=50&controller_id=primary
GET /api/system/failover-events?limit=20
```

**Метрики и конфигурация:**
```bash
GET /api/system/performance?hours=24
GET /api/config/current
```

**Управление уставкой:**
```bash
GET /api/setpoint/current
POST /api/setpoint
GET /api/setpoint/history?limit=10
```

**Функции:**
- Получение последних данных процесса
- Расчет статистики за период
- История работы PID контроллеров
- События переключения контроллеров
- Метрики производительности системы
- Текущая конфигурация системы
- Получение текущей уставки
- Установка новой уставки с валидацией
- История изменений уставки
- Интеграция с OPC UA для изменения уставки

### 3. OPC UA Server (Центральный узел данных)

**Назначение:** Централизованное хранение и обмен данными между всеми компонентами системы.

**Технологии:**
- Python 3.11
- opcua library
- Docker контейнер

**Функции:**
- Создание адресного пространства OPC UA
- Инициализация переменных из конфигурации
- Обеспечение синхронного доступа к данным
- Управление подключениями клиентов

**Переменные процесса:**
```
ns=2;i=4  - PV_level (текущий уровень)
ns=2;i=5  - SP_level (уставка)
ns=2;i=6  - OP_valve (управляющее воздействие)
ns=2;i=7  - outlet_flow (расход на выходе)
ns=2;i=8  - inlet_flow (расход на входе)
```

**Переменные отказоустойчивости:**
```
ns=2;i=9  - primary_controller_status
ns=2;i=10 - backup_controller_status
ns=2;i=11 - active_controller (1=primary, 2=backup)
ns=2;i=12 - primary_controller_heartbeat
ns=2;i=13 - backup_controller_heartbeat
```

**Переменные состояния PID:**
```
ns=2;i=14 - pid_integral (интегральная составляющая)
ns=2;i=15 - pid_previous_error (предыдущая ошибка)
ns=2;i=16 - pid_previous_derivative (предыдущая производная)
```

### 4. Process Model (Модель технологического процесса)

**Назначение:** Симуляция физического процесса управления уровнем жидкости в баке.

#### Архитектурные компоненты

**ProcessComponent (Базовый класс):**
```python
class ProcessComponent:
    """Базовый класс для всех компонентов процесса"""
    def __init__(self, name: str, parameters: Dict[str, Any])
    def calculate(self, inputs: Dict[str, float], dt: float) -> Dict[str, float]
    def get_state(self) -> Dict[str, Any]
    def set_state(self, state: Dict[str, Any])
```

**TankModel (Модель бака):**
```python
class TankModel(ProcessComponent):
    """Модель бака с жидкостью"""
    - Расчет уровня жидкости по материальному балансу
    - Учет геометрических параметров (высота, диаметр)
    - Расчет давления на основе уровня и плотности
    - Ограничения по минимальному и максимальному уровню
```

**Valve (Модель клапана):**
```python
class Valve(ProcessComponent):
    """Модель регулирующего клапана"""
    - Расчет пропускной способности по ГОСТ формулам
    - Линейная характеристика клапана
    - Учет перепада давления
    - Ограничения по степени открытия (0-100%)
```

#### Математическая модель

1. **Материальный баланс бака:**
   ```
   dV/dt = Q_in - Q_out
   dh/dt = (Q_in - Q_out) / A
   ```

2. **Расчет расхода через клапан (ГОСТ):**
   ```
   Q = (Kv / (3.57 × 10⁴)) × √(Δp / ρ)
   Kv = Kv0 + (Kvs - Kv0) × (OP / 100)
   ```

3. **Расчет давления:**
   ```
   p = ρ × g × h
   ```

### 5. Universal Controller (Универсальный контроллер)

**Назначение:** Реализация ПИД-регулирования с поддержкой режимов основного и резервного контроллера.

#### Режимы работы

**Primary Mode (Основной режим):**
- Активное управление процессом
- Отправка heartbeat сигналов
- Мониторинг собственного состояния
- Автоматическое восстановление управления при возврате в строй

**Backup Mode (Резервный режим):**
- Мониторинг состояния основного контроллера
- Готовность к немедленному переключению
- Отправка собственных heartbeat сигналов
- Автоматическая активация при отказе основного

#### PID Controller (ПИД-регулятор)

**Алгоритм управления:**
```python
class PIDController:
    """ПИД-регулятор по ГОСТ стандартам"""
    
    def calculate(self, setpoint, process_value, dt):
        # Нормализация входных значений
        SP_norm = (setpoint - self.pv_min) / (self.pv_max - self.pv_min)
        PV_norm = (process_value - self.pv_min) / (self.pv_max - self.pv_min)
        
        # Расчет ошибки
        error = SP_norm - PV_norm
        
        # Пропорциональная составляющая
        P = self.kp * error
        
        # Интегральная составляющая с ограничением
        self.integral += error * dt
        self.integral = max(-self.integral_limit, 
                           min(self.integral, self.integral_limit))
        I = self.ki * self.integral
        
        # Дифференциальная составляющая с фильтрацией
        derivative = (error - self.prev_error) / dt
        self.filtered_derivative = (derivative + 
                                   self.filter_time * self.filtered_derivative) / \
                                  (1 + self.filter_time)
        D = self.kd * self.filtered_derivative
        
        # Итоговое управляющее воздействие
        output = P + I + D
        return max(self.output_min, min(output, self.output_max))
```

#### Логика отказоустойчивости

**Heartbeat механизм:**
```python
def update_controller_status(self):
    """Обновление статуса и heartbeat"""
    current_time = time.time()
    if self.mode == 'primary':
        self._set_variable_value('primary_controller_heartbeat', current_time)
    else:
        self._set_variable_value('backup_controller_heartbeat', current_time)
```

#### Сохранение состояния PID

**Автоматическое сохранение:**
```python
async def save_pid_state(self):
    """Сохранение состояния PID в OPC UA"""
    if self.controller:
        state = self.controller.get_state()
        await self.set_variable_value('pid_integral', state['integral'])
        await self.set_variable_value('pid_previous_error', state['previous_error'])
        await self.set_variable_value('pid_previous_derivative', state['previous_derivative'])
```

**Восстановление при запуске:**
```python
async def restore_pid_state(self):
    """Восстановление состояния PID из OPC UA"""
    integral = await self.get_variable_value('pid_integral')
    previous_error = await self.get_variable_value('pid_previous_error')
    previous_derivative = await self.get_variable_value('pid_previous_derivative')
    
    if all(v is not None for v in [integral, previous_error, previous_derivative]):
        state = {'integral': integral, 'previous_error': previous_error, 'previous_derivative': previous_derivative}
        self.controller.set_state(state)
        return True
    return False
```

**Логика переключения:**
```python
def check_and_switch_controller(self):
    """Проверка и переключение контроллеров"""
    current_time = time.time()
    primary_heartbeat = self._get_variable_value('primary_controller_heartbeat')
    
    primary_is_alive = (current_time - primary_heartbeat) < self.heartbeat_timeout
    
    if self.mode == 'backup' and not primary_is_alive:
        if not self.failover_triggered:
            self.failover_start_time = current_time
            self.failover_triggered = True
        elif (current_time - self.failover_start_time) > self.failover_delay:
            # Активация резервного контроллера
            self._set_variable_value('active_controller', 2)
            self.is_active = True
```

### 6. Watchdog (Мониторинг контроллеров)

**Назначение:** Отдельный сервис для мониторинга состояния контроллеров через OPC UA heartbeat механизм.

**Технологии:**
- Python 3.11
- opcua library для мониторинга OPC UA переменных
- Docker контейнер

**Функции:**
- Мониторинг heartbeat переменных контроллеров
- Обнаружение отказов контроллеров
- Логирование событий переключения
- Сохранение событий в базу данных

**Алгоритм работы:**
```python
def monitor_controllers(self):
    """Мониторинг состояния контроллеров"""
    primary_heartbeat = self.get_variable_value('primary_controller_heartbeat')
    backup_heartbeat = self.get_variable_value('backup_controller_heartbeat')
    active_controller = self.get_variable_value('active_controller')
    
    current_time = time.time()
    
    # Проверка timeout'ов
    primary_timeout = (current_time - primary_heartbeat) > self.heartbeat_timeout
    backup_timeout = (current_time - backup_heartbeat) > self.heartbeat_timeout
    
    # Логирование состояния
    if primary_timeout and active_controller == 1:
        logger.warning("⚠️ Основной контроллер недоступен")
    elif backup_timeout and active_controller == 2:
        logger.warning("⚠️ Резервный контроллер недоступен")
```

## Поток данных и взаимодействие

### Нормальная работа (Primary Active)

1. **Primary Controller** отправляет heartbeat и статус в OPC UA
2. **Backup Controller** отправляет heartbeat и мониторит Primary
3. **Process Model** читает OP_valve, рассчитывает новый PV_level
4. **Primary Controller** читает SP и PV, рассчитывает новый OP_valve
5. **Backup Controller** только мониторит (не записывает OP)
6. **Process Model** сохраняет данные процесса в PostgreSQL
7. **Primary Controller** сохраняет состояние PID в PostgreSQL
8. **Watchdog** мониторит heartbeat переменные
9. **Analytics Service** предоставляет API для получения данных из БД

### Отказ основного контроллера

1. **Primary Controller** перестает отправлять heartbeat
2. **Backup Controller** обнаруживает timeout (5 секунд)
3. **Watchdog** обнаруживает отсутствие heartbeat основного контроллера
4. **Backup Controller** ждет failover_delay (2 секунды)
5. **Backup Controller** устанавливает active_controller = 2
6. **Backup Controller** начинает активное управление
7. **Process Model** продолжает работу без прерывания
8. **Backup Controller** сохраняет событие переключения в PostgreSQL
9. **Analytics Service** может предоставить информацию о событии переключения

### Восстановление основного контроллера

1. **Primary Controller** восстанавливается и отправляет heartbeat
2. **Backup Controller** обнаруживает восстановление Primary
3. **Watchdog** обнаруживает восстановление heartbeat основного контроллера
4. **Primary Controller** устанавливает active_controller = 1
5. **Backup Controller** возвращается в режим мониторинга
6. **Primary Controller** возобновляет активное управление
7. **Primary Controller** восстанавливает состояние PID из OPC UA
8. **Backup Controller** сохраняет событие возврата в PostgreSQL
9. **Analytics Service** может предоставить информацию о событии возврата

## Параметры системы

### Модель процесса

**Бак:**
- Высота: 3.0 м
- Диаметр: 2.0 м  
- Плотность жидкости: 1000 кг/м³
- Начальный уровень: 1.5 м
- Площадь поперечного сечения: 3.14 м²

**Клапан:**
- Начальное открытие: 50%
- Диапазон: 0-100%
- Kv0 (минимальный): 0.01
- Kvs (максимальный): 800
- Расчет по ГОСТ: Q = (Kv / (3.57 × 10⁴)) × √(Δp / ρ)

**Потоки:**
- Входной расход: 100 м³/ч (постоянный)
- Выходной расход: 160-200 м³/ч при Kv100
- Гидростатическое давление: ρ × g × h

### PID-регулятор

**Настройки по ГОСТ:**
- Kp (пропорциональный): 15.0
- Ki (интегральный): 0.1
- Kd (дифференциальный): 1.0
- Уставка: 1.6 м
- Выходной диапазон: 0-100%
- Ограничение интеграла: 5.0

### База данных

**PostgreSQL:**
- Версия: 15
- Порт: 5432
- База данных: digital_twin_db
- Пользователи: process_user, readonly_user, postgres
- Схемы: process_data, controller_data, system_logs, configurations

**Сервис аналитики:**
- Порт: 8080
- Framework: Flask
- Подключение к БД: psycopg2
- OPC UA интеграция: opcua library
- API endpoints: 9 основных endpoints (включая управление уставкой)

### Отказоустойчивость

**Временные параметры:**
- Heartbeat timeout: 5.0 секунд
- Failover delay: 2.0 секунды
- Controller update interval: 0.1 секунды
- Model update interval: 0.1 секунды

## Мониторинг и диагностика

### Логирование

Структурированное логирование во всех компонентах:

```python
# Примеры логов
logger.info("✓ Подключение к OPC UA серверу установлено")
logger.warning("⚠️ Основной контроллер недоступен")
logger.critical("🚨 ПЕРЕКЛЮЧЕНИЕ НА РЕЗЕРВНЫЙ КОНТРОЛЛЕР!")
logger.info("✅ Основной контроллер восстановлен")
```

### Индикаторы состояния

**В логах основного контроллера:**
- `ОСНОВНОЙ PID: SP=X.Xм, PV=X.Xм, OP=X.X%` - активное управление
- `ОСНОВНОЙ (мониторинг)` - режим мониторинга после восстановления

**В логах резервного контроллера:**
- `РЕЗЕРВНЫЙ (мониторинг)` - нормальный режим мониторинга
- `⚠️ Основной контроллер недоступен` - обнаружение отказа
- `🚨 ПЕРЕКЛЮЧЕНИЕ НА РЕЗЕРВНЫЙ КОНТРОЛЛЕР!` - активация резервного
- `РЕЗЕРВНЫЙ ПИ расчет` - активное управление резервным контроллером
- `✅ Основной контроллер восстановлен` - возврат к мониторингу

## Расширение архитектуры

### Добавление новых компонентов процесса

1. **Создание нового компонента:**
   ```python
   class HeatExchanger(ProcessComponent):
       def calculate(self, inputs: Dict[str, float], dt: float) -> Dict[str, float]:
           # Реализация расчета теплообменника
           return outputs
   ```

2. **Регистрация в системе:**
   - Добавить параметры в `config.json`
   - Обновить модель для использования нового компонента
   - Добавить соответствующие OPC UA переменные

### Масштабирование системы

**Горизонтальное масштабирование:**
- Несколько экземпляров модели для разных процессов
- Кластер OPC UA серверов
- Load balancing для клиентов
- Репликация PostgreSQL базы данных
- Кластер сервисов аналитики

**Вертикальное масштабирование:**
- Увеличение ресурсов контейнеров
- Оптимизация алгоритмов расчета
- Кэширование данных в PostgreSQL
- Оптимизация запросов к базе данных

## Безопасность архитектуры

### Сетевая безопасность

- **Изоляция контейнеров:** внутренняя сеть Docker
- **Минимальная экспозиция портов:** только OPC UA сервер (4840), PostgreSQL (5432), Analytics (8080)
- **Firewall правила:** ограничение доступа к портам
- **База данных:** отдельные пользователи с ограниченными правами
- **API сервис:** работает только внутри Docker сети

### Безопасность приложений

- **Принцип минимальных привилегий:** непривилегированные пользователи
- **Валидация данных:** проверка входных параметров
- **Ограничения диапазонов:** контроль значений переменных

## Производительность и оптимизация

### Временные характеристики

- **Цикл модели:** 100 мс (configurable)
- **Цикл контроллера:** 100 мс (configurable)
- **Heartbeat интервал:** 1 секунда
- **Timeout переключения:** 5 секунд
- **Задержка переключения:** 2 секунды
- **Сохранение в БД:** каждую итерацию (100 мс)
- **API ответ:** < 100 мс для простых запросов

### Оптимизация производительности

1. **Синхронное программирование:**
   - Блокирующие OPC UA операции для надежности
   - Последовательная обработка данных
   - Контролируемое использование ресурсов

2. **Кэширование:**
   - Кэширование Node ID для OPC UA переменных
   - Локальное кэширование конфигурации
   - Оптимизация частоты обновлений

3. **Алгоритмическая оптимизация:**
   - Эффективные численные методы
   - Минимизация вычислительной сложности
   - Предварительные расчеты констант

4. **Оптимизация базы данных:**
   - Индексы на часто используемые поля
   - Партиционирование таблиц по времени
   - Оптимизация запросов
   - Сжатие данных

5. **Оптимизация API:**
   - Кэширование результатов запросов
   - Пагинация для больших наборов данных
   - Асинхронная обработка запросов
   - Оптимизация JSON сериализации

Данная архитектура обеспечивает высокую надежность, отказоустойчивость и производительность системы цифрового двойника с автоматическим переключением между основным и резервным контроллерами, надежным хранением данных в PostgreSQL и удобным API для аналитики.
