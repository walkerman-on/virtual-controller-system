# Система конфигурации - Единый источник правды

## Обзор

Новая система конфигурации разделяет настройки на два файла:

- **`.env`** - переменные окружения (порты, пароли, токены, настройки подключения)
- **`config.json`** - параметры модели и системы (размеры бака, PID коэффициенты, OPC UA переменные)

## Структура файлов

### .env файл
Содержит только переменные окружения:

```bash
# TELEGRAM BOT
TELEGRAM_BOT_TOKEN=your_bot_token_here
ADMIN_CHAT_ID=your_chat_id_here

# БАЗА ДАННЫХ
DB_HOST=digital-twin-db
DB_PORT=5432
DB_NAME=digital_twin_db
DB_USER=postgres
DB_PASSWORD=postgres_password

# OPC UA СЕРВЕР
OPCUA_SERVER_HOST=opcua-server
OPCUA_SERVER_PORT=4840
OPCUA_SERVER_ENDPOINT=opc.tcp://opcua-server:4840/freeopcua/server/

# И другие переменные окружения...
```

### config.json файл
Содержит параметры модели и системы:

```json
{
  "model_parameters": {
    "tank_height": 3.0,
    "tank_diameter": 2.0,
    "liquid_density": 1000.0
  },
  "pid_controller": {
    "kp": 15.0,
    "ki": 0.1,
    "kd": 1.0,
    "setpoint": 1.6
  },
  "opcua_variables": {
    "process_variables": {
      "PV_level": {
        "node_id": "ns=2;i=4",
        "description": "Текущий уровень жидкости в баке"
      }
    }
  }
}
```

## Использование

### В Python коде

```python
from utils.config_loader import get_config, get_config_section, get_env_value

# Получить полную конфигурацию
config = get_config()

# Получить секцию конфигурации
model_params = get_config_section("model_parameters")
pid_params = get_config_section("pid_controller")

# Получить переменную окружения
db_host = get_env_value("DB_HOST")
telegram_token = get_env_value("TELEGRAM_BOT_TOKEN")
```

### В Docker Compose

```yaml
services:
  database:
    ports:
      - "${DB_PORT}:5432"
    environment:
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_USER=${DB_USER}
      - POSTGRES_DB=${DB_NAME}
    volumes:
      - ./config.json:/app/config.json
```

## Преимущества

1. **Разделение ответственности**:
   - `.env` - только переменные окружения
   - `config.json` - только параметры системы

2. **Безопасность**:
   - Пароли и токены в `.env` (можно добавить в `.gitignore`)
   - Параметры модели в `config.json` (можно версионировать)

3. **Гибкость**:
   - Легко менять настройки подключения через `.env`
   - Легко настраивать параметры модели через `config.json`

4. **Совместимость**:
   - Существующий код продолжает работать
   - Постепенная миграция на новую систему

## Миграция

### Шаг 1: Создать .env файл
```bash
cp env.example .env
# Отредактировать .env с вашими настройками
```

### Шаг 2: Обновить код
Заменить прямые обращения к `config.json` на использование `config_loader`:

```python
# Старый способ
with open('config.json') as f:
    config = json.load(f)
db_host = config['connection_settings']['database']['host']

# Новый способ
from utils.config_loader import get_config_section, get_env_value
db_host = get_env_value('DB_HOST')
```

### Шаг 3: Обновить Docker Compose
Добавить переменные окружения из `.env`:

```yaml
services:
  database:
    ports:
      - "${DB_PORT}:5432"
    environment:
      - POSTGRES_PASSWORD=${DB_PASSWORD}
```

## Тестирование

Запустить тест системы конфигурации:

```bash
python3 test_config_simple.py
```

## Файлы

- `utils/config_loader.py` - основная утилита загрузки конфигурации
- `test_config_simple.py` - тест системы конфигурации
- `env.example` - пример .env файла
- `config.json` - параметры модели и системы
