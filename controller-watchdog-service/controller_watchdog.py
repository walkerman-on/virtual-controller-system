#!/usr/bin/env python3
"""
Controller Watchdog Service
Специализированный сервис для мониторинга контроллеров и их перезагрузки
"""

import json
import logging
import os
import sys
import time
import docker
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from opcua import Client

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_moscow_time():
    """Получение текущего времени по МСК (UTC+3)"""
    moscow_tz = timezone(timedelta(hours=3))
    return datetime.now(moscow_tz)

# Импорт Telegram уведомлений
TELEGRAM_AVAILABLE = False
try:
    sys.path.append('/app/telegram')
    from telegram_bot import TelegramNotifier
    TELEGRAM_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ Telegram модуль недоступен")

class ControllerWatchdogService:
    """Сервис мониторинга контроллеров"""
    
    def __init__(self, config_path: str = "/app/config.json", 
                 opcua_url: str = "opc.tcp://opcua-server:4840/freeopcua/server/"):
        self.config_path = config_path
        self.opcua_url = opcua_url
        self.config = self._load_config()
        
        # Параметры мониторинга
        self.update_interval = self.config.get('system_settings', {}).get('watchdog_update_interval', 5.0)
        self.heartbeat_timeout = self.config.get('system_settings', {}).get('controller_heartbeat_timeout', 5.0)
        self.failover_delay = self.config.get('system_settings', {}).get('controller_failover_delay', 2.0)
        
        # OPC UA клиент
        self.opcua_client = None
        
        # Docker клиент для перезагрузки контейнеров
        self.docker_client = None
        
        # Telegram уведомления
        self.telegram_notifier = None
        
        # Состояние контроллеров
        self.controller_states = {
            'primary': {'status': 'unknown', 'last_heartbeat': 0, 'restart_count': 0},
            'backup': {'status': 'unknown', 'last_heartbeat': 0, 'restart_count': 0}
        }
        
        logger.info("🎛️ Controller Watchdog Service инициализирован")
        
    def _load_config(self) -> Dict[str, Any]:
        """Загрузка конфигурации"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info("📋 Конфигурация загружена")
                return config
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки конфигурации: {e}")
            return {}
    
    def init_docker_client(self):
        """Инициализация Docker клиента"""
        try:
            self.docker_client = docker.from_env()
            logger.info("🐳 Docker клиент инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Docker клиента: {e}")
    
    def init_telegram_notifications(self):
        """Инициализация Telegram уведомлений"""
        if not TELEGRAM_AVAILABLE:
            logger.warning("⚠️ Telegram уведомления недоступны")
            return
        
        try:
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            if not bot_token:
                logger.warning("⚠️ TELEGRAM_BOT_TOKEN не установлен")
                return
            
            self.telegram_notifier = TelegramNotifier(bot_token)
            
            # Загружаем подписчиков
            try:
                subscribers_file = '/app/data/telegram_subscribers.json'
                if os.path.exists(subscribers_file):
                    with open(subscribers_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        subscribers = data.get('subscribers', [])
                        for chat_id in subscribers:
                            self.telegram_notifier.subscribers.add(chat_id)
                        logger.info(f"📋 Загружено {len(subscribers)} подписчиков")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось загрузить подписчиков: {e}")
            
            logger.info("✅ Telegram уведомления инициализированы")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Telegram: {e}")
    
    def connect_to_opcua(self) -> bool:
        """Подключение к OPC UA серверу"""
        try:
            self.opcua_client = Client(self.opcua_url)
            self.opcua_client.connect()
            logger.info("✅ Подключение к OPC UA серверу установлено")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к OPC UA: {e}")
            return False
    
    def get_opcua_variable(self, var_name: str) -> Optional[float]:
        """Получение значения переменной OPC UA"""
        try:
            pv_config = self.config.get('opcua_variables', {}).get('process_variables', {})
            if var_name not in pv_config:
                logger.error(f"Переменная {var_name} не найдена в конфигурации")
                return None
                
            node_id = pv_config[var_name]['node_id']
            var_node = self.opcua_client.get_node(node_id)
            value = var_node.get_value()
            return value
        except Exception as e:
            logger.error(f"Ошибка получения значения {var_name}: {e}")
            return None
    
    def send_notification(self, level: str, message: str, additional_data: Dict = None):
        """Отправка уведомления"""
        if not self.telegram_notifier:
            return
        
        try:
            import asyncio
            asyncio.run(self.telegram_notifier.send_notification(
                level, "controller_watchdog", message, additional_data
            ))
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления: {e}")
    
    def restart_controller(self, controller_name: str) -> bool:
        """Перезагрузка контроллера"""
        if not self.docker_client:
            logger.error("❌ Docker клиент не инициализирован")
            return False
        
        try:
            container_name = f"pid-controller-{controller_name}"
            container = self.docker_client.containers.get(container_name)
            
            logger.info(f"🔄 Перезагружаем {controller_name} контроллер...")
            container.restart(timeout=10)
            
            # Обновляем счетчик перезагрузок
            self.controller_states[controller_name]['restart_count'] += 1
            
            # Отправляем уведомление
            self.send_notification(
                "WARNING",
                f"🔄 {controller_name.title()} контроллер перезагружен",
                {
                    "Controller": controller_name,
                    "Restart Count": self.controller_states[controller_name]['restart_count'],
                    "Time": get_moscow_time().strftime('%H:%M:%S')
                }
            )
            
            logger.info(f"✅ {controller_name} контроллер перезагружен")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка перезагрузки {controller_name} контроллера: {e}")
            self.send_notification(
                "ERROR",
                f"❌ Не удалось перезагрузить {controller_name} контроллер",
                {
                    "Controller": controller_name,
                    "Error": str(e)
                }
            )
            return False
    
    def monitor_controllers(self):
        """Мониторинг контроллеров"""
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
                self.controller_states['primary']['last_heartbeat'] = primary_heartbeat
                
            if backup_heartbeat is not None:
                backup_alive = (current_time - backup_heartbeat) < self.heartbeat_timeout
                self.controller_states['backup']['last_heartbeat'] = backup_heartbeat
            
            # Обновляем статусы
            self.controller_states['primary']['status'] = 'alive' if primary_alive else 'dead'
            self.controller_states['backup']['status'] = 'alive' if backup_alive else 'dead'
            
            logger.info(f"🎛️ Primary: {'✅ Активен' if primary_alive else '❌ Недоступен'}")
            logger.info(f"🎛️ Backup:  {'✅ Активен' if backup_alive else '❌ Недоступен'}")
            logger.info(f"✅ Активный: {'Основной' if active_controller == 1 else 'Резервный' if active_controller == 2 else 'Неизвестно'}")
            
            # Логика перезагрузки и уведомлений
            if not primary_alive and not backup_alive:
                logger.critical("🚨 КРИТИЧЕСКАЯ СИТУАЦИЯ: Оба контроллера недоступны!")
                self.send_notification(
                    "CRITICAL",
                    "🚨 КРИТИЧЕСКАЯ СИТУАЦИЯ: Оба контроллера недоступны!",
                    {
                        "Primary Status": "❌ Недоступен",
                        "Backup Status": "❌ Недоступен",
                        "Action": "Попытка перезагрузки обоих контроллеров"
                    }
                )
                
                # Перезагружаем оба контроллера
                self.restart_controller('primary')
                time.sleep(self.failover_delay)
                self.restart_controller('backup')
                
            elif not primary_alive and active_controller == 1:
                logger.warning("⚠️ Основной контроллер недоступен, но все еще активен!")
                self.send_notification(
                    "WARNING",
                    "⚠️ Основной контроллер недоступен, но все еще активен!",
                    {
                        "Primary Status": "❌ Недоступен",
                        "Backup Status": "✅ Активен" if backup_alive else "❌ Недоступен",
                        "Action": "Перезагрузка основного контроллера"
                    }
                )
                self.restart_controller('primary')
                
            elif not backup_alive and active_controller == 2:
                logger.warning("⚠️ Резервный контроллер недоступен, но все еще активен!")
                self.send_notification(
                    "WARNING",
                    "⚠️ Резервный контроллер недоступен, но все еще активен!",
                    {
                        "Primary Status": "✅ Активен" if primary_alive else "❌ Недоступен",
                        "Backup Status": "❌ Недоступен",
                        "Action": "Перезагрузка резервного контроллера"
                    }
                )
                self.restart_controller('backup')
                
            elif primary_alive and backup_alive:
                logger.debug("✅ Оба контроллера работают нормально")
                
        except Exception as e:
            logger.error(f"❌ Ошибка мониторинга контроллеров: {e}")
    
    def run_watchdog_loop(self):
        """Основной цикл работы"""
        logger.info("🚀 Запуск Controller Watchdog Service...")
        
        # Инициализация
        self.init_docker_client()
        self.init_telegram_notifications()
        
        # Подключение к OPC UA
        max_connection_attempts = 5
        connection_attempt = 0
        
        while connection_attempt < max_connection_attempts:
            if self.connect_to_opcua():
                break
            connection_attempt += 1
            logger.warning(f"Попытка подключения {connection_attempt}/{max_connection_attempts}")
            time.sleep(5)
        
        if connection_attempt >= max_connection_attempts:
            logger.critical("❌ Controller Watchdog Service не смог подключиться к OPC UA серверу. Выход.")
            return
        
        try:
            logger.info(f"🔄 Начинаем мониторинг контроллеров (интервал: {self.update_interval}с)")
            
            while True:
                self.monitor_controllers()
                time.sleep(self.update_interval)
                
        except KeyboardInterrupt:
            logger.info("🛑 Controller Watchdog Service остановлен пользователем")
        except Exception as e:
            logger.critical(f"💥 Критическая ошибка в Controller Watchdog Service: {e}")
        finally:
            if self.opcua_client:
                self.opcua_client.disconnect()
            logger.info("👋 Controller Watchdog Service завершил работу")


def main():
    """Главная функция"""
    opcua_server_url = os.getenv("OPCUA_SERVER_URL", "opc.tcp://opcua-server:4840/freeopcua/server/")
    config_path = os.getenv("CONFIG_PATH", "/app/config.json")
    
    logger.info("🎛️ Инициализация Controller Watchdog Service...")
    logger.info(f"OPC UA Server: {opcua_server_url}")
    logger.info(f"Config Path: {config_path}")
    
    try:
        watchdog = ControllerWatchdogService(config_path, opcua_server_url)
        watchdog.run_watchdog_loop()
    except Exception as e:
        logger.critical(f"💥 Критическая ошибка при запуске Controller Watchdog Service: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
