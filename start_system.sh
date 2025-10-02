#!/bin/bash

# Скрипт для запуска системы цифрового двойника процесса
# Автор: Senior Developer
# Описание: Автоматизированный запуск всех компонентов системы

set -e

echo "=== Запуск системы цифрового двойника нефтегазового процесса ==="

# Проверка наличия Docker
if ! command -v docker &> /dev/null; then
    echo "Ошибка: Docker не установлен"
    exit 1
fi

# Проверка наличия Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "Ошибка: Docker Compose не установлен"
    exit 1
fi

# Проверка наличия config.json
if [ ! -f "config.json" ]; then
    echo "Ошибка: Файл config.json не найден"
    exit 1
fi

echo "Проверка конфигурации..."
python3 -c "import json; json.load(open('config.json'))" 2>/dev/null || {
    echo "Ошибка: Неверный формат config.json"
    exit 1
}

echo "Конфигурация корректна"

# Остановка существующих контейнеров
echo "Остановка существующих контейнеров..."
docker-compose down 2>/dev/null || true

# Сборка и запуск контейнеров
echo "Сборка и запуск контейнеров..."
docker-compose up --build -d

# Ожидание запуска сервисов
echo "Ожидание запуска сервисов..."
sleep 10

# Проверка статуса контейнеров
echo "Проверка статуса контейнеров..."
docker-compose ps

# Проверка доступности OPC UA сервера
echo "Проверка доступности OPC UA сервера..."
timeout 30 bash -c 'until nc -z localhost 4840; do sleep 1; done' && {
    echo "✓ OPC UA сервер доступен на порту 4840"
} || {
    echo "✗ OPC UA сервер недоступен"
    echo "Проверьте логи: docker-compose logs opcua-server"
}

echo ""
echo "=== Система запущена ==="
echo ""
echo "Доступные команды:"
echo "  docker-compose logs -f                    # Просмотр всех логов"
echo "  docker-compose logs -f opcua-server       # Логи OPC UA сервера"
echo "  docker-compose logs -f process-model      # Логи модели процесса"
echo "  docker-compose logs -f pid-controller     # Логи PID контроллера"
echo "  docker-compose ps                         # Статус контейнеров"
echo "  docker-compose down                       # Остановка системы"
echo ""
echo "Мониторинг системы:"
echo "  python3 monitor_client.py                 # Интерактивный мониторинг"
echo ""
echo "OPC UA подключение:"
echo "  Endpoint: opc.tcp://localhost:4840/freeopcua/server/"
echo ""

# Опциональный запуск мониторинга
if [ "$1" = "--monitor" ]; then
    echo "Запуск мониторинга..."
    python3 monitor_client.py
fi
