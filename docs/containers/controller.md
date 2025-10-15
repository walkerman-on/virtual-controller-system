# 🎛️ Controller (Primary & Backup)

## Описание
Универсальный PID-регулятор для управления технологическим процессом. Поддерживает работу в режиме основного (primary) или резервного (backup) контроллера с автоматическим переключением при отказе.

## Функции
- PID-регулирование уровня жидкости в резервуаре
- Автоматическое переключение между контроллерами
- Интеграция с OPC UA сервером
- Логирование в базу данных
- Telegram уведомления о критических ситуациях

## Режимы работы
- **Primary**: Основной контроллер (активен по умолчанию)
- **Backup**: Резервный контроллер (активируется при отказе основного)

## Конфигурация
- **OPC UA сервер**: opc.tcp://opcua-server:4840/freeopcua/server/
- **База данных**: PostgreSQL
- **Интервал обновления**: 0.1 секунды
- **Таймаут heartbeat**: 5.0 секунд
- **Задержка failover**: 2.0 секунды

## Переменные окружения
```bash
CONTROLLER_MODE=primary|backup
OPCUA_SERVER_URL=opc.tcp://opcua-server:4840/freeopcua/server/
DB_HOST=database
DB_PORT=5432
DB_NAME=digital_twin_db
DB_USER=process_user
DB_PASSWORD=process_password
TELEGRAM_BOT_TOKEN=your_bot_token
```

## PID Параметры
- **Kp**: Пропорциональный коэффициент
- **Ki**: Интегральный коэффициент  
- **Kd**: Дифференциальный коэффициент
- **Выход**: 0-100%
- **Интегральный лимит**: 10.0

## Запуск
```bash
# Основной контроллер
docker-compose up -d controller-primary

# Резервный контроллер
docker-compose up -d controller-backup

# Оба контроллера
docker-compose up -d controller-primary controller-backup
```

## Проверка состояния
```bash
# Статус контроллеров
docker-compose ps controller-primary controller-backup

# Логи основного контроллера
docker-compose logs controller-primary

# Логи резервного контроллера
docker-compose logs controller-backup
```

## Тестирование failover
```bash
# Остановка основного контроллера
docker-compose stop controller-primary

# Проверка переключения на резервный
docker-compose logs controller-backup | grep "ПЕРЕКЛЮЧЕНИЕ"

# Восстановление основного контроллера
docker-compose up -d controller-primary
```

## OPC UA Переменные
- `liquid_level` - Уровень жидкости (PV)
- `setpoint` - Уставка (SP)
- `control_output` - Выход управления (OP)
- `primary_controller_status` - Статус основного контроллера
- `backup_controller_status` - Статус резервного контроллера
- `primary_controller_heartbeat` - Heartbeat основного контроллера

## Логирование
- Все действия записываются в базу данных
- Критические события отправляются в Telegram
- Детальное логирование PID расчетов

## Мониторинг
- Health check подключения к OPC UA
- Автоматический перезапуск при сбоях
- Интеграция с watchdog сервисом
