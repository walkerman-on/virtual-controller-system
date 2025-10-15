# Модель процесса

## Описание
Симуляция промышленного процесса - бак с жидкостью, входной и выходной потоки.

## Контейнер
- **Имя**: process-model
- **Файл**: process_model_client.py

## Переменные окружения
- `OPCUA_SERVER_URL` - URL OPC UA сервера
- `DB_HOST` - хост базы данных
- `DB_PORT` - порт базы данных
- `DB_NAME` - имя базы данных
- `DB_USER` - пользователь БД
- `DB_PASSWORD` - пароль БД
- `TELEGRAM_BOT_TOKEN` - токен Telegram бота

## Volumes
- `./config.json` - конфигурация системы
- `./database/database_manager.py` - менеджер БД
- `./telegram` - модули Telegram
- `telegram_data` - данные Telegram

## Параметры модели
- `tank_height` - высота бака (3.0 м)
- `tank_diameter` - диаметр бака (2.0 м)
- `liquid_density` - плотность жидкости (1000.0 кг/м³)
- `constant_inlet_flow` - постоянный входной поток (100.0 м³/ч)
- `initial_liquid_level` - начальный уровень (1.5 м)
- `initial_valve_opening` - начальное открытие клапана (50.0%)

## Физика процесса
- Уравнение баланса массы
- Гидростатическое давление
- Управление клапаном

## Логи
```bash
docker-compose logs model
```
