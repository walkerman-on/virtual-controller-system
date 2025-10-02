# Архитектура цифрового двойника с отказоустойчивым управлением

## Обзор архитектуры

Система представляет собой отказоустойчивый цифровой двойник технологического процесса, построенный на микросервисной архитектуре с использованием Docker контейнеров и протокола OPC UA для межсервисного взаимодействия.

### Принципы проектирования

1. **Модульность** - каждый компонент системы изолирован в отдельном контейнере
2. **Отказоустойчивость** - система продолжает работу при отказе отдельных компонентов
3. **Масштабируемость** - возможность горизонтального масштабирования компонентов
4. **Стандартизация** - использование промышленного протокола OPC UA
5. **Расширяемость** - модульная архитектура позволяет легко добавлять новые компоненты

## Схема взаимодействия компонентов

### Архитектура с резервным контроллером

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
```

### Docker контейнеры

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Network                          │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │opcua-server │  │process-model│  │controller-  │        │
│  │             │  │             │  │  primary    │        │
│  │ Port: 4840  │  │             │  │             │        │
│  │             │  │             │  │             │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                             │
│                                    ┌─────────────┐        │
│                                    │controller-  │        │
│                                    │  backup     │        │
│                                    │             │        │
│                                    │             │        │
│                                    └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Компоненты системы

### 1. OPC UA Server (Центральный узел данных)

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

### 2. Process Model (Модель технологического процесса)

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

### 3. Universal Controller (Универсальный контроллер)

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

## Поток данных и взаимодействие

### Нормальная работа (Primary Active)

1. **Primary Controller** отправляет heartbeat и статус в OPC UA
2. **Backup Controller** отправляет heartbeat и мониторит Primary
3. **Process Model** читает OP_valve, рассчитывает новый PV_level
4. **Primary Controller** читает SP и PV, рассчитывает новый OP_valve
5. **Backup Controller** только мониторит (не записывает OP)

### Отказ основного контроллера

1. **Primary Controller** перестает отправлять heartbeat
2. **Backup Controller** обнаруживает timeout (5 секунд)
3. **Backup Controller** ждет failover_delay (2 секунды)
4. **Backup Controller** устанавливает active_controller = 2
5. **Backup Controller** начинает активное управление
6. **Process Model** продолжает работу без прерывания

### Восстановление основного контроллера

1. **Primary Controller** восстанавливается и отправляет heartbeat
2. **Backup Controller** обнаруживает восстановление Primary
3. **Primary Controller** устанавливает active_controller = 1
4. **Backup Controller** возвращается в режим мониторинга
5. **Primary Controller** возобновляет активное управление

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

**Вертикальное масштабирование:**
- Увеличение ресурсов контейнеров
- Оптимизация алгоритмов расчета
- Кэширование данных

## Безопасность архитектуры

### Сетевая безопасность

- **Изоляция контейнеров:** внутренняя сеть Docker
- **Минимальная экспозиция портов:** только OPC UA сервер (4840)
- **Firewall правила:** ограничение доступа к портам

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

Данная архитектура обеспечивает высокую надежность, отказоустойчивость и производительность системы цифрового двойника с автоматическим переключением между основным и резервным контроллерами.
