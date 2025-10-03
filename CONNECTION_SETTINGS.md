# Настройки подключения для системы цифрового двойника

## OPC UA Server
- **Host**: opcua-server (внутри Docker сети)
- **Port**: 4840
- **Endpoint**: opc.tcp://opcua-server:4840/freeopcua/server/
- **Namespace**: ProcessVariables
- **Timeout**: 10 секунд
- **Retry attempts**: 3
- **Retry delay**: 1 секунда

## PostgreSQL Database
- **Host**: database (внутри Docker сети)
- **Port**: 5432
- **Database name**: digital_twin_db
- **User**: process_user
- **Password**: process_password
- **Admin user**: postgres
- **Admin password**: postgres_password
- **Connection timeout**: 30 секунд
- **Pool min size**: 2
- **Pool max size**: 10

## Analytics API
- **Host**: analytics (внутри Docker сети)
- **Port**: 8080
- **Base URL**: http://analytics:8080
- **External URL**: http://localhost:8080
- **Timeout**: 30 секунд
- **Retry attempts**: 3

## Monitoring
- **Health check interval**: 30 секунд
- **Log rotation size**: 10MB
- **Log retention days**: 7
- **Metrics collection interval**: 60 секунд

## Внешние подключения (для клиентов)

### OPC UA Client
```
Endpoint: opc.tcp://localhost:4840/freeopcua/server/
Namespace: ProcessVariables
```

### PostgreSQL (прямое подключение)
```
Host: localhost
Port: 5432
Database: digital_twin_db
User: process_user
Password: process_password
```

### Analytics API
```
Base URL: http://localhost:8080
Health check: http://localhost:8080/health
```

## Переменные окружения Docker

### OPC UA Server
```bash
OPCUA_SERVER_URL=opc.tcp://opcua-server:4840/freeopcua/server/
```

### Database
```bash
DB_HOST=database
DB_PORT=5432
DB_NAME=digital_twin_db
DB_USER=process_user
DB_PASSWORD=process_password
```

### Analytics
```bash
ANALYTICS_PORT=8080
ANALYTICS_HOST=0.0.0.0
```

## Примеры подключения

### Python OPC UA Client
```python
from opcua import Client

client = Client("opc.tcp://localhost:4840/freeopcua/server/")
client.connect()

# Получение значения уровня
level_node = client.get_node("ns=2;i=4")
current_level = level_node.get_value()
print(f"Текущий уровень: {current_level} м")

client.disconnect()
```

### PostgreSQL подключение
```python
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="digital_twin_db",
    user="process_user",
    password="process_password"
)

cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM process_data.process_variables")
count = cursor.fetchone()[0]
print(f"Записей в базе: {count}")

conn.close()
```

### REST API запросы
```bash
# Проверка состояния
curl http://localhost:8080/health

# Последние данные
curl http://localhost:8080/api/process/latest?limit=5

# Статистика
curl http://localhost:8080/api/process/statistics?hours=1
```

## Порты системы

| Сервис | Внутренний порт | Внешний порт | Описание |
|--------|----------------|--------------|----------|
| OPC UA Server | 4840 | 4840 | OPC UA протокол |
| PostgreSQL | 5432 | 5432 | База данных |
| Analytics API | 8080 | 8080 | REST API |

## Сетевая схема

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Network                          │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │opcua-server │  │   database  │  │  analytics  │        │
│  │:4840        │  │:5432        │  │:8080        │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │process-model│  │controller-  │  │controller-  │        │
│  │             │  │  primary    │  │  backup     │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                             │
│  ┌─────────────┐                                          │
│  │  watchdog   │                                          │
│  └─────────────┘                                          │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌─────────────────┐
                    │   Host Machine   │
                    │                 │
                    │ localhost:4840   │ ← OPC UA
                    │ localhost:5432   │ ← PostgreSQL
                    │ localhost:8080   │ ← Analytics API
                    └─────────────────┘
```
