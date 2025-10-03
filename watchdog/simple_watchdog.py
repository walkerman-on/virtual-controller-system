#!/usr/bin/env python3
"""
Упрощенный Watchdog для мониторинга контроллеров через OPC UA
Не требует Docker API, работает только с OPC UA переменными
"""

import json
import logging
import os
import time
from typing import Dict, Any, Optional

from opcua import Client

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimpleWatchdog:
    """
    Упрощенный Watchdog для мониторинга контроллеров через OPC UA heartbeat
    """

    def __init__(self, server_url: str, config_path: str):
        self.server_url = server_url
        self.config_path = config_path
        self.config = self._load_config()
        self.opcua_client: Optional[Client] = None
        
        # Параметры мониторинга
        self.update_interval = self.config['system_settings'].get('watchdog_update_interval', 5.0)
        self.heartbeat_timeout = self.config['system_settings'].get('controller_heartbeat_timeout', 5.0)
        
        logger.info(f"🐕 Simple Watchdog инициализирован. Интервал: {self.update_interval}с, Timeout: {self.heartbeat_timeout}с")

    def _load_config(self) -> Dict[str, Any]:
        """Загрузка конфигурации из JSON файла"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info("📋 Конфигурация загружена")
                return config
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки конфигурации: {e}")
            return {}

    def connect_to_opcua(self) -> bool:
        """Подключение к OPC UA серверу"""
        try:
            self.opcua_client = Client(self.server_url)
            self.opcua_client.connect()
            logger.info("🔗 Simple Watchdog подключился к OPC UA серверу")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка подключения Simple Watchdog к OPC UA серверу: {e}")
            return False

    def disconnect_from_opcua(self):
        """Отключение от OPC UA сервера"""
        if self.opcua_client:
            try:
                self.opcua_client.disconnect()
                logger.info("🔌 Simple Watchdog отключился от OPC UA сервера")
            except Exception as e:
                logger.error(f"❌ Ошибка отключения от OPC UA сервера: {e}")

    def get_opcua_variable(self, var_name: str) -> Optional[float]:
        """Получение значения переменной OPC UA"""
        try:
            pv_config = self.config['opcua_variables']['process_variables']
            if var_name not in pv_config:
                logger.error(f"Переменная {var_name} не найдена в конфигурации")
                return None
                
            node_id = pv_config[var_name]['node_id']
            var_node = self.opcua_client.get_node(node_id)
            value = var_node.get_value()
            logger.debug(f"Получено {var_name} = {value}")
            return value
        except Exception as e:
            logger.error(f"Ошибка получения значения {var_name}: {e}")
            return None

    def set_opcua_variable(self, var_name: str, value: Any) -> bool:
        """Установка значения переменной OPC UA"""
        try:
            pv_config = self.config['opcua_variables']['process_variables']
            if var_name not in pv_config:
                logger.error(f"Переменная {var_name} не найдена в конфигурации")
                return False
                
            node_id = pv_config[var_name]['node_id']
            var_node = self.opcua_client.get_node(node_id)
            var_node.set_value(value)
            logger.debug(f"Установлено {var_name} = {value}")
            return True
        except Exception as e:
            logger.error(f"Ошибка установки значения {var_name}: {e}")
            return False

    def monitor_controllers(self):
        """Мониторинг контроллеров через OPC UA heartbeat"""
        try:
            current_time = time.time()
            
            # Получение heartbeat значений
            primary_heartbeat = self.get_opcua_variable('primary_controller_heartbeat')
            backup_heartbeat = self.get_opcua_variable('backup_controller_heartbeat')
            active_controller = self.get_opcua_variable('active_controller')
            
            # Определение состояния контроллеров
            primary_alive = False
            backup_alive = False
            
            if primary_heartbeat is not None:
                primary_alive = (current_time - primary_heartbeat) < self.heartbeat_timeout
                
            if backup_heartbeat is not None:
                backup_alive = (current_time - backup_heartbeat) < self.heartbeat_timeout
            
            # Обновление статусов
            self.set_opcua_variable('primary_controller_status', primary_alive)
            self.set_opcua_variable('backup_controller_status', backup_alive)
            
            # Логирование статуса
            primary_status = "✅ Активен" if primary_alive else "❌ Недоступен"
            backup_status = "✅ Активен" if backup_alive else "❌ Недоступен"
            active_name = "Основной" if active_controller == 1 else "Резервный" if active_controller == 2 else "Неизвестно"
            
            logger.info(f"🔍 Мониторинг контроллеров:")
            logger.info(f"   🎛️ Primary: {primary_status} (heartbeat: {primary_heartbeat})")
            logger.info(f"   🎛️ Backup:  {backup_status} (heartbeat: {backup_heartbeat})")
            logger.info(f"   ✅ Активный: {active_name} (ID: {active_controller})")
            
            # Критические ситуации
            if not primary_alive and not backup_alive:
                logger.critical("🚨 КРИТИЧЕСКАЯ СИТУАЦИЯ: Оба контроллера недоступны!")
            elif not primary_alive and backup_alive and active_controller == 1:
                logger.warning("⚠️ Основной контроллер недоступен, но все еще активен!")
            elif primary_alive and not backup_alive:
                logger.warning("⚠️ Резервный контроллер недоступен")
            elif primary_alive and backup_alive:
                logger.debug("✅ Оба контроллера работают нормально")
                
        except Exception as e:
            logger.error(f"❌ Ошибка мониторинга контроллеров: {e}")

    def run_watchdog_loop(self):
        """Основной цикл работы Simple Watchdog"""
        logger.info("🚀 Запуск Simple Watchdog...")
        
        # Подключение к OPC UA серверу
        max_connection_attempts = 5
        connection_attempt = 0
        
        while connection_attempt < max_connection_attempts:
            if self.connect_to_opcua():
                break
            connection_attempt += 1
            logger.warning(f"Попытка подключения {connection_attempt}/{max_connection_attempts}")
            time.sleep(5)
        
        if connection_attempt >= max_connection_attempts:
            logger.critical("❌ Simple Watchdog не смог подключиться к OPC UA серверу. Выход.")
            return

        try:
            logger.info(f"🔄 Начинаем мониторинг через OPC UA (интервал: {self.update_interval}с)")
            
            while True:
                self.monitor_controllers()
                time.sleep(self.update_interval)
                
        except KeyboardInterrupt:
            logger.info("🛑 Simple Watchdog остановлен пользователем")
        except Exception as e:
            logger.critical(f"💥 Критическая ошибка в цикле Simple Watchdog: {e}")
        finally:
            self.disconnect_from_opcua()
            logger.info("👋 Simple Watchdog завершил работу")


def main():
    """Главная функция"""
    # Получение параметров из переменных окружения
    opcua_server_url = os.getenv("OPCUA_SERVER_URL", "opc.tcp://opcua-server:4840/freeopcua/server/")
    config_path = os.getenv("CONFIG_PATH", "/app/config.json")
    
    logger.info("🐕 Инициализация Simple Watchdog...")
    logger.info(f"OPC UA Server: {opcua_server_url}")
    logger.info(f"Config Path: {config_path}")
    
    try:
        watchdog = SimpleWatchdog(opcua_server_url, config_path)
        watchdog.run_watchdog_loop()
    except Exception as e:
        logger.critical(f"💥 Критическая ошибка при запуске Simple Watchdog: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = main()
