# Watchdog сервисы

## Описание
Сервисы мониторинга и автоматического перезапуска компонентов системы.

## Контейнеры
- **Controller Watchdog**: controller-watchdog-service
- **System Watchdog**: watchdog-system-service

## Controller Watchdog
Мониторит контроллеры и перезапускает их при необходимости.

### Переменные окружения
- `OPCUA_SERVER_URL` - URL OPC UA сервера
- `TELEGRAM_BOT_TOKEN` - токен Telegram бота

### Volumes
- `./config.json` - конфигурация системы
- `./telegram` - модули Telegram
- `telegram_data` - данные Telegram
- `/var/run/docker.sock` - Docker socket (только чтение)

## System Watchdog
Мониторит все контейнеры системы и отправляет уведомления.

### Переменные окружения
- `TELEGRAM_BOT_TOKEN` - токен Telegram бота

### Volumes
- `./telegram` - модули Telegram
- `telegram_data` - данные Telegram
- `/var/run/docker.sock` - Docker socket (только чтение)

## Функции
- Мониторинг состояния контроллеров
- Автоматический перезапуск при сбоях
- Отправка уведомлений в Telegram
- Мониторинг всех контейнеров системы

## Права доступа
Запускаются от root для доступа к Docker socket.

## Логи
```bash
docker-compose logs controller-watchdog-service
docker-compose logs watchdog-system-service
```
