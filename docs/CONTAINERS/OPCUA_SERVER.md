# OPC UA Сервер

## Описание
OPC UA сервер для предоставления данных процесса через стандартный протокол OPC UA.

## Контейнер
- **Имя**: opcua-server
- **Порт**: 4840
- **Endpoint**: opc.tcp://opcua-server:4840/freeopcua/server/

## Переменные окружения
- `DB_HOST` - хост базы данных
- `DB_PORT` - порт базы данных
- `DB_NAME` - имя базы данных
- `DB_USER` - пользователь БД
- `DB_PASSWORD` - пароль БД

## Volumes
- `./config.json` - конфигурация системы

## OPC UA Переменные
- `PV_level` - текущий уровень жидкости
- `SP_level` - уставка уровня
- `OP_valve` - управляющее воздействие
- `outlet_flow` - выходной поток
- `inlet_flow` - входной поток
- `primary_controller_status` - статус основного контроллера
- `backup_controller_status` - статус резервного контроллера
- `active_controller` - активный контроллер
- `pid_integral` - интегральная составляющая PID
- `pid_previous_error` - предыдущая ошибка PID
- `pid_previous_derivative` - предыдущая производная PID

## Подключение
```bash
# Из Python
from opcua import Client
client = Client("opc.tcp://opcua-server:4840/freeopcua/server/")
client.connect()
```

## Логи
```bash
docker-compose logs opcua-server
```
