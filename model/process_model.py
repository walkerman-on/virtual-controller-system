"""
Базовые классы для моделирования технологических процессов
Шаблонная архитектура для создания различных моделей процессов
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
import math
import asyncio
import os
import sys

logger = logging.getLogger(__name__)

# Импорт Telegram уведомлений (опционально)
TELEGRAM_AVAILABLE = False
try:
    # Добавляем путь к модулю Telegram
    telegram_path = os.path.join(os.path.dirname(__file__), '..', 'telegram')
    if os.path.exists(telegram_path):
        sys.path.append(telegram_path)
        from telegram_bot import get_telegram_notifier
        TELEGRAM_AVAILABLE = True
        logger.info("✅ Telegram модуль загружен")
except (ImportError, FileNotFoundError) as e:
    TELEGRAM_AVAILABLE = False
    logger.warning(f"⚠️ Telegram модуль недоступен: {e}")


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


def send_telegram_notification_sync(level: str, component: str, message: str, 
                                   additional_data: Optional[Dict] = None):
    """Синхронная отправка уведомления через Telegram"""
    if not TELEGRAM_AVAILABLE:
        return
    
    try:
        # Проверяем, есть ли уже запущенный event loop
        try:
            loop = asyncio.get_running_loop()
            # Если есть запущенный loop, создаем задачу
            asyncio.create_task(send_telegram_notification(level, component, message, additional_data))
        except RuntimeError:
            # Если нет запущенного loop, создаем новый
            asyncio.run(send_telegram_notification(level, component, message, additional_data))
    except Exception as e:
        logger.error(f"❌ Ошибка синхронной отправки Telegram уведомления: {e}")


class ProcessComponent(ABC):
    """Базовый абстрактный класс для компонентов процесса"""
    
    def __init__(self, name: str, parameters: Dict[str, Any]):
        """
        Инициализация компонента процесса
        
        Args:
            name: Название компонента
            parameters: Параметры компонента
        """
        self.name = name
        self.parameters = parameters
        self.state = {}
        
    @abstractmethod
    def calculate(self, inputs: Dict[str, float], dt: float) -> Dict[str, float]:
        """
        Расчет выходных параметров компонента
        
        Args:
            inputs: Входные параметры
            dt: Временной шаг
            
        Returns:
            Словарь выходных параметров
        """
        pass
    
    def get_state(self) -> Dict[str, Any]:
        """Получение текущего состояния компонента"""
        return self.state.copy()
    
    def set_state(self, state: Dict[str, Any]):
        """Установка состояния компонента"""
        self.state.update(state)


class Tank(ProcessComponent):
    """Модель бака с жидкостью"""
    
    def __init__(self, name: str, parameters: Dict[str, Any]):
        """
        Инициализация модели бака
        
        Args:
            name: Название бака
            parameters: Параметры бака (высота, диаметр, плотность жидкости)
        """
        super().__init__(name, parameters)
        
        # Параметры бака
        self.height = parameters.get('tank_height', 3.0)  # м
        self.diameter = parameters.get('tank_diameter', 1.0)  # м
        self.density = parameters.get('liquid_density', 1000.0)  # кг/м³
        self.gravity = parameters.get('gravity', 9.81)  # м/с²
        
        # Расчет площади поперечного сечения
        self.cross_section_area = parameters.get('tank_cross_section_area', 
                                               3.14159 * (self.diameter / 2) ** 2)
        
        # Начальное состояние
        self.state = {
            'liquid_level': parameters.get('initial_liquid_level', 1.5),  # м
            'volume': 0.0,  # м³
            'mass': 0.0,  # кг
            'pressure': 0.0  # Па
        }
        
        self._update_derived_properties()
        
    def _update_derived_properties(self):
        """Обновление производных свойств на основе уровня жидкости"""
        level = self.state['liquid_level']
        
        # Объем жидкости
        self.state['volume'] = level * self.cross_section_area
        
        # Масса жидкости
        self.state['mass'] = self.state['volume'] * self.density
        
        # Гидростатическое давление на дне бака (как в JavaScript)
        self.state['pressure'] = self.density * self.gravity * level
        
    def calculate(self, inputs: Dict[str, float], dt: float) -> Dict[str, float]:
        """
        Расчет изменения уровня жидкости в баке
        
        Args:
            inputs: Словарь с входными потоками {'inlet_flow', 'outlet_flow'}
            dt: Временной шаг в секундах
            
        Returns:
            Словарь с выходными параметрами
        """
        try:
            inlet_flow = inputs.get('inlet_flow', 0.0)  # м³/ч
            outlet_flow = inputs.get('outlet_flow', 0.0)  # м³/ч
            
            # Проверка корректности входных данных
            if inlet_flow < 0:
                logger.warning(f"⚠️ {self.name}: Отрицательный входной поток {inlet_flow:.2f} м³/ч")
                inlet_flow = 0.0
            if outlet_flow < 0:
                logger.warning(f"⚠️ {self.name}: Отрицательный выходной поток {outlet_flow:.2f} м³/ч")
                outlet_flow = 0.0
            if dt <= 0:
                logger.error(f"❌ {self.name}: Некорректный временной шаг {dt}")
                dt = 0.1  # Используем безопасное значение по умолчанию
            
            # Проверка на аномально большие значения потоков
            max_reasonable_flow = 1000.0  # м³/ч
            if inlet_flow > max_reasonable_flow:
                logger.error(f"🚨 {self.name}: КРИТИЧЕСКИЙ ВХОДНОЙ ПОТОК {inlet_flow:.2f} м³/ч превышает разумный лимит!")
                inlet_flow = max_reasonable_flow
            if outlet_flow > max_reasonable_flow:
                logger.error(f"🚨 {self.name}: КРИТИЧЕСКИЙ ВЫХОДНОЙ ПОТОК {outlet_flow:.2f} м³/ч превышает разумный лимит!")
                outlet_flow = max_reasonable_flow
            
            # Преобразование потоков в м³/с
            inlet_flow_ms = inlet_flow / 3600.0
            outlet_flow_ms = outlet_flow / 3600.0
            
            # Расчет изменения объема
            volume_change = (inlet_flow_ms - outlet_flow_ms) * dt
            
            # Обновление уровня жидкости
            current_volume = self.state['volume']
            new_volume = current_volume + volume_change
            
            # Проверка на переполнение и опустошение
            max_volume = self.height * self.cross_section_area
            min_volume = 0.0
            
            # Критические ситуации
            if new_volume > max_volume:
                logger.critical(f"🚨 {self.name}: ПЕРЕПОЛНЕНИЕ БАКА! Объем {new_volume:.3f} м³ превышает максимальный {max_volume:.3f} м³")
                # Отправка критического уведомления в Telegram
                send_telegram_notification_sync(
                    'CRITICAL', 'tank', 
                    f"ПЕРЕПОЛНЕНИЕ БАКА! Объем {new_volume:.3f} м³ превышает максимальный {max_volume:.3f} м³",
                    {
                        'tank_name': self.name,
                        'current_volume': f"{new_volume:.3f} м³",
                        'max_volume': f"{max_volume:.3f} м³",
                        'inlet_flow': f"{inlet_flow:.1f} м³/ч",
                        'outlet_flow': f"{outlet_flow:.1f} м³/ч"
                    }
                )
                new_volume = max_volume
            elif new_volume < min_volume:
                logger.critical(f"🚨 {self.name}: ОПУСТОШЕНИЕ БАКА! Объем {new_volume:.3f} м³ ниже минимального {min_volume:.3f} м³")
                # Отправка критического уведомления в Telegram
                send_telegram_notification_sync(
                    'CRITICAL', 'tank',
                    f"ОПУСТОШЕНИЕ БАКА! Объем {new_volume:.3f} м³ ниже минимального {min_volume:.3f} м³",
                    {
                        'tank_name': self.name,
                        'current_volume': f"{new_volume:.3f} м³",
                        'min_volume': f"{min_volume:.3f} м³",
                        'inlet_flow': f"{inlet_flow:.1f} м³/ч",
                        'outlet_flow': f"{outlet_flow:.1f} м³/ч"
                    }
                )
                new_volume = min_volume
            
            # Предупреждения о приближении к критическим значениям
            volume_percentage = (new_volume / max_volume) * 100
            if volume_percentage > 90:
                logger.warning(f"⚠️ {self.name}: Бак заполнен на {volume_percentage:.1f}% - близко к переполнению!")
                # Отправка предупреждения в Telegram
                send_telegram_notification_sync(
                    'WARNING', 'tank',
                    f"Бак заполнен на {volume_percentage:.1f}% - близко к переполнению!",
                    {
                        'tank_name': self.name,
                        'fill_percentage': f"{volume_percentage:.1f}%",
                        'current_volume': f"{new_volume:.3f} м³",
                        'max_volume': f"{max_volume:.3f} м³"
                    }
                )
            elif volume_percentage < 10:
                logger.warning(f"⚠️ {self.name}: Бак заполнен на {volume_percentage:.1f}% - близко к опустошению!")
                # Отправка предупреждения в Telegram
                send_telegram_notification_sync(
                    'WARNING', 'tank',
                    f"Бак заполнен на {volume_percentage:.1f}% - близко к опустошению!",
                    {
                        'tank_name': self.name,
                        'fill_percentage': f"{volume_percentage:.1f}%",
                        'current_volume': f"{new_volume:.3f} м³",
                        'max_volume': f"{max_volume:.3f} м³"
                    }
                )
            
            # Обновление уровня
            self.state['liquid_level'] = new_volume / self.cross_section_area
            
            # Обновление производных свойств
            self._update_derived_properties()
            
            # Логирование критических значений давления
            pressure = self.state['pressure']
            if pressure > 50000:  # Па
                logger.warning(f"⚠️ {self.name}: Высокое давление {pressure:.1f} Па")
            
            return {
                'liquid_level': self.state['liquid_level'],
                'volume': self.state['volume'],
                'mass': self.state['mass'],
                'pressure': self.state['pressure']
            }
            
        except Exception as e:
            logger.error(f"❌ {self.name}: Ошибка расчета бака: {e}")
            # Возвращаем предыдущее состояние при ошибке
            return {
                'liquid_level': self.state.get('liquid_level', 0.0),
                'volume': self.state.get('volume', 0.0),
                'mass': self.state.get('mass', 0.0),
                'pressure': self.state.get('pressure', 0.0)
            }


class Valve(ProcessComponent):
    """Модель клапана"""
    
    def __init__(self, name: str, parameters: Dict[str, Any]):
        """
        Инициализация модели клапана
        
        Args:
            name: Название клапана
            parameters: Параметры клапана
        """
        super().__init__(name, parameters)
        
        # Параметры клапана
        self.max_opening = parameters.get('max_opening', 100.0)  # %
        self.min_opening = parameters.get('min_opening', 0.0)  # %
        
        # Параметры для расчета Kvs
        self.inlet_flow = parameters.get('inlet_flow', 100.0)  # м³/ч
        self.max_level = parameters.get('max_level', 3.0)  # м
        self.g = 9.81  # м/с²
        
        # Kv0 - минимальная пропускная способность (при закрытом клапане)
        self.kv0 = parameters.get('kv0', 0.01)  # Минимальный коэффициент
        
        # Kvs - максимальная пропускная способность (при полностью открытом клапане)
        # Расчет для получения расхода 160-200 м³/ч при Kv100
        # При давлении ~15500Па и плотности 1000кг/м³: Kvs = 1632
        self.kvs = 400
        
        # Начальное состояние
        self.state = {
            'opening': parameters.get('initial_opening', 50.0),  # %
            'flow_coefficient': 0.0
        }
        
        self._update_flow_coefficient()
        
    def _update_flow_coefficient(self):
        """Обновление коэффициента пропускной способности"""
        opening_ratio = self.state['opening'] / 100.0
        # Линейная характеристика клапана: Kv = Kv0 + (Kvs - Kv0) * u
        self.state['flow_coefficient'] = self.kv0 + (self.kvs - self.kv0) * opening_ratio
        
    def calculate(self, inputs: Dict[str, float], dt: float) -> Dict[str, float]:
        """
        Расчет расхода через клапан по формуле из JavaScript примера
        
        Args:
            inputs: Словарь с входными параметрами {'pressure', 'density'}
            dt: Временной шаг
            
        Returns:
            Словарь с выходными параметрами
        """
        try:
            pressure = inputs.get('pressure', 0.0)  # Па
            density = inputs.get('density', 1000.0)  # кг/м³
            
            # Проверка корректности входных данных
            if pressure < 0:
                logger.warning(f"⚠️ {self.name}: Отрицательное давление {pressure:.1f} Па")
                pressure = 0.0
            if density <= 0:
                logger.error(f"❌ {self.name}: Некорректная плотность {density:.1f} кг/м³")
                density = 1000.0  # Используем стандартную плотность воды
            
            # Проверка на аномально высокие значения
            if pressure > 200000:  # Па (2 бара)
                logger.warning(f"⚠️ {self.name}: Высокое давление {pressure:.1f} Па")
            if density > 2000:  # кг/м³
                logger.warning(f"⚠️ {self.name}: Высокая плотность {density:.1f} кг/м³")
            
            if pressure > 0 and density > 0:
                # Расчет Kv по ГОСТ формуле (линейная характеристика)
                # Kv(u) = Kv₀ + (Kv₁₀₀ - Kv₀) * u
                u = self.state['opening'] / 100.0
                kv_value = self.kv0 + (self.kvs - self.kv0) * u
                
                # Проверка корректности коэффициента Kv
                if kv_value < 0:
                    logger.error(f"❌ {self.name}: Отрицательный коэффициент Kv {kv_value:.3f}")
                    kv_value = self.kv0
                
                # Расчет расхода по ГОСТ формуле
                # Q = (Kv / (3.57 * 10^4)) * sqrt(Δp / ρ1)
                # где Δp = давление в баке (гидростатическое давление)
                pressure_density_ratio = pressure / density
                if pressure_density_ratio < 0:
                    logger.error(f"❌ {self.name}: Отрицательное отношение давления к плотности")
                    flow_rate_m3h = 0.0
                else:
                    flow_rate = (kv_value / (3.57 * 10**4)) * math.sqrt(pressure_density_ratio)
                    
                    # Преобразование в м³/ч
                    flow_rate_m3h = flow_rate * 3600.0
                    
                    # Проверка на аномально высокий расход
                    max_reasonable_flow = 500.0  # м³/ч
                    if flow_rate_m3h > max_reasonable_flow:
                        logger.warning(f"⚠️ {self.name}: Высокий расход {flow_rate_m3h:.1f} м³/ч")
                    
                    # Отладочная информация (только при высоком уровне логирования)
                    logger.debug(f"🔍 {self.name}: opening={self.state['opening']:.1f}%, "
                               f"kv_value={kv_value:.3f}, pressure={pressure:.1f}Pa, "
                               f"density={density:.1f}кг/м³, flow_rate={flow_rate_m3h:.1f}м³/ч")
            else:
                flow_rate_m3h = 0.0
                logger.debug(f"🔍 {self.name}: Нулевой расход из-за давления={pressure:.1f}Па или плотности={density:.1f}кг/м³")
                
            return {
                'flow_rate': flow_rate_m3h,
                'opening': self.state['opening'],
                'flow_coefficient': self.state['flow_coefficient']
            }
            
        except Exception as e:
            logger.error(f"❌ {self.name}: Ошибка расчета клапана: {e}")
            # Возвращаем безопасные значения при ошибке
            return {
                'flow_rate': 0.0,
                'opening': self.state.get('opening', 0.0),
                'flow_coefficient': self.state.get('flow_coefficient', 0.0)
            }
    
    def set_opening(self, opening: float):
        """Установка степени открытия клапана"""
        try:
            # Проверка корректности входного значения
            if opening < 0:
                logger.warning(f"⚠️ {self.name}: Попытка установить отрицательное открытие {opening:.1f}%")
                opening = 0.0
            elif opening > 100:
                logger.warning(f"⚠️ {self.name}: Попытка установить открытие больше 100% {opening:.1f}%")
                opening = 100.0
            
            # Ограничение значения
            old_opening = self.state['opening']
            opening = max(self.min_opening, min(opening, self.max_opening))
            
            # Логирование значительных изменений
            if abs(opening - old_opening) > 10:  # Изменение больше 10%
                logger.info(f"🔧 {self.name}: Значительное изменение открытия с {old_opening:.1f}% на {opening:.1f}%")
            
            # Критические значения открытия
            if opening < 5:
                logger.warning(f"⚠️ {self.name}: Критически низкое открытие {opening:.1f}% - возможен застой!")
                # Отправка предупреждения в Telegram
                send_telegram_notification_sync(
                    'WARNING', 'valve',
                    f"Критически низкое открытие клапана {opening:.1f}% - возможен застой!",
                    {
                        'valve_name': self.name,
                        'opening_percentage': f"{opening:.1f}%",
                        'previous_opening': f"{old_opening:.1f}%"
                    }
                )
            elif opening > 95:
                logger.warning(f"⚠️ {self.name}: Критически высокое открытие {opening:.1f}% - возможен перелив!")
                # Отправка предупреждения в Telegram
                send_telegram_notification_sync(
                    'WARNING', 'valve',
                    f"Критически высокое открытие клапана {opening:.1f}% - возможен перелив!",
                    {
                        'valve_name': self.name,
                        'opening_percentage': f"{opening:.1f}%",
                        'previous_opening': f"{old_opening:.1f}%"
                    }
                )
            
            self.state['opening'] = opening
            self._update_flow_coefficient()
            
        except Exception as e:
            logger.error(f"❌ {self.name}: Ошибка установки открытия клапана: {e}")


class ProcessModel:
    """Основная модель технологического процесса"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация модели процесса
        
        Args:
            config: Конфигурация модели
        """
        self.config = config
        self.components = {}
        self.time_step = config.get('simulation_time_step', 0.1)
        self.simulation_time = 0.0
        
        # Создание компонентов
        self._create_components()
        
        logger.info("Модель технологического процесса инициализирована")
        
    def _create_components(self):
        """Создание компонентов модели"""
        # Создание бака
        tank_params = self.config.copy()
        self.components['tank'] = Tank('MainTank', tank_params)
        
        # Создание выходного клапана
        valve_params = {
            'max_opening': 100.0,
            'min_opening': 0.0,
            'kv0': 0.01,  # Минимальный коэффициент
            'inlet_flow': self.config.get('constant_inlet_flow', 100.0),
            'max_level': self.config.get('height', 3.0),
            'initial_opening': self.config.get('initial_valve_opening', 50.0)
        }
        self.components['outlet_valve'] = Valve('OutletValve', valve_params)
        
        logger.info("Компоненты модели созданы")
        
    def calculate_step(self, valve_opening: float) -> Dict[str, float]:
        """
        Расчет одного шага моделирования
        
        Args:
            valve_opening: Степень открытия клапана (%)
            
        Returns:
            Словарь с результатами расчета
        """
        try:
            # Проверка корректности входных данных
            if valve_opening is None:
                logger.error("❌ ProcessModel: Получено None значение для valve_opening")
                valve_opening = 50.0  # Используем безопасное значение по умолчанию
            elif valve_opening < 0 or valve_opening > 100:
                logger.warning(f"⚠️ ProcessModel: Некорректное значение valve_opening {valve_opening:.1f}%")
                valve_opening = max(0.0, min(valve_opening, 100.0))
            
            # Установка степени открытия клапана
            self.components['outlet_valve'].set_opening(valve_opening)
            
            # Получение текущего состояния бака
            tank_state = self.components['tank'].get_state()
            
            # Проверка состояния бака перед расчетом
            if tank_state['liquid_level'] < 0:
                logger.error(f"❌ ProcessModel: Отрицательный уровень жидкости {tank_state['liquid_level']:.3f}м")
            elif tank_state['liquid_level'] > self.config.get('height', 3.0):
                logger.error(f"❌ ProcessModel: Уровень жидкости превышает высоту бака {tank_state['liquid_level']:.3f}м")
            
            # Расчет расхода через клапан
            valve_inputs = {
                'pressure': tank_state['pressure'],
                'density': self.config.get('liquid_density', 1000.0)
            }
            valve_outputs = self.components['outlet_valve'].calculate(valve_inputs, self.time_step)
            
            # Проверка результатов расчета клапана
            if valve_outputs['flow_rate'] < 0:
                logger.error(f"❌ ProcessModel: Отрицательный расход через клапан {valve_outputs['flow_rate']:.2f} м³/ч")
            
            # Расчет нового состояния бака
            tank_inputs = {
                'inlet_flow': self.config.get('constant_inlet_flow', 100.0),
                'outlet_flow': valve_outputs['flow_rate']
            }
            tank_outputs = self.components['tank'].calculate(tank_inputs, self.time_step)
            
            # Проверка результатов расчета бака
            if tank_outputs['liquid_level'] < 0:
                logger.critical(f"🚨 ProcessModel: КРИТИЧЕСКАЯ ОШИБКА - отрицательный уровень жидкости!")
            elif tank_outputs['liquid_level'] > self.config.get('height', 3.0) * 1.1:  # 10% запас
                logger.critical(f"🚨 ProcessModel: КРИТИЧЕСКАЯ ОШИБКА - уровень жидкости превышает высоту бака!")
            
            # Обновление времени симуляции
            self.simulation_time += self.time_step
            
            # Формирование результата
            result = {
                'simulation_time': self.simulation_time,
                'liquid_level': tank_outputs['liquid_level'],
                'tank_volume': tank_outputs['volume'],
                'tank_pressure': tank_outputs['pressure'],
                'outlet_flow': valve_outputs['flow_rate'],
                'valve_opening': valve_outputs['opening']
            }
            
            # Логирование критических состояний процесса
            level_percentage = (tank_outputs['liquid_level'] / self.config.get('height', 3.0)) * 100
            if level_percentage > 95:
                logger.warning(f"⚠️ ProcessModel: КРИТИЧЕСКИЙ УРОВЕНЬ! Заполнение бака {level_percentage:.1f}%")
            elif level_percentage < 5:
                logger.warning(f"⚠️ ProcessModel: КРИТИЧЕСКИЙ УРОВЕНЬ! Заполнение бака {level_percentage:.1f}%")
            
            # Проверка на стабильность процесса
            if abs(valve_outputs['flow_rate'] - tank_inputs['inlet_flow']) > 50:  # Разница больше 50 м³/ч
                logger.warning(f"⚠️ ProcessModel: Нестабильность процесса - разница потоков {abs(valve_outputs['flow_rate'] - tank_inputs['inlet_flow']):.1f} м³/ч")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ ProcessModel: Критическая ошибка расчета шага моделирования: {e}")
            # Возвращаем безопасные значения при ошибке
            return {
                'simulation_time': self.simulation_time,
                'liquid_level': 1.5,  # Средний уровень
                'tank_volume': 0.0,
                'tank_pressure': 0.0,
                'outlet_flow': 0.0,
                'valve_opening': valve_opening if valve_opening is not None else 50.0
            }
    
    def get_current_state(self) -> Dict[str, Any]:
        """Получение текущего состояния модели"""
        state = {
            'simulation_time': self.simulation_time,
            'components': {}
        }
        
        for name, component in self.components.items():
            state['components'][name] = component.get_state()
            
        return state
    
    def reset(self):
        """Сброс модели к начальному состоянию"""
        self.simulation_time = 0.0
        
        # Сброс компонентов
        for component in self.components.values():
            if hasattr(component, 'reset'):
                component.reset()
                
        logger.info("Модель сброшена к начальному состоянию")
