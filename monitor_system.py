#!/usr/bin/env python3
"""
Скрипт для мониторинга системы цифрового двойника
Позволяет проверять состояние системы и получать данные через API
"""

import requests
import json
import time
from datetime import datetime
import argparse


class SystemMonitor:
    def __init__(self, base_url="http://localhost:8080"):
        self.base_url = base_url
        
    def check_health(self):
        """Проверка состояния сервиса"""
        try:
            response = requests.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def get_latest_process_data(self, limit=5):
        """Получение последних данных процесса"""
        try:
            response = requests.get(f"{self.base_url}/api/process/latest?limit={limit}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def get_process_statistics(self, hours=24):
        """Получение статистики процесса"""
        try:
            response = requests.get(f"{self.base_url}/api/process/statistics?hours={hours}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def get_pid_history(self, limit=5, controller_id="primary"):
        """Получение истории PID контроллера"""
        try:
            response = requests.get(f"{self.base_url}/api/controller/pid-history?limit={limit}&controller_id={controller_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def get_failover_events(self, limit=10):
        """Получение событий переключения"""
        try:
            response = requests.get(f"{self.base_url}/api/system/failover-events?limit={limit}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def get_performance_metrics(self, hours=24):
        """Получение метрик производительности"""
        try:
            response = requests.get(f"{self.base_url}/api/system/performance?hours={hours}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def get_current_config(self):
        """Получение текущей конфигурации"""
        try:
            response = requests.get(f"{self.base_url}/api/config/current")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def print_status(self):
        """Вывод общего статуса системы"""
        print("=" * 60)
        print(f"МОНИТОРИНГ СИСТЕМЫ ЦИФРОВОГО ДВОЙНИКА - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        # Проверка здоровья
        health = self.check_health()
        if "error" in health:
            print(f"❌ Сервис недоступен: {health['error']}")
            return
        else:
            print(f"✅ Сервис работает: {health['status']}")
            print(f"📊 База данных: {'подключена' if health['database_connected'] else 'не подключена'}")
        
        # Последние данные процесса
        print("\n📈 ПОСЛЕДНИЕ ДАННЫЕ ПРОЦЕССА:")
        process_data = self.get_latest_process_data(3)
        if "error" not in process_data and process_data.get("success"):
            for i, record in enumerate(process_data["data"][:3], 1):
                print(f"  {i}. Время: {record['timestamp'][:19]}")
                print(f"     Уровень: {record['pv_level']:.3f}м (уставка: {record['sp_level']}м)")
                print(f"     Клапан: {record['op_valve']:.1f}%")
                print(f"     Расход: вход {record['inlet_flow']:.1f}м³/ч, выход {record['outlet_flow']:.1f}м³/ч")
                print()
        
        # Статистика за час
        print("📊 СТАТИСТИКА ЗА ПОСЛЕДНИЙ ЧАС:")
        stats = self.get_process_statistics(1)
        if "error" not in stats and stats.get("success"):
            print(f"  Всего записей: {stats['total_records']}")
            print(f"  Средний уровень: {stats['level_statistics']['average']:.3f}м")
            print(f"  Диапазон уровня: {stats['level_statistics']['minimum']:.3f}м - {stats['level_statistics']['maximum']:.3f}м")
            print(f"  Среднее открытие клапана: {stats['valve_statistics']['average_opening']:.1f}%")
            print(f"  Точность поддержания уровня: {stats['level_accuracy_percentage']:.1f}%")
        
        # PID контроллер
        print("\n🎛️ PID КОНТРОЛЛЕР:")
        pid_data = self.get_pid_history(1)
        if "error" not in pid_data and pid_data.get("success") and pid_data["data"]:
            latest_pid = pid_data["data"][0]
            print(f"  Контроллер: {latest_pid['controller_id']} ({'активен' if latest_pid['is_active'] else 'неактивен'})")
            print(f"  Параметры: Kp={latest_pid['kp']}, Ki={latest_pid['ki']}, Kd={latest_pid['kd']}")
            print(f"  Ошибка: {latest_pid['error_value']:.6f}")
            print(f"  Интеграл: {latest_pid['integral']:.3f}")
            print(f"  Выход: {latest_pid['output']:.1f}%")
        
        # События переключения
        print("\n🔄 СОБЫТИЯ ПЕРЕКЛЮЧЕНИЯ:")
        failover = self.get_failover_events(5)
        if "error" not in failover and failover.get("success"):
            if failover["count"] > 0:
                for event in failover["data"]:
                    print(f"  {event['timestamp'][:19]}: {event['event_type']} ({event['from_controller']} → {event['to_controller']})")
                    print(f"    Причина: {event['reason']}")
            else:
                print("  Событий переключения не было")
        
        print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Мониторинг системы цифрового двойника")
    parser.add_argument("--url", default="http://localhost:8080", help="URL сервиса аналитики")
    parser.add_argument("--watch", action="store_true", help="Непрерывный мониторинг")
    parser.add_argument("--interval", type=int, default=10, help="Интервал обновления в секундах")
    
    args = parser.parse_args()
    
    monitor = SystemMonitor(args.url)
    
    if args.watch:
        print("Запуск непрерывного мониторинга... (Ctrl+C для остановки)")
        try:
            while True:
                monitor.print_status()
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nМониторинг остановлен")
    else:
        monitor.print_status()


if __name__ == "__main__":
    main()
