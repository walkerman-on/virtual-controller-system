"""
Модель технологического процесса для цифрового двойника
Взаимодействует с OPC UA сервером для получения управляющих воздействий
и передачи рассчитанных параметров процесса
"""

import asyncio
import json
import logging
import os
import time
from typing import Dict, Any, Optional

from opcua import Client
from process_model import ProcessModel
from database_manager import get_db_manager, DatabaseLogger

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProcessModelClient:
    """Клиент модели процесса для взаимодействия с OPC UA сервером"""
    
    def __init__(self, config_path: str = "config.json"):
        """
        Инициализация клиента модели
        
        Args:
            config_path: Путь к файлу конфигурации
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.client = None
        self.model = None
        self.running = False
        
        # Параметры подключения
        self.server_url = os.getenv('OPCUA_SERVER_URL', 
                                  f"opc.tcp://localhost:{self.config['system_settings']['opcua_server_port']}/freeopcua/server/")
        
        # Интервал обновления модели
        self.update_interval = self.config['system_settings']['model_update_interval']
        
        # Инициализация базы данных
        self.db_manager = get_db_manager()
        self.db_logger = None
        
        # Node IDs для переменных
        self.node_ids = {}
        self._setup_node_ids()
        
    def _load_config(self) -> Dict[str, Any]:
        """Загрузка конфигурации из JSON файла"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"📋 Конфигурация модели загружена из {self.config_path}")
            return config
        except FileNotFoundError:
            logger.error(f"❌ Файл конфигурации {self.config_path} не найден")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON: {e}")
            raise
    
    def _setup_node_ids(self):
        """Настройка Node IDs для переменных OPC UA"""
        pv_config = self.config['opcua_variables']['process_variables']
        
        for var_name, var_config in pv_config.items():
            self.node_ids[var_name] = var_config['node_id']
            
        logger.info("🔗 Node IDs настроены")
    
    def _connect_to_server(self) -> bool:
        """Подключение к OPC UA серверу"""
        try:
            self.client = Client(self.server_url)
            self.client.connect()
            logger.info(f"🔗 Подключение к OPC UA серверу: {self.server_url}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к серверу: {e}")
            return False
    
    def _disconnect_from_server(self):
        """Отключение от OPC UA сервера"""
        if self.client:
            try:
                self.client.disconnect()
                logger.info("🔌 Отключение от OPC UA сервера")
            except Exception as e:
                logger.error(f"❌ Ошибка отключения: {e}")
    
    def _get_variable_value(self, var_name: str) -> Optional[float]:
        """Получение значения переменной с сервера"""
        try:
            node_id = self.node_ids.get(var_name)
            if not node_id:
                logger.warning(f"⚠️ Node ID для переменной {var_name} не найден")
                return None
                
            node = self.client.get_node(node_id)
            value = node.get_value()
            logger.debug(f"📥 Получено значение {var_name}: {value}")
            return value
        except Exception as e:
            logger.error(f"❌ Ошибка получения значения {var_name}: {e}")
            return None
    
    def _set_variable_value(self, var_name: str, value: float):
        """Установка значения переменной на сервере"""
        try:
            node_id = self.node_ids.get(var_name)
            if not node_id:
                logger.warning(f"⚠️ Node ID для переменной {var_name} не найден")
                return
                
            node = self.client.get_node(node_id)
            node.set_value(value)
            logger.debug(f"📤 Установлено значение {var_name}: {value}")
        except Exception as e:
            logger.error(f"❌ Ошибка установки значения {var_name}: {e}")
    
    def _initialize_model(self):
        """Инициализация модели процесса"""
        try:
            # Создание модели с параметрами из конфигурации
            model_params = self.config['model_parameters']
            self.model = ProcessModel(model_params)
            
            # Получение начальных значений с сервера
            initial_opening = self._get_variable_value('OP_valve')
            if initial_opening is None:
                initial_opening = model_params.get('initial_valve_opening', 50.0)
                self._set_variable_value('OP_valve', initial_opening)
            
            # Установка начального уровня жидкости
            initial_level = model_params.get('initial_liquid_level', 1.5)
            self._set_variable_value('PV_level', initial_level)
            
            # Установка начального расхода
            initial_flow = model_params.get('constant_inlet_flow', 100.0)
            self._set_variable_value('inlet_flow', initial_flow)
            
            logger.info("🏭 Модель процесса инициализирована")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации модели: {e}")
            return False
    
    def _run_simulation_step(self):
        """Выполнение одного шага симуляции"""
        try:
            # Получение текущего управляющего воздействия с сервера
            valve_opening = self._get_variable_value('OP_valve')
            if valve_opening is None:
                logger.warning("⚠️ Не удалось получить значение OP_valve, используем предыдущее")
                valve_opening = 50.0
            
            # Расчет модели
            result = self.model.calculate_step(valve_opening)
            
            # Отправка результатов на сервер
            self._set_variable_value('PV_level', result['liquid_level'])
            self._set_variable_value('outlet_flow', result['outlet_flow'])
            
            # Сохранение данных в базу данных
            if self.db_manager and self.db_manager.sync_connection:
                try:
                    # Получаем дополнительные данные с сервера
                    sp_level = self._get_variable_value('SP_level') or 2.0
                    inlet_flow = self._get_variable_value('inlet_flow') or 100.0
                    tank_pressure = result.get('tank_pressure', 0)
                    
                    self.db_manager.save_process_data_sync(
                        pv_level=result['liquid_level'],
                        sp_level=sp_level,
                        op_valve=valve_opening,
                        outlet_flow=result['outlet_flow'],
                        inlet_flow=inlet_flow,
                        tank_pressure=tank_pressure,
                        valve_position=valve_opening
                    )
                except Exception as e:
                    logger.debug(f"Ошибка сохранения данных процесса в БД: {e}")
            
            # Логирование состояния
            logger.info(f"⏱️ Время: {result['simulation_time']:.1f}с, "
                       f"📊 Уровень: {result['liquid_level']:.3f}м, "
                       f"🔧 Клапан: {result['valve_opening']:.1f}%, "
                       f"💧 Расход: {result['outlet_flow']:.1f}м³/ч")
            
            # Отладочная информация
            tank_pressure = result.get('tank_pressure', 0)
            atmospheric_pressure = 101325.0
            total_pressure = atmospheric_pressure + tank_pressure
            logger.info(f"🔍 Отладка: гидростатическое_давление={tank_pressure:.1f}Па, "
                       f"полное_давление={total_pressure:.1f}Па, "
                       f"плотность={self.config.get('liquid_density', 1000.0)}кг/м³")
            
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения шага симуляции: {e}")
    
    def start_simulation(self):
        """Запуск симуляции модели"""
        logger.info("🚀 Запуск симуляции модели процесса")
        
        # Инициализация базы данных
        try:
            self.db_manager.init_sync_connection()
            self.db_logger = DatabaseLogger(self.db_manager, "process-model")
            logger.info("✅ Модель процесса подключена к базе данных")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось подключиться к базе данных: {e}")
        
        # Подключение к серверу
        if not self._connect_to_server():
            logger.error("❌ Не удалось подключиться к серверу")
            return False
        
        # Инициализация модели
        if not self._initialize_model():
            logger.error("❌ Не удалось инициализировать модель")
            self._disconnect_from_server()
            return False
        
        # Запуск основного цикла симуляции
        self.running = True
        logger.info("▶️ Симуляция запущена")
        
        try:
            while self.running:
                start_time = time.time()
                
                # Выполнение шага симуляции
                self._run_simulation_step()
                
                # Ожидание до следующего шага
                elapsed_time = time.time() - start_time
                sleep_time = max(0, self.update_interval - elapsed_time)
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
        except KeyboardInterrupt:
            logger.info("🛑 Получен сигнал остановки")
        except Exception as e:
            logger.error(f"💥 Критическая ошибка симуляции: {e}")
        finally:
            self.running = False
            self._disconnect_from_server()
            logger.info("⏹️ Симуляция остановлена")
    
    def stop_simulation(self):
        """Остановка симуляции"""
        self.running = False
        logger.info("🛑 Запрос на остановку симуляции")


def main():
    """Основная функция запуска модели"""
    logger.info("🏭 Запуск модели технологического процесса")
    
    # Создание и запуск клиента модели
    model_client = ProcessModelClient()
    
    try:
        model_client.start_simulation()
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
    finally:
        logger.info("👋 Модель процесса завершена")


if __name__ == "__main__":
    main()
