"""
PID-регулятор для управления технологическим процессом
Взаимодействует с OPC UA сервером для получения измерений и установки управляющих воздействий
"""

import asyncio
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


class PIDController:
    """Класс PID-регулятора"""
    
    def __init__(self, kp: float, ki: float, kd: float, 
                 output_min: float = 0.0, output_max: float = 100.0,
                 integral_limit: float = 10.0, derivative_filter_time: float = 0.1):
        """
        Инициализация PID-регулятора
        
        Args:
            kp: Пропорциональный коэффициент
            ki: Интегральный коэффициент
            kd: Дифференциальный коэффициент
            output_min: Минимальное выходное значение
            output_max: Максимальное выходное значение
            integral_limit: Ограничение интегральной составляющей
            derivative_filter_time: Время фильтрации производной
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_min = output_min
        self.output_max = output_max
        self.integral_limit = integral_limit
        self.derivative_filter_time = derivative_filter_time
        
        # Состояние регулятора
        self.previous_error = 0.0
        self.integral = 0.0
        self.previous_derivative = 0.0
        self.last_time = None
        
        logger.info(f"PID-регулятор инициализирован: Kp={kp}, Ki={ki}, Kd={kd}")
    
    def calculate(self, setpoint: float, process_value: float, dt: float) -> float:
        """
        Расчет выходного сигнала ПИ-регулятора по ГОСТ формулам из лекций
        
        Args:
            setpoint: Заданное значение (уставка)
            process_value: Текущее значение процесса
            dt: Временной шаг
            
        Returns:
            Выходной сигнал регулятора
        """
        # Расчет ошибки по ГОСТ формуле: e = action * (PV - SP)
        # action = 1 для прямого действия (клапан открывается при увеличении PV)
        action = 1
        error = action * (process_value - setpoint)
        
        # Пропорциональная составляющая: P = Kc * e
        P = self.kp * error
        
        # Интегральная составляющая по ГОСТ формуле: Ii = Ii-1 + ei * Δt
        self.integral += error * dt
        # Ограничение интегральной составляющей
        self.integral = max(-self.integral_limit, min(self.integral, self.integral_limit))
        I = (1.0 / self.ki) * self.integral  # I = (1/Tи) * Ii
        
        # Дифференциальная составляющая
        if dt > 0:
            D = self.kd * (error - self.previous_error) / dt
        else:
            D = 0.0
        
        # Общий выходной сигнал по ГОСТ формуле: OPi = Kc*ei + (1/Tи)*Ii + ОРнач
        op_start = 50.0  # Начальное значение выхода
        output = P + I + op_start
        
        # Ограничение выхода
        output = max(self.output_min, min(output, self.output_max))
        
        # Сохранение состояния для следующего шага
        self.previous_error = error
        
        # Подробное логирование
        logger.info(f"ПИ расчет: SP={setpoint:.3f}, PV={process_value:.3f}, "
                    f"Error={error:.3f}, P={P:.3f}, I={I:.3f}, D={D:.3f}, "
                    f"OP_start={op_start:.1f}, Output={output:.3f}")
        
        return output
    
    def reset(self):
        """Сброс состояния регулятора"""
        self.previous_error = 0.0
        self.integral = 0.0
        self.previous_derivative = 0.0
        self.last_time = None
        logger.info("Состояние PID-регулятора сброшено")
    
    def get_state(self) -> Dict[str, float]:
        """Получение текущего состояния регулятора"""
        return {
            'previous_error': self.previous_error,
            'integral': self.integral,
            'previous_derivative': self.previous_derivative,
            'kp': self.kp,
            'ki': self.ki,
            'kd': self.kd
        }


class PIDControllerClient:
    """Клиент PID-регулятора для взаимодействия с OPC UA сервером"""
    
    def __init__(self, config_path: str = "config.json"):
        """
        Инициализация клиента PID-регулятора
        
        Args:
            config_path: Путь к файлу конфигурации
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.client = None
        self.controller = None
        self.running = False
        
        # Параметры подключения
        self.server_url = os.getenv('OPCUA_SERVER_URL', 
                                  f"opc.tcp://localhost:{self.config['system_settings']['opcua_server_port']}/freeopcua/server/")
        
        # Интервал обновления контроллера
        self.update_interval = self.config['system_settings']['controller_update_interval']
        
        # Node IDs для переменных
        self.node_ids = {}
        self._setup_node_ids()
        
        # Инициализация PID-регулятора
        self._initialize_controller()
        
    def _load_config(self) -> Dict[str, Any]:
        """Загрузка конфигурации из JSON файла"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"Конфигурация контроллера загружена из {self.config_path}")
            return config
        except FileNotFoundError:
            logger.error(f"Файл конфигурации {self.config_path} не найден")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            raise
    
    def _setup_node_ids(self):
        """Настройка Node IDs для переменных OPC UA"""
        pv_config = self.config['opcua_variables']['process_variables']
        
        for var_name, var_config in pv_config.items():
            self.node_ids[var_name] = var_config['node_id']
            
        logger.info("Node IDs настроены")
    
    def _initialize_controller(self):
        """Инициализация PID-регулятора"""
        pid_config = self.config['pid_controller']
        
        self.controller = PIDController(
            kp=pid_config['kp'],
            ki=pid_config['ki'],
            kd=pid_config['kd'],
            output_min=pid_config['output_min'],
            output_max=pid_config['output_max'],
            integral_limit=pid_config['integral_limit'],
            derivative_filter_time=pid_config['derivative_filter_time']
        )
        
        logger.info("PID-регулятор инициализирован")
    
    def _connect_to_server(self) -> bool:
        """Подключение к OPC UA серверу"""
        try:
            self.client = Client(self.server_url)
            self.client.connect()
            logger.info(f"Подключение к OPC UA серверу: {self.server_url}")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к серверу: {e}")
            return False
    
    def _disconnect_from_server(self):
        """Отключение от OPC UA сервера"""
        if self.client:
            try:
                self.client.disconnect()
                logger.info("Отключение от OPC UA сервера")
            except Exception as e:
                logger.error(f"Ошибка отключения: {e}")
    
    def _get_variable_value(self, var_name: str) -> Optional[float]:
        """Получение значения переменной с сервера"""
        try:
            node_id = self.node_ids.get(var_name)
            if not node_id:
                logger.warning(f"Node ID для переменной {var_name} не найден")
                return None
                
            node = self.client.get_node(node_id)
            value = node.get_value()
            logger.debug(f"Получено значение {var_name}: {value}")
            return value
        except Exception as e:
            logger.error(f"Ошибка получения значения {var_name}: {e}")
            return None
    
    def _set_variable_value(self, var_name: str, value: float):
        """Установка значения переменной на сервере"""
        try:
            node_id = self.node_ids.get(var_name)
            if not node_id:
                logger.warning(f"Node ID для переменной {var_name} не найден")
                return
                
            node = self.client.get_node(node_id)
            node.set_value(value)
            logger.debug(f"Установлено значение {var_name}: {value}")
        except Exception as e:
            logger.error(f"Ошибка установки значения {var_name}: {e}")
    
    def _run_control_step(self):
        """Выполнение одного шага управления"""
        try:
            # Получение текущих значений с сервера
            setpoint = self._get_variable_value('SP_level')
            process_value = self._get_variable_value('PV_level')
            
            if setpoint is None or process_value is None:
                logger.warning("Не удалось получить значения SP или PV")
                return
            
            # Расчет выходного сигнала PID-регулятора
            output = self.controller.calculate(setpoint, process_value, self.update_interval)
            
            # Отладочная информация о PID расчете
            logger.info(f"PID расчет: SP={setpoint:.3f}м, PV={process_value:.3f}м, "
                       f"Error={process_value-setpoint:.3f}м, Output={output:.3f}")
            
            # Установка управляющего воздействия на сервере
            self._set_variable_value('OP_valve', output)
            
            # Логирование состояния
            logger.info(f"PID: SP={setpoint:.3f}м, PV={process_value:.3f}м, "
                       f"Error={process_value-setpoint:.3f}м, OP={output:.1f}%")
            
            # Отладочная информация о состоянии PID
            logger.debug(f"PID состояние: Kp={self.controller.kp}, Ki={self.controller.ki}, Kd={self.controller.kd}, "
                        f"Integral={self.controller.integral:.3f}, "
                        f"Previous_error={self.controller.previous_error:.3f}")
            
        except Exception as e:
            logger.error(f"Ошибка выполнения шага управления: {e}")
    
    def start_control(self):
        """Запуск управления"""
        logger.info("Запуск PID-регулятора")
        
        # Подключение к серверу
        if not self._connect_to_server():
            logger.error("Не удалось подключиться к серверу")
            return False
        
        # Запуск основного цикла управления
        self.running = True
        logger.info("PID-регулятор запущен")
        
        try:
            while self.running:
                start_time = time.time()
                
                # Выполнение шага управления
                self._run_control_step()
                
                # Ожидание до следующего шага
                elapsed_time = time.time() - start_time
                sleep_time = max(0, self.update_interval - elapsed_time)
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
        except KeyboardInterrupt:
            logger.info("Получен сигнал остановки")
        except Exception as e:
            logger.error(f"Критическая ошибка управления: {e}")
        finally:
            self.running = False
            self._disconnect_from_server()
            logger.info("PID-регулятор остановлен")
    
    def stop_control(self):
        """Остановка управления"""
        self.running = False
        logger.info("Запрос на остановку PID-регулятора")


def main():
    """Основная функция запуска PID-регулятора"""
    logger.info("Запуск PID-регулятора")
    
    # Создание и запуск клиента контроллера
    controller_client = PIDControllerClient()
    
    try:
        controller_client.start_control()
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        logger.info("PID-регулятор завершен")


if __name__ == "__main__":
    main()
