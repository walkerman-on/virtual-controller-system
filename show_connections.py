#!/usr/bin/env python3
"""
Скрипт для получения всех URL и настроек подключения системы цифрового двойника
"""

import json
import os
import sys
from datetime import datetime

def load_config():
    """Загрузка конфигурации из config.json"""
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ Файл config.json не найден!")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка парсинга config.json: {e}")
        return None

def print_section_header(title):
    """Печать заголовка секции"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_connection_info():
    """Вывод информации о подключениях"""
    config = load_config()
    if not config:
        return
    
    print_section_header("🔗 НАСТРОЙКИ ПОДКЛЮЧЕНИЯ")
    
    # OPC UA Server
    opcua_settings = config.get('connection_settings', {}).get('opcua_server', {})
    print(f"\n📡 OPC UA Server:")
    print(f"   Host: {opcua_settings.get('host', 'opcua-server')}")
    print(f"   Port: {opcua_settings.get('port', 4840)}")
    print(f"   Endpoint: {opcua_settings.get('endpoint', 'opc.tcp://opcua-server:4840/freeopcua/server/')}")
    print(f"   Namespace: {opcua_settings.get('namespace', 'ProcessVariables')}")
    print(f"   Timeout: {opcua_settings.get('timeout', 10.0)} сек")
    
    # Database
    db_settings = config.get('connection_settings', {}).get('database', {})
    print(f"\n🗄️  PostgreSQL Database:")
    print(f"   Host: {db_settings.get('host', 'database')}")
    print(f"   Port: {db_settings.get('port', 5432)}")
    print(f"   Database: {db_settings.get('name', 'digital_twin_db')}")
    print(f"   User: {db_settings.get('user', 'process_user')}")
    print(f"   Password: {db_settings.get('password', 'process_password')}")
    print(f"   Admin User: {db_settings.get('admin_user', 'postgres')}")
    print(f"   Connection Timeout: {db_settings.get('connection_timeout', 30.0)} сек")
    
    # Analytics API
    analytics_settings = config.get('connection_settings', {}).get('analytics_api', {})
    print(f"\n📊 Analytics API:")
    print(f"   Host: {analytics_settings.get('host', 'analytics')}")
    print(f"   Port: {analytics_settings.get('port', 8080)}")
    print(f"   Internal URL: {analytics_settings.get('base_url', 'http://analytics:8080')}")
    print(f"   External URL: {analytics_settings.get('external_url', 'http://localhost:8080')}")
    print(f"   Timeout: {analytics_settings.get('timeout', 30.0)} сек")

def print_external_urls():
    """Вывод внешних URL для доступа к сервисам"""
    print_section_header("🌐 ВНЕШНИЕ URL ДЛЯ ДОСТУПА")
    
    print(f"\n📡 OPC UA Server:")
    print(f"   Endpoint: opc.tcp://localhost:4840/freeopcua/server/")
    print(f"   Namespace: ProcessVariables")
    
    print(f"\n🗄️  PostgreSQL Database:")
    print(f"   Host: localhost")
    print(f"   Port: 5432")
    print(f"   Database: digital_twin_db")
    print(f"   User: process_user")
    print(f"   Password: process_password")
    
    print(f"\n📊 Analytics API:")
    print(f"   Health Check: http://localhost:8080/health")
    print(f"   Latest Data: http://localhost:8080/api/process/latest")
    print(f"   Statistics: http://localhost:8080/api/process/statistics")
    print(f"   PID History: http://localhost:8080/api/controller/pid-history")
    print(f"   Failover Events: http://localhost:8080/api/system/failover-events")
    print(f"   Performance: http://localhost:8080/api/system/performance")
    print(f"   Configuration: http://localhost:8080/api/config/current")

def print_connection_examples():
    """Вывод примеров подключения"""
    print_section_header("💻 ПРИМЕРЫ ПОДКЛЮЧЕНИЯ")
    
    print(f"\n🐍 Python OPC UA Client:")
    print(f"""
from opcua import Client

client = Client("opc.tcp://localhost:4840/freeopcua/server/")
client.connect()

# Получение значения уровня
level_node = client.get_node("ns=2;i=4")
current_level = level_node.get_value()
print(f"Текущий уровень: {{current_level}} м")

client.disconnect()
""")
    
    print(f"\n🐍 Python PostgreSQL подключение:")
    print(f"""
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
print(f"Записей в базе: {{count}}")

conn.close()
""")
    
    print(f"\n🌐 REST API запросы:")
    print(f"""
# Проверка состояния
curl http://localhost:8080/health

# Последние данные процесса
curl http://localhost:8080/api/process/latest?limit=5

# Статистика за последний час
curl http://localhost:8080/api/process/statistics?hours=1

# История PID контроллера
curl http://localhost:8080/api/controller/pid-history?controller_id=primary&limit=10

# События переключения
curl http://localhost:8080/api/system/failover-events?limit=5

# Метрики производительности
curl http://localhost:8080/api/system/performance?hours=24

# Текущая конфигурация
curl http://localhost:8080/api/config/current
""")

def print_docker_commands():
    """Вывод Docker команд для работы с сервисами"""
    print_section_header("🐳 DOCKER КОМАНДЫ")
    
    print(f"\n📋 Основные команды:")
    print(f"   Запуск системы: docker-compose up -d")
    print(f"   Остановка системы: docker-compose down")
    print(f"   Перезапуск: docker-compose restart")
    print(f"   Просмотр логов: docker-compose logs -f")
    
    print(f"\n🔍 Подключение к контейнерам:")
    print(f"   OPC UA Server: docker exec -it opcua-server bash")
    print(f"   Database: docker exec -it digital-twin-db psql -U postgres -d digital_twin_db")
    print(f"   Model: docker exec -it process-model bash")
    print(f"   Controller Primary: docker exec -it pid-controller-primary bash")
    print(f"   Controller Backup: docker exec -it pid-controller-backup bash")
    print(f"   Analytics: docker exec -it analytics-service bash")
    
    print(f"\n📊 Мониторинг:")
    print(f"   Статус контейнеров: docker-compose ps")
    print(f"   Использование ресурсов: docker stats")
    print(f"   Логи конкретного сервиса: docker-compose logs -f <service_name>")

def print_ports_info():
    """Вывод информации о портах"""
    print_section_header("🔌 ПОРТЫ СИСТЕМЫ")
    
    ports = [
        ("OPC UA Server", 4840, "OPC UA протокол"),
        ("PostgreSQL", 5432, "База данных"),
        ("Analytics API", 8080, "REST API")
    ]
    
    print(f"\n{'Сервис':<20} {'Порт':<8} {'Описание'}")
    print(f"{'-'*50}")
    for service, port, description in ports:
        print(f"{service:<20} {port:<8} {description}")

def main():
    """Основная функция"""
    print(f"🔧 Система цифрового двойника - Настройки подключения")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    print_connection_info()
    print_external_urls()
    print_connection_examples()
    print_docker_commands()
    print_ports_info()
    
    print(f"\n{'='*60}")
    print(f"✅ Все настройки подключения выведены!")
    print(f"📁 Конфигурация: config.json")
    print(f"📁 Настройки подключения: CONNECTION_SETTINGS.md")
    print(f"📁 Docker переменные: docker.env")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
