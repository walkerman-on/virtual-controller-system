# PID Контроллеры

## Описание
Основной и резервный PID контроллеры для регулирования процесса.

## Контейнеры
- **Основной**: pid-controller-primary
- **Резервный**: pid-controller-backup

## Переменные окружения
- `OPCUA_SERVER_URL` - URL OPC UA сервера
- `CONTROLLER_MODE` - режим контроллера (primary/backup)
- `DB_HOST` - хост базы данных
- `DB_PORT` - порт базы данных
- `DB_NAME` - имя базы данных
- `DB_USER` - пользователь БД
- `DB_PASSWORD` - пароль БД
- `TELEGRAM_BOT_TOKEN` - токен Telegram бота

## Volumes
- `./config.json` - конфигурация системы
- `./database/database_manager.py` - менеджер БД

## PID Параметры
- `kp` - пропорциональный коэффициент (15.0)
- `ki` - интегральный коэффициент (0.1)
- `kd` - дифференциальный коэффициент (1.0)
- `setpoint` - уставка (1.6 м)
- `output_min` - минимальный выход (0.0%)
- `output_max` - максимальный выход (100.0%)

## Алгоритм работы
1. Чтение текущего уровня из OPC UA
2. Вычисление ошибки (setpoint - current_level)
3. Расчет PID выходного сигнала
4. Запись управляющего воздействия в OPC UA
5. Обновление статуса и heartbeat

## Failover
- Автоматическое переключение при отказе основного контроллера
- Время переключения: 2.0 секунды
- Heartbeat timeout: 5.0 секунд

## Логи
```bash
docker-compose logs controller-primary
docker-compose logs controller-backup
```
