#!/usr/bin/env python3
"""
System Watchdog Service
Сервис для мониторинга всех контейнеров системы и отправки уведомлений
"""

import json
import logging
import os
import sys
import time
import docker
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

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
    from telegram_notifier import SimpleTelegramNotifier
    TELEGRAM_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ Telegram модуль недоступен")

class SystemWatchdogService:
    """Сервис мониторинга системы"""
    
    def __init__(self):
        self.docker_client = None
        self.telegram_notifier = None
        
        # Список контейнеров для мониторинга (8 из 9, исключая watchdog-system-service)
        self.monitored_containers = [
            'digital-twin-db',
            'opcua-server', 
            'process-model',
            'pid-controller-primary',
            'pid-controller-backup',
            'analytics-service',
            'telegram-notification-bot',
            'controller-watchdog-service'
        ]
        
        # Состояние контейнеров
        self.container_states = {}
        for container_name in self.monitored_containers:
            self.container_states[container_name] = {
                'status': 'unknown',
                'last_seen': 0,
                'restart_count': 0,
                'alerts_sent': set(),
                'first_seen': True  # Флаг первого обнаружения
            }
        
        # Интервал мониторинга
        self.update_interval = 10.0  # 10 секунд
        
        # Отслеживание предыдущего состояния системы
        self.previous_healthy_count = 0
        self.previous_critical_containers = []
        
        logger.info("🔍 System Watchdog Service инициализирован")
    
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
            
            self.telegram_notifier = SimpleTelegramNotifier(bot_token)
            
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
    
    def send_notification(self, level: str, message: str, additional_data: Dict = None):
        """Отправка уведомления"""
        if not self.telegram_notifier:
            logger.warning("⚠️ Telegram notifier не инициализирован")
            return
        
        try:
            import asyncio
            import threading
            
            def send_async():
                try:
                    # Создаем новый event loop в отдельном потоке
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.telegram_notifier.send_notification(
                        level, "system_watchdog", message, additional_data
                    ))
                    loop.close()
                except Exception as e:
                    logger.error(f"❌ Ошибка в async отправке уведомления: {e}")
            
            # Запускаем в отдельном потоке
            thread = threading.Thread(target=send_async)
            thread.daemon = True
            thread.start()
            thread.join(timeout=5)  # Ждем максимум 5 секунд
            
            logger.info(f"📤 Уведомление отправлено: {level} - {message[:50]}...")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления: {e}")
    
    def get_container_status(self, container_name: str) -> Dict[str, Any]:
        """Получение статуса контейнера"""
        try:
            container = self.docker_client.containers.get(container_name)
            
            status = container.status
            health = container.attrs.get('State', {}).get('Health', {}).get('Status', 'unknown')
            
            return {
                'status': status,
                'health': health,
                'running': status == 'running',
                'healthy': health == 'healthy' or health == 'unknown',  # unknown считается здоровым
                'restart_count': container.attrs.get('RestartCount', 0),
                'created': container.attrs.get('Created', ''),
                'started_at': container.attrs.get('State', {}).get('StartedAt', '')
            }
        except docker.errors.NotFound:
            return {
                'status': 'not_found',
                'health': 'unknown',
                'running': False,
                'healthy': False,
                'restart_count': 0,
                'created': '',
                'started_at': ''
            }
        except Exception as e:
            logger.error(f"❌ Ошибка получения статуса контейнера {container_name}: {e}")
            return {
                'status': 'error',
                'health': 'unknown',
                'running': False,
                'healthy': False,
                'restart_count': 0,
                'created': '',
                'started_at': ''
            }
    
    def restart_container(self, container_name: str) -> bool:
        """Перезагрузка контейнера"""
        try:
            container = self.docker_client.containers.get(container_name)
            logger.info(f"🔄 Перезагружаем контейнер {container_name}...")
            container.restart(timeout=30)
            
            # Обновляем счетчик перезагрузок
            self.container_states[container_name]['restart_count'] += 1
            
            # Отправляем уведомление
            self.send_notification(
                "WARNING",
                f"🔄 Контейнер {container_name} перезагружен",
                {
                    "Container": container_name,
                    "Restart Count": self.container_states[container_name]['restart_count'],
                    "Time": get_moscow_time().strftime('%H:%M:%S')
                }
            )
            
            logger.info(f"✅ Контейнер {container_name} перезагружен")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка перезагрузки контейнера {container_name}: {e}")
            self.send_notification(
                "ERROR",
                f"❌ Не удалось перезагрузить контейнер {container_name}",
                {
                    "Container": container_name,
                    "Error": str(e)
                }
            )
            return False
    
    def monitor_containers(self):
        """Мониторинг всех контейнеров"""
        logger.info("🔍 Мониторинг контейнеров системы:")
        
        current_time = time.time()
        healthy_count = 0
        total_count = len(self.monitored_containers)
        critical_containers = []
        
        for container_name in self.monitored_containers:
            container_info = self.get_container_status(container_name)
            
            # Получаем предыдущее состояние
            previous_status = self.container_states[container_name]['status']
            
            # Обновляем состояние
            self.container_states[container_name]['status'] = container_info['status']
            self.container_states[container_name]['last_seen'] = current_time
            
            if container_info['running'] and container_info['healthy']:
                healthy_count += 1
                logger.info(f"  ✅ {container_name}: {container_info['status']} ({container_info['health']})")
                
                # Проверяем первый запуск контейнера
                if self.container_states[container_name]['first_seen']:
                    self.send_notification(
                        "INFO",
                        f"🚀 Контейнер {container_name} запущен",
                        {
                            "Container": container_name,
                            "Status": container_info['status'],
                            "Health": container_info['health'],
                            "Start Time": get_moscow_time().strftime('%H:%M:%S')
                        }
                    )
                    logger.info(f"🚀 Контейнер {container_name} запущен")
                    self.container_states[container_name]['first_seen'] = False
                
                # Проверяем восстановление контейнера
                elif previous_status in ['exited', 'not_found', 'error'] or (previous_status == 'running' and not container_info['healthy']):
                    # Контейнер восстановился
                    self.send_notification(
                        "INFO",
                        f"✅ Контейнер {container_name} восстановлен",
                        {
                            "Container": container_name,
                            "Previous Status": previous_status,
                            "Current Status": container_info['status'],
                            "Health": container_info['health'],
                            "Recovery Time": get_moscow_time().strftime('%H:%M:%S')
                        }
                    )
                    logger.info(f"✅ Контейнер {container_name} восстановлен после проблем")
                    
                    # Очищаем отправленные предупреждения при восстановлении
                    self.container_states[container_name]['alerts_sent'].clear()
                    
            else:
                critical_containers.append(container_name)
                logger.warning(f"  ❌ {container_name}: {container_info['status']} ({container_info['health']})")
                
                # Отправляем уведомления о проблемах
                if container_info['status'] == 'not_found':
                    if 'not_found' not in self.container_states[container_name]['alerts_sent']:
                        self.send_notification(
                            "CRITICAL",
                            f"🚨 КОНТЕЙНЕР {container_name} НЕ НАЙДЕН!",
                            {
                                "Container": container_name,
                                "Status": "Not Found",
                                "Action Required": "Проверить конфигурацию Docker"
                            }
                        )
                        self.container_states[container_name]['alerts_sent'].add('not_found')
                
                elif container_info['status'] == 'exited':
                    if 'exited' not in self.container_states[container_name]['alerts_sent']:
                        self.send_notification(
                            "ERROR",
                            f"❌ Контейнер {container_name} остановлен",
                            {
                                "Container": container_name,
                                "Status": "Exited",
                                "Restart Count": container_info['restart_count'],
                                "Action": "Попытка перезагрузки"
                            }
                        )
                        self.container_states[container_name]['alerts_sent'].add('exited')
                        
                        # Попытка перезагрузки
                        self.restart_container(container_name)
                
                elif container_info['status'] == 'running' and not container_info['healthy']:
                    if 'unhealthy' not in self.container_states[container_name]['alerts_sent']:
                        self.send_notification(
                            "WARNING",
                            f"⚠️ Контейнер {container_name} нездоров",
                            {
                                "Container": container_name,
                                "Status": container_info['status'],
                                "Health": container_info['health'],
                                "Action": "Мониторинг состояния"
                            }
                        )
                        self.container_states[container_name]['alerts_sent'].add('unhealthy')
                
                # Дополнительная проверка для контроллеров - если они перезапускаются
                elif container_info['status'] == 'running' and container_info['health'] == 'starting' and 'controller' in container_name:
                    if 'restarting' not in self.container_states[container_name]['alerts_sent']:
                        self.send_notification(
                            "WARNING",
                            f"🔄 Контейнер {container_name} перезапускается",
                            {
                                "Container": container_name,
                                "Status": container_info['status'],
                                "Health": container_info['health'],
                                "Action": "Автоматический перезапуск"
                            }
                        )
                        self.container_states[container_name]['alerts_sent'].add('restarting')
        
        # Общая статистика
        logger.info(f"📊 Состояние системы: {healthy_count}/{total_count} контейнеров работают (из 9, исключая watchdog-system-service)")
        
        # Проверяем изменения в общем состоянии системы
        if self.previous_healthy_count != healthy_count:
            if healthy_count > self.previous_healthy_count:
                # Система улучшилась
                self.send_notification(
                    "INFO",
                    f"📈 Состояние системы улучшилось: {healthy_count}/{total_count} контейнеров работают",
                    {
                        "Previous": f"{self.previous_healthy_count}/{total_count}",
                        "Current": f"{healthy_count}/{total_count}",
                        "Improvement": f"+{healthy_count - self.previous_healthy_count} контейнеров",
                        "Time": get_moscow_time().strftime('%H:%M:%S')
                    }
                )
            else:
                # Система ухудшилась
                self.send_notification(
                    "WARNING",
                    f"📉 Состояние системы ухудшилось: {healthy_count}/{total_count} контейнеров работают",
                    {
                        "Previous": f"{self.previous_healthy_count}/{total_count}",
                        "Current": f"{healthy_count}/{total_count}",
                        "Degradation": f"{self.previous_healthy_count - healthy_count} контейнеров",
                        "Time": get_moscow_time().strftime('%H:%M:%S')
                    }
                )
        
        # Обновляем предыдущее состояние
        self.previous_healthy_count = healthy_count
        self.previous_critical_containers = critical_containers.copy()
        
        if critical_containers:
            logger.warning(f"⚠️ Проблемные контейнеры: {', '.join(critical_containers)}")
            
            # Отправляем сводное уведомление о критических контейнерах
            if len(critical_containers) > 2:  # Если больше 2 контейнеров с проблемами
                self.send_notification(
                    "CRITICAL",
                    f"🚨 КРИТИЧЕСКОЕ СОСТОЯНИЕ СИСТЕМЫ: {len(critical_containers)} контейнеров с проблемами",
                    {
                        "Healthy Containers": f"{healthy_count}/{total_count}",
                        "Critical Containers": ", ".join(critical_containers),
                        "System Status": "Degraded"
                    }
                )
    
    def run_watchdog_loop(self):
        """Основной цикл работы"""
        logger.info("🚀 Запуск System Watchdog Service...")
        
        # Инициализация
        self.init_docker_client()
        self.init_telegram_notifications()
        
        if not self.docker_client:
            logger.critical("❌ System Watchdog Service не может работать без Docker клиента. Выход.")
            return
        
        try:
            logger.info(f"🔄 Начинаем мониторинг контейнеров (интервал: {self.update_interval}с)")
            
            while True:
                self.monitor_containers()
                time.sleep(self.update_interval)
                
        except KeyboardInterrupt:
            logger.info("🛑 System Watchdog Service остановлен пользователем")
        except Exception as e:
            logger.critical(f"💥 Критическая ошибка в System Watchdog Service: {e}")
        finally:
            logger.info("👋 System Watchdog Service завершил работу")


def main():
    """Главная функция"""
    logger.info("🔍 Инициализация System Watchdog Service...")
    
    try:
        watchdog = SystemWatchdogService()
        watchdog.run_watchdog_loop()
    except Exception as e:
        logger.critical(f"💥 Критическая ошибка при запуске System Watchdog Service: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
