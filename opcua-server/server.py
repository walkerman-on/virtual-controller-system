"""
OPC UA сервер для цифрового двойника нефтегазового процесса
Создает переменные для модели и контроллера на основе config.json
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from opcua import Server, ua
from shared.app_config import load_app_config

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProcessOPCUAServer:
    """OPC UA сервер для технологического процесса"""
    
    def __init__(self, config_path: str = "config.json"):
        """
        Инициализация OPC UA сервера
        
        Args:
            config_path: Путь к файлу конфигурации
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.server = None
        self.namespace = None
        self.variables = {}
        
    def _load_config(self) -> dict:
        """Загрузка конфигурации из JSON."""
        try:
            config = load_app_config(self.config_path)
            logger.info(f"📋 Конфигурация загружена из {self.config_path}")
            return config
        except FileNotFoundError:
            logger.error(f"❌ Файл конфигурации {self.config_path} не найден")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки конфигурации: {e}")
            raise
    
    def _setup_server(self):
        """Настройка OPC UA сервера"""
        # Создание сервера
        self.server = Server()
        
        # Настройка endpoint
        endpoint = f"opc.tcp://0.0.0.0:{self.config['system_settings']['opcua_server_port']}/freeopcua/server/"
        self.server.set_endpoint(endpoint)
        
        # Настройка сервера
        self.server.set_server_name("Process Digital Twin OPC UA Server")
        
        # Создание namespace
        self.namespace = self.server.register_namespace("ProcessVariables")
        
        # Создание объектов
        self._create_objects()
        
        # Создание переменных
        self._create_variables()
        
        logger.info(f"🔗 OPC UA сервер настроен на endpoint: {endpoint}")
    
    def _create_objects(self):
        """Создание объектов в адресном пространстве"""
        # Основной объект процесса
        self.process_obj = self.server.nodes.objects.add_object(
            self.namespace, "Process"
        )
        
        # Объект для переменных процесса
        self.pv_obj = self.process_obj.add_object(
            self.namespace, "ProcessVariables"
        )
        
        # Объект для контроллера
        self.controller_obj = self.process_obj.add_object(
            self.namespace, "Controller"
        )
        
        logger.info("🏗️ Объекты адресного пространства созданы")
    
    def _create_variables(self):
        """Создание переменных на основе конфигурации"""
        pv_config = self.config['opcua_variables']['process_variables']
        
        for var_name, var_config in pv_config.items():
            # Получение начального значения
            initial_value = var_config['initial_value']
            
            # Создание переменной с указанным Node ID
            node_id = var_config['node_id']
            # Парсинг Node ID (например, "ns=2;i=1001")
            if node_id.startswith("ns=") and ";i=" in node_id:
                ns_part, id_part = node_id.split(";i=")
                namespace_idx = int(ns_part.split("=")[1])
                numeric_id = int(id_part)
                node_id_obj = ua.NodeId(numeric_id, namespace_idx)
            else:
                # Fallback к автоматическому созданию
                node_id_obj = self.namespace
            
            var_node = self.pv_obj.add_variable(
                node_id_obj, var_name, initial_value
            )
            
            # Настройка свойств переменной
            var_node.set_writable()
            
            # Сохранение ссылки на переменную
            self.variables[var_name] = var_node
            
            logger.info(f"📊 Переменная {var_name} создана со значением {initial_value}")
    
    def start_server(self):
        """Запуск OPC UA сервера"""
        try:
            self._setup_server()
            
            # Запуск сервера
            self.server.start()
            logger.info("🚀 OPC UA сервер запущен")
            
            # Вывод информации о доступных переменных
            logger.info("📋 Доступные переменные:")
            for var_name, var_node in self.variables.items():
                logger.info(f"  📊 {var_name}: {var_node.get_value()}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска сервера: {e}")
            return False
    
    def stop_server(self):
        """Остановка OPC UA сервера"""
        if self.server:
            try:
                self.server.stop()
                logger.info("🛑 OPC UA сервер остановлен")
            except Exception as e:
                logger.error(f"❌ Ошибка остановки сервера: {e}")
    
    def get_variable_value(self, var_name: str):
        """Получение значения переменной"""
        if var_name in self.variables:
            return self.variables[var_name].get_value()
        else:
            logger.warning(f"⚠️ Переменная {var_name} не найдена")
            return None
    
    def set_variable_value(self, var_name: str, value):
        """Установка значения переменной"""
        if var_name in self.variables:
            self.variables[var_name].set_value(value)
            logger.debug(f"📝 Переменная {var_name} установлена в {value}")
        else:
            logger.warning(f"⚠️ Переменная {var_name} не найдена")


def main():
    """Основная функция запуска сервера"""
    logger.info("🚀 Запуск OPC UA сервера для цифрового двойника процесса")
    
    # Создание и запуск сервера
    server = ProcessOPCUAServer()
    
    try:
        if server.start_server():
            logger.info("✅ Сервер успешно запущен. Нажмите Ctrl+C для остановки")
            
            # Основной цикл
            while True:
                asyncio.sleep(1)
                
    except KeyboardInterrupt:
        logger.info("🛑 Получен сигнал остановки")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
    finally:
        server.stop_server()
        logger.info("👋 Сервер остановлен")


if __name__ == "__main__":
    main()
