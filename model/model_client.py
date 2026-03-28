"""
Модель технологического процесса для цифрового двойника
Взаимодействует с OPC UA сервером для получения управляющих воздействий
и передачи рассчитанных параметров процесса
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from opcua import Client
from database_manager import get_db_manager, DatabaseLogger
from shared.app_config import load_app_config
from simulation_runtime import ModelSimulationRuntime

# Импорт Telegram уведомлений
TELEGRAM_AVAILABLE = False
try:
    sys.path.append('/app/telegram')
    from telegram_bot import TelegramNotifier
    TELEGRAM_AVAILABLE = True
except ImportError:
    logging.warning("⚠️ Telegram модуль недоступен")

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


class ProcessModelClient:
    """Клиент модели процесса для взаимодействия с OPC UA сервером"""
    
    def __init__(self, config_path: str = "config.json"):
        """
        Инициализация клиента модели
        
        Args:
            config_path: Путь к файлу конфигурации
        """
        self.config_path = config_path
        self.config = load_app_config(config_path)
        self.client = None
        self.model = None
        self._runtime: ModelSimulationRuntime | None = None
        self.running = False
        
        # Параметры подключения
        self.server_url = os.getenv('OPCUA_SERVER_URL', 
                                  f"opc.tcp://localhost:{self.config['system_settings']['opcua_server_port']}/freeopcua/server/")
        
        # Интервал обновления модели
        self.update_interval = self.config['system_settings']['model_update_interval']
        
        # Инициализация базы данных
        self.db_manager = get_db_manager()
        self.db_logger = None
        
        # Инициализация Telegram уведомлений
        self.telegram_notifier = None
        self.init_telegram_notifications()
        
        # Состояние для предотвращения спама уведомлений
        self.notification_sent = {
            'tank_overflow': False,
            'tank_empty': False,
            'tank_high': False,
            'tank_low': False,
            'valve_stuck': False
        }
        
        # Node IDs для переменных
        self.node_ids = {}
        self._setup_node_ids()
        
    def _setup_node_ids(self):
        """Настройка Node IDs для переменных OPC UA"""
        pv_config = self.config['opcua_variables']['process_variables']
        
        for var_name, var_config in pv_config.items():
            self.node_ids[var_name] = var_config['node_id']
            
        logger.info("🔗 Node IDs настроены")

    def _plant_bindings(self) -> Dict[str, Any]:
        return self.config["model_plant"]["bindings"]

    def _tank_height(self) -> float:
        return float(self.config["model_parameters"].get("tank_height", 3.0))

    def _sp_tag_for_db(self) -> str:
        loops = self.config.get("controller_loops") or []
        if loops and isinstance(loops[0], dict):
            b = loops[0].get("bindings") or {}
            return str(b.get("sp", "SP_level"))
        return "SP_level"

    def _model_alerts(self) -> Dict[str, Any]:
        return self.config["model_alerts"]

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
            
            logger.info("✅ Telegram уведомления инициализированы в модели процесса")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Telegram: {e}")
    
    def send_notification(self, level: str, message: str, additional_data: Dict = None):
        """Отправка уведомления"""
        if not self.telegram_notifier:
            return
        
        try:
            asyncio.run(self.telegram_notifier.send_notification(
                level, "process_model", message, additional_data
            ))
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления: {e}")
    
    def check_critical_conditions(self, tank_level: float, valve_position: float,
                                 inlet_flow: float, outlet_flow: float):
        """Проверка критических условий и отправка уведомлений (пороги из ``model_alerts``)."""
        try:
            a = self._model_alerts()
            lv = a["levels"]
            vv = a["valve"]
            tx = a["texts"]
            th = self._tank_height()
            t_now = get_moscow_time().strftime("%H:%M:%S")

            if tank_level > lv["critical_high_m"]:
                if not self.notification_sent["tank_overflow"]:
                    to = tx["tank_overflow"]
                    self.send_notification(
                        "CRITICAL",
                        to["title"],
                        {
                            "Tank Level": f"{tank_level:.2f} м",
                            "Max Height": f"{th:.1f} м",
                            "Valve Position": f"{valve_position:.1f}%",
                            "Outlet Flow": f"{outlet_flow:.1f} м³/ч",
                            "Inlet Flow": f"{inlet_flow:.1f} м³/ч",
                            "Action Required": to["action"],
                            "Time": t_now,
                        },
                    )
                    self.notification_sent["tank_overflow"] = True
                    logger.critical(to["title"])

            elif tank_level < lv["critical_low_m"]:
                if not self.notification_sent["tank_empty"]:
                    te = tx["tank_empty"]
                    self.send_notification(
                        "CRITICAL",
                        te["title"],
                        {
                            "Tank Level": f"{tank_level:.2f} м",
                            "Min Safe Level": f"{lv['min_safe_level_hint_m']:.1f} м",
                            "Valve Position": f"{valve_position:.1f}%",
                            "Outlet Flow": f"{outlet_flow:.1f} м³/ч",
                            "Inlet Flow": f"{inlet_flow:.1f} м³/ч",
                            "Action Required": te["action"],
                            "Time": t_now,
                        },
                    )
                    self.notification_sent["tank_empty"] = True
                    logger.critical(te["title"])

            elif valve_position > vv["stuck_open_above_pct"]:
                if not self.notification_sent["valve_stuck"]:
                    vo = tx["valve_stuck_open"]
                    self.send_notification(
                        "CRITICAL",
                        vo["title"],
                        {
                            "Valve Position": f"{valve_position:.1f}%",
                            "Tank Level": f"{tank_level:.2f} м",
                            "Action Required": vo["action"],
                            "Time": t_now,
                        },
                    )
                    self.notification_sent["valve_stuck"] = True
                    logger.critical(vo["title"])

            elif valve_position < vv["stuck_closed_below_pct"]:
                if not self.notification_sent["valve_stuck"]:
                    vc = tx["valve_stuck_closed"]
                    self.send_notification(
                        "CRITICAL",
                        vc["title"],
                        {
                            "Valve Position": f"{valve_position:.1f}%",
                            "Tank Level": f"{tank_level:.2f} м",
                            "Action Required": vc["action"],
                            "Time": t_now,
                        },
                    )
                    self.notification_sent["valve_stuck"] = True
                    logger.critical(vc["title"])

            elif lv["warn_high_band_low_m"] < tank_level <= lv["warn_high_band_high_m"]:
                if not self.notification_sent["tank_high"]:
                    thi = tx["tank_high"]
                    self.send_notification(
                        "WARNING",
                        thi["title"],
                        {
                            "Tank Level": f"{tank_level:.2f} м",
                            "Valve Position": f"{valve_position:.1f}%",
                            "Warning Threshold": thi["warning_threshold_label"],
                            "Critical Threshold": thi["critical_threshold_label"],
                            "Time": t_now,
                        },
                    )
                    self.notification_sent["tank_high"] = True
                    logger.warning(thi["title"])

            elif lv["warn_low_band_low_m"] <= tank_level < lv["warn_low_band_high_m"]:
                if not self.notification_sent["tank_low"]:
                    tlo = tx["tank_low"]
                    self.send_notification(
                        "WARNING",
                        tlo["title"],
                        {
                            "Tank Level": f"{tank_level:.2f} м",
                            "Valve Position": f"{valve_position:.1f}%",
                            "Warning Threshold": tlo["warning_threshold_label"],
                            "Critical Threshold": tlo["critical_threshold_label"],
                            "Time": t_now,
                        },
                    )
                    self.notification_sent["tank_low"] = True
                    logger.warning(tlo["title"])

            if lv["normal_min_m"] <= tank_level <= lv["normal_max_m"]:
                self.notification_sent["tank_high"] = False
                self.notification_sent["tank_low"] = False

            if vv["normal_min_pct"] <= valve_position <= vv["normal_max_pct"]:
                self.notification_sent["valve_stuck"] = False

        except Exception as e:
            logger.error(f"❌ Ошибка проверки критических условий: {e}")
    
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
    
    def _set_variable_value(self, var_name: str, value: float) -> bool:
        """Установка значения переменной на сервере"""
        try:
            node_id = self.node_ids.get(var_name)
            if not node_id:
                logger.warning(f"⚠️ Node ID для переменной {var_name} не найден")
                return False
                
            node = self.client.get_node(node_id)
            node.set_value(value)
            logger.debug(f"📤 Установлено значение {var_name}: {value}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка установки значения {var_name}: {e}")
            return False
    
    def _initialize_model(self):
        """Инициализация модели процесса"""
        try:
            model_params = self.config["model_parameters"]
            self._runtime = ModelSimulationRuntime(self.config)
            self.model = self._runtime.plant
            b_in = self._plant_bindings()["in"]
            b_out = self._plant_bindings()["out"]

            initial_opening = self._get_variable_value(b_in["valve_opening"])
            if initial_opening is None:
                initial_opening = model_params.get("initial_valve_opening", 50.0)
                self._set_variable_value(b_in["valve_opening"], initial_opening)

            initial_level = model_params.get("initial_liquid_level", 1.5)
            self._set_variable_value(b_out["liquid_level"], initial_level)

            initial_flow = model_params.get("constant_inlet_flow", 100.0)
            self._set_variable_value(b_in["inlet_flow"], initial_flow)

            logger.info("🏭 Модель процесса инициализирована")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации модели: {e}")
            return False
    
    def _run_simulation_step(self):
        """Выполнение одного шага симуляции"""
        try:
            if not self._runtime:
                logger.error("❌ Рантайм модели не инициализирован")
                return

            b_in = self._plant_bindings()["in"]
            valve_tag = b_in["valve_opening"]
            valve_opening = self._get_variable_value(valve_tag)
            if valve_opening is None:
                logger.warning("⚠️ Не удалось получить значение %s, используем предыдущее", valve_tag)
                valve_opening = 50.0

            if valve_opening < 0 or valve_opening > 100:
                logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Некорректное значение клапана {valve_opening:.1f}%")
                valve_opening = max(0.0, min(valve_opening, 100.0))

            result = self._runtime.run_step(self._get_variable_value, self._set_variable_value)

            if result is None:
                logger.critical("🚨 КРИТИЧЕСКАЯ ОШИБКА: Модель вернула None результат!")
                return

            tank_h = self._tank_height()
            if result["liquid_level"] < 0:
                logger.critical(f"🚨 КРИТИЧЕСКАЯ ОШИБКА: Отрицательный уровень жидкости {result['liquid_level']:.3f}м!")
            elif result["liquid_level"] > tank_h:
                logger.critical("🚨 КРИТИЧЕСКАЯ ОШИБКА: Уровень жидкости превышает высоту бака!")

            if result["outlet_flow"] < 0:
                logger.error(f"❌ ОШИБКА: Отрицательный расход {result['outlet_flow']:.2f} м³/ч")

            inlet_flow = self._get_variable_value(b_in["inlet_flow"]) or 100.0
            self.check_critical_conditions(
                result["liquid_level"],
                valve_opening,
                inlet_flow,
                result["outlet_flow"],
            )

            if self.db_manager and self.db_manager.sync_connection:
                try:
                    sp_level = self._get_variable_value(self._sp_tag_for_db()) or 2.0
                    tank_pressure = result.get("tank_pressure", 0)
                    
                    # Проверка корректности данных перед сохранением
                    if sp_level < 0 or sp_level > 5:
                        logger.warning(f"⚠️ Некорректная уставка уровня {sp_level:.2f}м")
                    if inlet_flow < 0 or inlet_flow > 1000:
                        logger.warning(f"⚠️ Некорректный входной поток {inlet_flow:.1f} м³/ч")
                    
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
                    logger.error(f"❌ Ошибка сохранения данных процесса в БД: {e}")
            else:
                logger.debug("База данных недоступна для сохранения данных процесса")
            
            # Логирование состояния
            logger.info(f"⏱️ Время: {result['simulation_time']:.1f}с, "
                       f"📊 Уровень: {result['liquid_level']:.3f}м, "
                       f"🔧 Клапан: {result['valve_opening']:.1f}%, "
                       f"💧 Расход: {result['outlet_flow']:.1f}м³/ч")
            
            # Отладочная информация
            tank_pressure = result.get('tank_pressure', 0)
            atmospheric_pressure = 101325.0
            total_pressure = atmospheric_pressure + tank_pressure
            logger.debug(f"🔍 Отладка: гидростатическое_давление={tank_pressure:.1f}Па, "
                       f"полное_давление={total_pressure:.1f}Па, "
                       f"плотность={self.config['model_parameters'].get('liquid_density', 1000.0)}кг/м³")
            
            plog = self._model_alerts()["process_log"]
            level_percentage = (result["liquid_level"] / self._tank_height()) * 100
            if level_percentage > plog["fill_percent_high"]:
                logger.warning(
                    f"⚠️ КРИТИЧЕСКОЕ СОСТОЯНИЕ: Бак заполнен на {level_percentage:.1f}%!"
                )
            elif level_percentage < plog["fill_percent_low"]:
                logger.warning(
                    f"⚠️ КРИТИЧЕСКОЕ СОСТОЯНИЕ: Бак заполнен на {level_percentage:.1f}%!"
                )

            inlet_flow = self._get_variable_value(self._plant_bindings()["in"]["inlet_flow"]) or 100.0
            flow_difference = abs(result["outlet_flow"] - inlet_flow)
            diff_lim = plog["inlet_outlet_diff_warn_m3h"]
            if flow_difference > diff_lim:
                logger.warning(
                    f"⚠️ НЕСТАБИЛЬНОСТЬ: Разница потоков {flow_difference:.1f} м³/ч (порог {diff_lim:.1f})"
                )
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка выполнения шага симуляции: {e}")
            # Попытка восстановления
            try:
                logger.info("🔄 Попытка восстановления состояния модели...")
                if self.model:
                    self.model.reset()
                    logger.info("✅ Модель сброшена к начальному состоянию")
            except Exception as recovery_error:
                logger.critical(f"🚨 КРИТИЧЕСКАЯ ОШИБКА: Не удалось восстановить модель: {recovery_error}")
    
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
