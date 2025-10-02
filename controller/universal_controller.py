"""
Универсальный PID-регулятор для управления технологическим процессом
Может работать как основной (primary) или резервный (backup) контроллер
Режим определяется переменной окружения CONTROLLER_MODE
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
        
        logger.info(f"ПИД-регулятор инициализирован: Kp={kp}, Ki={ki}, Kd={kd}")

    def reset(self):
        """Сброс состояния регулятора"""
        self.previous_error = 0.0
        self.integral = 0.0
        self.previous_derivative = 0.0
        logger.info("Состояние ПИД-регулятора сброшено")
    
    def get_state(self) -> Dict[str, float]:
        """Получение текущего состояния регулятора"""
        return {
            'integral': self.integral,
            'previous_error': self.previous_error,
            'previous_derivative': self.previous_derivative
        }
    
    def set_state(self, state: Dict[str, float]):
        """Установка состояния регулятора"""
        self.integral = state.get('integral', 0.0)
        self.previous_error = state.get('previous_error', 0.0)
        self.previous_derivative = state.get('previous_derivative', 0.0)
        logger.info(f"Состояние ПИД-регулятора восстановлено: integral={self.integral:.3f}, prev_error={self.previous_error:.3f}")

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
        
        return output


class UniversalControllerClient:
    """Универсальный клиент контроллера для взаимодействия с OPC UA сервером"""
    
    def __init__(self, config_path: str = '/app/config.json'):
        """
        Инициализация универсального контроллера
        
        Args:
            config_path: Путь к файлу конфигурации
        """
        self.config = self._load_config(config_path)
        self.client = None
        self.controller = None
        self.running = False
        
        # Определение режима работы из переменной окружения
        self.mode = os.getenv('CONTROLLER_MODE', 'primary').lower()
        self.is_primary = self.mode == 'primary'
        self.is_active = self.is_primary  # Основной контроллер активен по умолчанию
        
        # Получение URL сервера из переменной окружения или конфигурации
        self.server_url = os.getenv('OPCUA_SERVER_URL', 'opc.tcp://opcua-server:4840/freeopcua/server/')
        
        # Настройка логирования в зависимости от режима
        self.log_prefix = "ОСНОВНОЙ" if self.is_primary else "РЕЗЕРВНЫЙ"
        
        logger.info(f"{self.log_prefix} контроллер инициализирован, сервер: {self.server_url}")

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Загрузка конфигурации из файла"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info("Конфигурация загружена успешно")
                return config
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            return {}

    async def connect_to_server(self) -> bool:
        """Подключение к OPC UA серверу"""
        try:
            self.client = Client(self.server_url)
            self.client.connect()
            logger.info(f"✓ {self.log_prefix} контроллер подключился к OPC UA серверу")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения {self.log_prefix.lower()} контроллера к серверу: {e}")
            return False

    async def disconnect_from_server(self):
        """Отключение от OPC UA сервера"""
        if self.client:
            try:
                self.client.disconnect()
                logger.info(f"{self.log_prefix} контроллер отключился от OPC UA сервера")
            except Exception as e:
                logger.error(f"Ошибка отключения от сервера: {e}")

    async def get_variable_value(self, var_name: str) -> Optional[float]:
        """Получение значения переменной с сервера"""
        try:
            pv_config = self.config['opcua_variables']['process_variables']
            if var_name not in pv_config:
                logger.error(f"Переменная {var_name} не найдена в конфигурации")
                return None
                
            node_id = pv_config[var_name]['node_id']
            var_node = self.client.get_node(node_id)
            value = var_node.get_value()
            return value
        except Exception as e:
            logger.error(f"Ошибка получения значения {var_name}: {e}")
            return None

    async def set_variable_value(self, var_name: str, value: float) -> bool:
        """Установка значения переменной на сервере"""
        try:
            pv_config = self.config['opcua_variables']['process_variables']
            if var_name not in pv_config:
                logger.error(f"Переменная {var_name} не найдена в конфигурации")
                return False
                
            node_id = pv_config[var_name]['node_id']
            var_node = self.client.get_node(node_id)
            var_node.set_value(value)
            return True
        except Exception as e:
            logger.error(f"Ошибка установки значения {var_name}: {e}")
            return False

    async def update_controller_status(self):
        """Обновление статуса контроллера"""
        try:
            current_time = time.time()
            
            if self.is_primary:
                # Обновляем статус и heartbeat основного контроллера
                await self.set_variable_value('primary_controller_status', True)
                await self.set_variable_value('primary_controller_heartbeat', current_time)
                
                # Если основной контроллер активен, устанавливаем активный контроллер
                if self.is_active:
                    await self.set_variable_value('active_controller', 1)
            else:
                # Обновляем статус и heartbeat резервного контроллера
                await self.set_variable_value('backup_controller_status', self.is_active)
                await self.set_variable_value('backup_controller_heartbeat', current_time)
                
                # Если резервный контроллер активен, устанавливаем активный контроллер
                if self.is_active:
                    await self.set_variable_value('active_controller', 2)
            
        except Exception as e:
            logger.error(f"Ошибка обновления статуса контроллера: {e}")

    async def check_other_controller_status(self) -> bool:
        """Проверка состояния другого контроллера"""
        try:
            if self.is_primary:
                # Основной контроллер не проверяет других
                return False
            else:
                # Резервный контроллер проверяет основной
                primary_status = await self.get_variable_value('primary_controller_status')
                if primary_status is None:
                    return False
                
                primary_heartbeat = await self.get_variable_value('primary_controller_heartbeat')
                if primary_heartbeat is None:
                    return False
                
                current_time = time.time()
                heartbeat_timeout = self.config['system_settings'].get('controller_heartbeat_timeout', 5.0)
                
                # Если heartbeat слишком старый, считаем контроллер неактивным
                if current_time - primary_heartbeat > heartbeat_timeout:
                    logger.warning(f"Основной контроллер не отвечает {current_time - primary_heartbeat:.1f}с")
                    return False
                
                return bool(primary_status)
        except Exception as e:
            logger.error(f"Ошибка проверки статуса другого контроллера: {e}")
            return False

    async def save_pid_state(self):
        """Сохранение состояния PID в OPC UA"""
        if self.controller:
            try:
                state = self.controller.get_state()
                await self.set_variable_value('pid_integral', state['integral'])
                await self.set_variable_value('pid_previous_error', state['previous_error'])
                await self.set_variable_value('pid_previous_derivative', state['previous_derivative'])
                logger.debug(f"Состояние PID сохранено: {state}")
            except Exception as e:
                logger.error(f"Ошибка сохранения состояния PID: {e}")

    async def restore_pid_state(self):
        """Восстановление состояния PID из OPC UA"""
        if self.controller:
            try:
                integral = await self.get_variable_value('pid_integral')
                previous_error = await self.get_variable_value('pid_previous_error')
                previous_derivative = await self.get_variable_value('pid_previous_derivative')
                
                if integral is not None and previous_error is not None and previous_derivative is not None:
                    state = {
                        'integral': integral,
                        'previous_error': previous_error,
                        'previous_derivative': previous_derivative
                    }
                    self.controller.set_state(state)
                    logger.info(f"{self.log_prefix} контроллер восстановил состояние PID из OPC UA")
                    return True
                else:
                    logger.info(f"{self.log_prefix} контроллер начинает с чистого состояния PID")
                    return False
            except Exception as e:
                logger.error(f"Ошибка восстановления состояния PID: {e}")
                return False

    async def control_loop(self):
        """Основной цикл управления контроллера"""
        logger.info(f"🚀 Запуск {self.log_prefix.lower()} контроллера...")
        
        # Инициализация PID-регулятора
        pid_config = self.config['pid_controller']
        self.controller = PIDController(
            kp=pid_config['kp'],
            ki=pid_config['ki'],
            kd=pid_config['kd'],
            output_min=pid_config['output_min'],
            output_max=pid_config['output_max'],
            integral_limit=pid_config.get('integral_limit', 10.0),
            derivative_filter_time=pid_config.get('derivative_filter_time', 0.1)
        )
        
        # Попытка восстановить состояние PID из OPC UA
        await self.restore_pid_state()
        
        update_interval = self.config['system_settings']['controller_update_interval']
        failover_delay = self.config['system_settings'].get('controller_failover_delay', 2.0)
        
        other_controller_failed_time = None
        
        while self.running:
            try:
                # Обновляем статус текущего контроллера
                await self.update_controller_status()
                
                if not self.is_primary:
                    # Логика для резервного контроллера
                    other_controller_active = await self.check_other_controller_status()
                    
                    if not other_controller_active:
                        # Основной контроллер неактивен
                        if other_controller_failed_time is None:
                            other_controller_failed_time = time.time()
                            logger.warning("⚠️ Основной контроллер недоступен, запуск таймера переключения...")
                        
                        # Проверяем, прошло ли достаточно времени для переключения
                        if time.time() - other_controller_failed_time >= failover_delay:
                            if not self.is_active:
                                logger.critical("🚨 ПЕРЕКЛЮЧЕНИЕ НА РЕЗЕРВНЫЙ КОНТРОЛЛЕР!")
                                self.is_active = True
                                self.controller.reset()  # Сбрасываем состояние регулятора
                    else:
                        # Основной контроллер активен
                        if self.is_active:
                            logger.info("✅ Основной контроллер восстановлен, деактивация резервного")
                            self.is_active = False
                        other_controller_failed_time = None
                
                # Выполняем управление, если контроллер активен
                if self.is_active:
                    await self.perform_control()
                else:
                    # Если не активен, просто мониторим
                    await self.monitor_only()
                
                await asyncio.sleep(update_interval)
                
            except Exception as e:
                logger.error(f"Ошибка в цикле {self.log_prefix.lower()} контроллера: {e}")
                await asyncio.sleep(1)

    async def perform_control(self):
        """Выполнение управления (только когда контроллер активен)"""
        try:
            # Получение текущих значений
            setpoint = await self.get_variable_value('SP_level')
            process_value = await self.get_variable_value('PV_level')
            
            if setpoint is None or process_value is None:
                logger.error("Не удалось получить значения SP или PV")
                return
            
            # Расчет управляющего воздействия
            dt = self.config['system_settings']['controller_update_interval']
            output = self.controller.calculate(setpoint, process_value, dt)
            
            # Установка управляющего воздействия
            success = await self.set_variable_value('OP_valve', output)
            
            if success:
                # Сохранение состояния PID после успешного расчета
                await self.save_pid_state()
                
                error = process_value - setpoint
                logger.info(f"{self.log_prefix} ПИ расчет: SP={setpoint:.3f}, PV={process_value:.3f}, "
                           f"Error={error:.3f}, P={self.controller.kp * error:.3f}, "
                           f"I={(1.0 / self.controller.ki) * self.controller.integral:.3f}, "
                           f"D=0.000, OP_start=50.0, Output={output:.3f}")
                logger.info(f"{self.log_prefix} PID расчет: SP={setpoint:.3f}м, PV={process_value:.3f}м, "
                           f"Error={error:.3f}м, Output={output:.3f}")
                logger.info(f"{self.log_prefix} PID: SP={setpoint:.3f}м, PV={process_value:.3f}м, "
                           f"Error={error:.3f}м, OP={output:.1f}%")
            else:
                logger.error("Не удалось установить управляющее воздействие")
                
        except Exception as e:
            logger.error(f"Ошибка выполнения управления: {e}")

    async def monitor_only(self):
        """Мониторинг без управления"""
        try:
            sp = await self.get_variable_value('SP_level')
            pv = await self.get_variable_value('PV_level')
            op = await self.get_variable_value('OP_valve')
            
            if sp is not None and pv is not None and op is not None:
                logger.info(f"{self.log_prefix} (мониторинг): SP={sp:.3f}м, PV={pv:.3f}м, OP={op:.1f}%")
        except Exception as e:
            logger.error(f"Ошибка мониторинга: {e}")

    async def run(self):
        """Запуск контроллера"""
        logger.info(f"🔄 Инициализация {self.log_prefix.lower()} контроллера...")
        
        # Подключение к серверу
        if not await self.connect_to_server():
            logger.error("Не удалось подключиться к OPC UA серверу")
            return
        
        try:
            self.running = True
            await self.control_loop()
        except KeyboardInterrupt:
            logger.info("Получен сигнал остановки")
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
        finally:
            self.running = False
            # Обнуляем статус при остановке
            if self.is_primary:
                await self.set_variable_value('primary_controller_status', False)
            else:
                await self.set_variable_value('backup_controller_status', False)
            await self.disconnect_from_server()
            logger.info(f"{self.log_prefix} контроллер остановлен")


async def main():
    """Главная функция"""
    controller = UniversalControllerClient()
    await controller.run()


if __name__ == "__main__":
    asyncio.run(main())
