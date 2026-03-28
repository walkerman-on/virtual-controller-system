"""
Универсальный PID-регулятор для управления технологическим процессом
Может работать как основной (primary) или резервный (backup) контроллер
Режим определяется переменной окружения CONTROLLER_MODE
"""

import asyncio
import logging
import os
import sys
import time
from typing import Dict, Any, Optional

from opcua import Client
from database_manager import get_db_manager, DatabaseLogger
from shared.app_config import load_app_config

# Импорт Telegram уведомлений (опционально)
TELEGRAM_AVAILABLE = False
try:
    # Добавляем путь к модулю Telegram
    telegram_path = os.path.join(os.path.dirname(__file__), '..', 'telegram')
    if os.path.exists(telegram_path):
        sys.path.append(telegram_path)
        from telegram_bot import get_telegram_notifier
        TELEGRAM_AVAILABLE = True
        print("✅ Telegram модуль загружен в контроллере")
except (ImportError, FileNotFoundError) as e:
    TELEGRAM_AVAILABLE = False
    print(f"⚠️ Telegram модуль недоступен в контроллере: {e}")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def send_telegram_notification(level: str, component: str, message: str, 
                                   additional_data: Optional[Dict] = None):
    """Отправка уведомления через Telegram"""
    if not TELEGRAM_AVAILABLE:
        return
    
    try:
        notifier = get_telegram_notifier()
        if notifier:
            await notifier.send_notification(level, component, message, additional_data)
    except Exception as e:
        logger.error(f"❌ Ошибка отправки Telegram уведомления: {e}")


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
        
        logger.info(f"🎛️ ПИД-регулятор инициализирован: Kp={kp}, Ki={ki}, Kd={kd}")

    def reset(self):
        """Сброс состояния регулятора"""
        self.previous_error = 0.0
        self.integral = 0.0
        self.previous_derivative = 0.0
        logger.info("🔄 Состояние ПИД-регулятора сброшено")
    
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
        logger.info(f"💾 Состояние ПИД-регулятора восстановлено: integral={self.integral:.3f}, prev_error={self.previous_error:.3f}")

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
        try:
            # Проверка корректности входных данных
            if setpoint is None or process_value is None:
                logger.error(f"❌ PID: Получены None значения - SP={setpoint}, PV={process_value}")
                return 50.0  # Возвращаем безопасное значение
            
            if dt <= 0:
                logger.error(f"❌ PID: Некорректный временной шаг {dt}")
                dt = 0.1  # Используем безопасное значение
            
            # Проверка на аномальные значения
            if setpoint < 0 or setpoint > 10:
                logger.warning(f"⚠️ PID: Аномальная уставка {setpoint:.3f}м")
            if process_value < 0 or process_value > 10:
                logger.warning(f"⚠️ PID: Аномальное значение процесса {process_value:.3f}м")
            
            # Расчет ошибки по ГОСТ формуле: e = action * (PV - SP)
            # action = 1 для прямого действия (клапан открывается при увеличении PV)
            action = 1
            error = action * (process_value - setpoint)
            
            # Проверка на большие ошибки
            if abs(error) > 2.0:  # Ошибка больше 2 метров
                logger.warning(f"⚠️ PID: Большая ошибка {error:.3f}м - SP={setpoint:.3f}м, PV={process_value:.3f}м")
                # Отправка предупреждения в Telegram (асинхронно)
                if TELEGRAM_AVAILABLE:
                    try:
                        loop = asyncio.get_event_loop()
                        loop.create_task(send_telegram_notification(
                            'WARNING', 'pid_controller',
                            f"Большая ошибка управления {error:.3f}м",
                            {
                                'setpoint': f"{setpoint:.3f}м",
                                'process_value': f"{process_value:.3f}м",
                                'error': f"{error:.3f}м"
                            }
                        ))
                    except Exception as e:
                        logger.debug(f"Ошибка отправки Telegram уведомления: {e}")
            
            # Пропорциональная составляющая: P = Kc * e
            P = self.kp * error
            
            # Интегральная составляющая по ГОСТ формуле: Ii = Ii-1 + ei * Δt
            self.integral += error * dt
            # Ограничение интегральной составляющей
            self.integral = max(-self.integral_limit, min(self.integral, self.integral_limit))
            I = (1.0 / self.ki) * self.integral  # I = (1/Tи) * Ii
            
            # Проверка на переполнение интегральной составляющей
            if abs(self.integral) >= self.integral_limit:
                logger.warning(f"⚠️ PID: Интегральная составляющая достигла лимита {self.integral:.3f}")
            
            # Дифференциальная составляющая
            if dt > 0:
                D = self.kd * (error - self.previous_error) / dt
            else:
                D = 0.0
            
            # Общий выходной сигнал по ГОСТ формуле: OPi = Kc*ei + (1/Tи)*Ii + ОРнач
            op_start = 50.0  # Начальное значение выхода
            output = P + I + op_start
            
            # Проверка на аномальные значения выхода
            if output < 0 or output > 100:
                logger.warning(f"⚠️ PID: Аномальный выход {output:.3f}% - P={P:.3f}, I={I:.3f}, D={D:.3f}")
            
            # Ограничение выхода
            old_output = output
            output = max(self.output_min, min(output, self.output_max))
            
            if old_output != output:
                logger.warning(f"⚠️ PID: Выход ограничен с {old_output:.3f}% до {output:.3f}%")
            
            # Сохранение состояния для следующего шага
            self.previous_error = error
            
            # Логирование критических состояний
            if abs(error) > 1.0:  # Ошибка больше 1 метра
                logger.info(f"🔍 PID: Большая ошибка {error:.3f}м - SP={setpoint:.3f}м, PV={process_value:.3f}м, OP={output:.1f}%")
            
            return output
            
        except Exception as e:
            logger.error(f"❌ PID: Критическая ошибка расчета: {e}")
            # Возвращаем безопасное значение при ошибке
            return 50.0


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
        self._pids: Dict[str, PIDController] = {}
        self.running = False
        
        # Определение режима работы из переменной окружения
        self.mode = os.getenv('CONTROLLER_MODE', 'primary').lower()
        self.is_primary = self.mode == 'primary'
        self.is_active = self.is_primary  # Основной контроллер активен по умолчанию
        
        # Получение URL сервера из переменной окружения или конфигурации
        self.server_url = os.getenv('OPCUA_SERVER_URL', 'opc.tcp://opcua-server:4840/freeopcua/server/')
        
        # Настройка логирования в зависимости от режима
        self.log_prefix = "ОСНОВНОЙ" if self.is_primary else "РЕЗЕРВНЫЙ"
        
        # Инициализация базы данных
        self.db_manager = get_db_manager()
        self.db_logger = None
        
        logger.info(f"🔗 {self.log_prefix} контроллер инициализирован, сервер: {self.server_url}")

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Загрузка конфигурации из JSON (см. config.json)."""
        try:
            config = load_app_config(config_path)
            logger.info("📋 Конфигурация загружена успешно")
            return config
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            return {}

    def _pid_loops(self) -> list:
        return [L for L in self.config.get("controller_loops", []) if L.get("type") == "pid"]

    def _primary_loop_bindings(self) -> Dict[str, Any]:
        loops = self._pid_loops()
        if not loops:
            return {"sp": "SP_level", "pv": "PV_level", "mv": "OP_valve"}
        return loops[0].get("bindings", {})

    def _opc_tags_pv_sp(self) -> set:
        tags: set = set()
        for loop in self._pid_loops():
            b = loop.get("bindings") or {}
            if b.get("sp"):
                tags.add(b["sp"])
            if b.get("pv"):
                tags.add(b["pv"])
        return tags

    def _opc_tags_mv(self) -> set:
        return {
            (loop.get("bindings") or {}).get("mv")
            for loop in self._pid_loops()
            if (loop.get("bindings") or {}).get("mv")
        }

    async def connect_to_server(self) -> bool:
        """Подключение к OPC UA серверу"""
        try:
            self.client = Client(self.server_url)
            self.client.connect()
            logger.info(f"✅ {self.log_prefix} контроллер подключился к OPC UA серверу")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения {self.log_prefix.lower()} контроллера к серверу: {e}")
            return False

    async def disconnect_from_server(self):
        """Отключение от OPC UA сервера"""
        if self.client:
            try:
                self.client.disconnect()
                logger.info(f"🔌 {self.log_prefix} контроллер отключился от OPC UA сервера")
            except Exception as e:
                logger.error(f"Ошибка отключения от сервера: {e}")

    async def get_variable_value(self, var_name: str) -> Optional[float]:
        """Получение значения переменной с сервера"""
        try:
            pv_config = self.config['opcua_variables']['process_variables']
            if var_name not in pv_config:
                logger.error(f"❌ {self.log_prefix}: Переменная {var_name} не найдена в конфигурации")
                return None
                
            node_id = pv_config[var_name]['node_id']
            var_node = self.client.get_node(node_id)
            value = var_node.get_value()
            
            # Проверка корректности полученного значения
            if value is None:
                logger.warning(f"⚠️ {self.log_prefix}: Получено None значение для {var_name}")
            elif isinstance(value, (int, float)):
                if var_name in self._opc_tags_pv_sp() and (value < 0 or value > 10):
                    logger.warning(f"⚠️ {self.log_prefix}: Аномальное значение {var_name}={value:.3f}м")
                elif var_name in self._opc_tags_mv() and (value < 0 or value > 100):
                    logger.warning(f"⚠️ {self.log_prefix}: Аномальное значение {var_name}={value:.1f}%")
            
            return value
        except Exception as e:
            logger.error(f"❌ {self.log_prefix}: Ошибка получения значения {var_name}: {e}")
            return None

    async def set_variable_value(self, var_name: str, value: float) -> bool:
        """Установка значения переменной на сервере"""
        try:
            pv_config = self.config['opcua_variables']['process_variables']
            if var_name not in pv_config:
                logger.error(f"❌ {self.log_prefix}: Переменная {var_name} не найдена в конфигурации")
                return False
            
            # Проверка корректности значения перед установкой
            if value is None:
                logger.error(f"❌ {self.log_prefix}: Попытка установить None значение для {var_name}")
                return False
            
            if isinstance(value, (int, float)):
                if var_name in self._opc_tags_pv_sp() and (value < 0 or value > 10):
                    logger.warning(f"⚠️ {self.log_prefix}: Установка аномального значения {var_name}={value:.3f}м")
                elif var_name in self._opc_tags_mv() and (value < 0 or value > 100):
                    logger.warning(f"⚠️ {self.log_prefix}: Установка аномального значения {var_name}={value:.1f}%")

                node_id = pv_config[var_name]['node_id']
                var_node = self.client.get_node(node_id)
                var_node.set_value(value)

                if var_name in self._opc_tags_mv() and abs(value - 50.0) > 30:
                    logger.info(f"🔧 {self.log_prefix}: Значительное изменение выхода {var_name} на {value:.1f}%")
                
                return True
            else:
                logger.error(f"❌ {self.log_prefix}: Некорректный тип значения для {var_name}: {type(value)}")
                return False
                
        except Exception as e:
            logger.error(f"❌ {self.log_prefix}: Ошибка установки значения {var_name}: {e}")
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

    async def save_pid_state_for_loop(self, loop: Dict[str, Any], pid: PIDController) -> None:
        """Сохранение состояния одного контура ПИД в OPC UA по привязкам ``bindings.state``."""
        stmap = (loop.get("bindings") or {}).get("state") or {}
        if not stmap:
            return
        try:
            state = pid.get_state()
            await self.set_variable_value(stmap["integral"], state["integral"])
            await self.set_variable_value(stmap["previous_error"], state["previous_error"])
            await self.set_variable_value(stmap["previous_derivative"], state["previous_derivative"])
            logger.debug("Состояние PID %s: %s", loop.get("id"), state)
        except Exception as e:
            logger.error("Ошибка сохранения состояния PID %s: %s", loop.get("id"), e)

    async def save_pid_state(self):
        """Сохранить состояние всех контуров ПИД."""
        for loop in self._pid_loops():
            lid = loop["id"]
            if lid in self._pids:
                await self.save_pid_state_for_loop(loop, self._pids[lid])

    async def restore_pid_state_for_loop(self, loop: Dict[str, Any], pid: PIDController) -> bool:
        """Восстановление состояния одного контура из OPC UA."""
        stmap = (loop.get("bindings") or {}).get("state") or {}
        if not stmap:
            return False
        try:
            integral = await self.get_variable_value(stmap["integral"])
            previous_error = await self.get_variable_value(stmap["previous_error"])
            previous_derivative = await self.get_variable_value(stmap["previous_derivative"])
            if integral is not None and previous_error is not None and previous_derivative is not None:
                pid.set_state(
                    {
                        "integral": integral,
                        "previous_error": previous_error,
                        "previous_derivative": previous_derivative,
                    }
                )
                logger.info(
                    "💾 %s контур %s: состояние PID восстановлено из OPC UA",
                    self.log_prefix,
                    loop.get("id"),
                )
                return True
            logger.info("🆕 %s контур %s: чистое состояние PID", self.log_prefix, loop.get("id"))
            return False
        except Exception as e:
            logger.error("Ошибка восстановления PID %s: %s", loop.get("id"), e)
            return False

    async def restore_pid_state(self) -> bool:
        """Восстановить все контуры ПИД из OPC."""
        ok_any = False
        for loop in self._pid_loops():
            lid = loop["id"]
            if lid in self._pids:
                if await self.restore_pid_state_for_loop(loop, self._pids[lid]):
                    ok_any = True
        return ok_any

    async def control_loop(self):
        """Основной цикл управления контроллера"""
        logger.info(f"🚀 Запуск {self.log_prefix.lower()} контроллера...")
        
        self._pids.clear()
        for loop in self._pid_loops():
            p = loop["params"]
            self._pids[loop["id"]] = PIDController(
                kp=p["kp"],
                ki=p["ki"],
                kd=p["kd"],
                output_min=p["output_min"],
                output_max=p["output_max"],
                integral_limit=p.get("integral_limit", 10.0),
                derivative_filter_time=p.get("derivative_filter_time", 0.1),
            )

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
                                
                                # Отправка критического уведомления о переключении в Telegram
                                if TELEGRAM_AVAILABLE:
                                    try:
                                        await send_telegram_notification(
                                            'CRITICAL', 'controller_failover',
                                            "ПЕРЕКЛЮЧЕНИЕ НА РЕЗЕРВНЫЙ КОНТРОЛЛЕР!",
                                            {
                                                'from_controller': 'primary',
                                                'to_controller': 'backup',
                                                'reason': 'Primary controller heartbeat timeout',
                                                'duration_seconds': f"{time.time() - other_controller_failed_time:.1f}с",
                                                'failover_delay': f"{failover_delay}с"
                                            }
                                        )
                                    except Exception as e:
                                        logger.debug(f"Ошибка отправки Telegram уведомления о переключении: {e}")
                                
                                # Сохранение события переключения в БД
                                if self.db_manager and self.db_manager.async_pool:
                                    try:
                                        await self.db_manager.save_failover_event(
                                            event_type='failover',
                                            from_controller='primary',
                                            to_controller='backup',
                                            reason='Primary controller heartbeat timeout',
                                            duration_seconds=time.time() - other_controller_failed_time
                                        )
                                    except Exception as e:
                                        logger.debug(f"Ошибка сохранения события переключения: {e}")
                                
                                self.is_active = True
                                # Восстанавливаем состояние PID из OPC UA вместо сброса
                                await self.restore_pid_state()
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
                
                # Дополнительная проверка для основного контроллера при восстановлении
                if self.is_primary and self.is_active and self._pid_loops():
                    try:
                        first = self._pid_loops()[0]
                        stmap = (first.get("bindings") or {}).get("state") or {}
                        tag_int = stmap.get("integral")
                        lid = first.get("id")
                        if tag_int and lid in self._pids:
                            current_integral = await self.get_variable_value(tag_int)
                            pid0 = self._pids[lid]
                            if current_integral is not None and pid0.integral == 0:
                                await self.restore_pid_state()
                                logger.info(
                                    "🔄 %s контроллер восстановил состояние PID после перезагрузки",
                                    self.log_prefix,
                                )
                    except Exception as e:
                        logger.debug("Ошибка проверки состояния PID: %s", e)
                
                await asyncio.sleep(update_interval)
                
            except Exception as e:
                logger.error(f"Ошибка в цикле {self.log_prefix.lower()} контроллера: {e}")
                await asyncio.sleep(1)

    async def perform_control(self):
        """Выполнение управления по всем контурам ``controller_loops`` (тип ``pid``)."""
        try:
            loops = self._pid_loops()
            if not loops:
                logger.error("❌ %s: нет контуров pid в controller_loops", self.log_prefix)
                return

            dt = self.config["system_settings"]["controller_update_interval"]

            for idx, loop in enumerate(loops):
                lid = loop["id"]
                pid = self._pids.get(lid)
                if not pid:
                    continue
                b = loop.get("bindings") or {}
                setpoint = await self.get_variable_value(b["sp"])
                process_value = await self.get_variable_value(b["pv"])
                if setpoint is None or process_value is None:
                    logger.error("❌ %s контур %s: не удалось получить SP или PV", self.log_prefix, lid)
                    continue
                if setpoint < 0 or setpoint > 10:
                    logger.error(
                        "❌ %s контур %s: некорректная уставка %.3fм",
                        self.log_prefix,
                        lid,
                        setpoint,
                    )
                    continue
                if process_value < 0 or process_value > 10:
                    logger.error(
                        "❌ %s контур %s: некорректное значение процесса %.3fм",
                        self.log_prefix,
                        lid,
                        process_value,
                    )
                    continue

                output = pid.calculate(setpoint, process_value, dt)
                if output is None or output < 0 or output > 100:
                    logger.error("❌ %s контур %s: некорректный выход регулятора", self.log_prefix, lid)
                    continue

                success = await self.set_variable_value(b["mv"], output)
                if not success:
                    logger.error("❌ %s контур %s: не удалось установить MV", self.log_prefix, lid)
                    continue

                await self.save_pid_state_for_loop(loop, pid)

                if self.db_manager and self.db_manager.async_pool:
                    try:
                        state = pid.get_state()
                        error = process_value - setpoint
                        await self.db_manager.save_pid_state(
                            controller_id=f"{self.mode}_{lid}",
                            is_active=self.is_active,
                            kp=pid.kp,
                            ki=pid.ki,
                            kd=pid.kd,
                            integral=state["integral"],
                            previous_error=state["previous_error"],
                            previous_derivative=state["previous_derivative"],
                            setpoint=setpoint,
                            process_value=process_value,
                            output=output,
                            error_value=error,
                        )
                    except Exception as ex:
                        logger.error("❌ %s: ошибка сохранения в БД (контур %s): %s", self.log_prefix, lid, ex)

                if idx == 0:
                    error = process_value - setpoint
                    if abs(error) > 1.0:
                        logger.warning("⚠️ %s: КРИТИЧЕСКАЯ ОШИБКА УПРАВЛЕНИЯ %.3fм!", self.log_prefix, error)
                        if TELEGRAM_AVAILABLE:
                            try:
                                await send_telegram_notification(
                                    "CRITICAL",
                                    "controller",
                                    f"КРИТИЧЕСКАЯ ОШИБКА УПРАВЛЕНИЯ {error:.3f}м!",
                                    {
                                        "controller_mode": self.mode,
                                        "loop_id": lid,
                                        "setpoint": f"{setpoint:.3f}м",
                                        "process_value": f"{process_value:.3f}м",
                                        "error": f"{error:.3f}м",
                                        "output": f"{output:.1f}%",
                                        "is_active": self.is_active,
                                    },
                                )
                            except Exception:
                                pass
                    elif abs(error) > 0.5:
                        logger.warning("⚠️ %s: большая ошибка управления %.3fм", self.log_prefix, error)
                        if TELEGRAM_AVAILABLE:
                            try:
                                await send_telegram_notification(
                                    "WARNING",
                                    "controller",
                                    f"Большая ошибка управления {error:.3f}м",
                                    {
                                        "controller_mode": self.mode,
                                        "loop_id": lid,
                                        "setpoint": f"{setpoint:.3f}м",
                                        "process_value": f"{process_value:.3f}м",
                                        "error": f"{error:.3f}м",
                                        "output": f"{output:.1f}%",
                                    },
                                )
                            except Exception:
                                pass

                    if output < 5:
                        logger.warning("⚠️ %s: критически низкий выход %.1f%%", self.log_prefix, output)
                        if TELEGRAM_AVAILABLE:
                            try:
                                await send_telegram_notification(
                                    "WARNING",
                                    "controller",
                                    f"Критически низкий выход контроллера {output:.1f}% - возможен застой!",
                                    {
                                        "controller_mode": self.mode,
                                        "output_percentage": f"{output:.1f}%",
                                        "setpoint": f"{setpoint:.3f}м",
                                        "process_value": f"{process_value:.3f}м",
                                    },
                                )
                            except Exception:
                                pass
                    elif output > 95:
                        logger.warning("⚠️ %s: критически высокий выход %.1f%%", self.log_prefix, output)
                        if TELEGRAM_AVAILABLE:
                            try:
                                await send_telegram_notification(
                                    "WARNING",
                                    "controller",
                                    f"Критически высокий выход контроллера {output:.1f}% - возможен перелив!",
                                    {
                                        "controller_mode": self.mode,
                                        "output_percentage": f"{output:.1f}%",
                                        "setpoint": f"{setpoint:.3f}м",
                                        "process_value": f"{process_value:.3f}м",
                                    },
                                )
                            except Exception:
                                pass

                    logger.info(
                        "🎛️ %s PID[%s]: SP=%.3fм, PV=%.3fм, Error=%.3fм, OP=%.1f%%",
                        self.log_prefix,
                        lid,
                        setpoint,
                        process_value,
                        error,
                        output,
                    )

        except Exception as e:
            logger.error("❌ %s: критическая ошибка выполнения управления: %s", self.log_prefix, e)
            try:
                logger.info("🔄 %s: сброс состояния всех ПИД", self.log_prefix)
                for pid in self._pids.values():
                    pid.reset()
                logger.info("✅ %s: ПИД сброшены", self.log_prefix)
            except Exception as recovery_error:
                logger.critical(
                    "🚨 %s: не удалось восстановить контроллер: %s",
                    self.log_prefix,
                    recovery_error,
                )

    async def monitor_only(self):
        """Мониторинг без управления (первый контур pid)."""
        try:
            b = self._primary_loop_bindings()
            sp = await self.get_variable_value(b["sp"])
            pv = await self.get_variable_value(b["pv"])
            op = await self.get_variable_value(b["mv"])
            
            if sp is not None and pv is not None and op is not None:
                # Проверка на критические состояния при мониторинге
                error = pv - sp
                if abs(error) > 1.0:
                    logger.warning(f"⚠️ {self.log_prefix} (мониторинг): КРИТИЧЕСКАЯ ОШИБКА {error:.3f}м!")
                elif abs(error) > 0.5:
                    logger.warning(f"⚠️ {self.log_prefix} (мониторинг): Большая ошибка {error:.3f}м")
                
                # Проверка критических значений клапана
                if op < 5:
                    logger.warning(f"⚠️ {self.log_prefix} (мониторинг): Критически низкий клапан {op:.1f}%")
                elif op > 95:
                    logger.warning(f"⚠️ {self.log_prefix} (мониторинг): Критически высокий клапан {op:.1f}%")
                
                logger.info(f"👁️ {self.log_prefix} (мониторинг): SP={sp:.3f}м, PV={pv:.3f}м, OP={op:.1f}%")
            else:
                logger.warning(f"⚠️ {self.log_prefix} (мониторинг): Не удалось получить все значения - SP={sp}, PV={pv}, OP={op}")
        except Exception as e:
            logger.error(f"❌ {self.log_prefix}: Ошибка мониторинга: {e}")

    async def run(self):
        """Запуск контроллера"""
        logger.info(f"🔄 Инициализация {self.log_prefix.lower()} контроллера...")
        
        # Инициализация базы данных
        try:
            await self.db_manager.init_async_pool(min_size=2, max_size=5)
            self.db_logger = DatabaseLogger(self.db_manager, f"controller-{self.mode}")
            logger.info(f"✅ {self.log_prefix} контроллер подключен к базе данных")
        except Exception as e:
            logger.warning(f"Не удалось подключиться к базе данных: {e}")
        
        # Подключение к серверу
        if not await self.connect_to_server():
            logger.error("Не удалось подключиться к OPC UA серверу")
            return
        
        try:
            self.running = True
            await self.control_loop()
        except KeyboardInterrupt:
            logger.info("🛑 Получен сигнал остановки")
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
            logger.info(f"⏹️ {self.log_prefix} контроллер остановлен")


async def main():
    """Главная функция"""
    controller = UniversalControllerClient()
    await controller.run()


if __name__ == "__main__":
    asyncio.run(main())
