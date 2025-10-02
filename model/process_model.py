"""
Базовые классы для моделирования технологических процессов
Шаблонная архитектура для создания различных моделей процессов
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
import math

logger = logging.getLogger(__name__)


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
        inlet_flow = inputs.get('inlet_flow', 0.0)  # м³/ч
        outlet_flow = inputs.get('outlet_flow', 0.0)  # м³/ч
        
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
        new_volume = max(0.0, min(new_volume, max_volume))
        
        # Обновление уровня
        self.state['liquid_level'] = new_volume / self.cross_section_area
        
        # Обновление производных свойств
        self._update_derived_properties()
        
        return {
            'liquid_level': self.state['liquid_level'],
            'volume': self.state['volume'],
            'mass': self.state['mass'],
            'pressure': self.state['pressure']
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
        pressure = inputs.get('pressure', 0.0)  # Па
        density = inputs.get('density', 1000.0)  # кг/м³
        
        if pressure > 0 and density > 0:
            # Расчет Kv по ГОСТ формуле (линейная характеристика)
            # Kv(u) = Kv₀ + (Kv₁₀₀ - Kv₀) * u
            u = self.state['opening'] / 100.0
            kv_value = self.kv0 + (self.kvs - self.kv0) * u
            
            # Расчет расхода по ГОСТ формуле
            # Q = (Kv / (3.57 * 10^4)) * sqrt(Δp / ρ1)
            # где Δp = давление в баке (гидростатическое давление)
            flow_rate = (kv_value / (3.57 * 10**4)) * (pressure / density) ** 0.5
            
            # Преобразование в м³/ч
            flow_rate_m3h = flow_rate * 3600.0
            
            # Отладочная информация
            logger.info(f"DEBUG: opening={self.state['opening']:.1f}%, "
                       f"kv0={self.kv0:.3f}, kvs={self.kvs:.3f}, kv_value={kv_value:.3f}, "
                       f"pressure={pressure:.1f}Pa, density={density:.1f}кг/м³, "
                       f"pressure_density_ratio={pressure/density:.6f}, "
                       f"sqrt_ratio={math.sqrt(pressure/density):.6f}, "
                       f"flow_rate={flow_rate_m3h:.1f}м³/ч")
        else:
            flow_rate_m3h = 0.0
            
        return {
            'flow_rate': flow_rate_m3h,
            'opening': self.state['opening'],
            'flow_coefficient': self.state['flow_coefficient']
        }
    
    def set_opening(self, opening: float):
        """Установка степени открытия клапана"""
        # Ограничение значения
        opening = max(self.min_opening, min(opening, self.max_opening))
        self.state['opening'] = opening
        self._update_flow_coefficient()


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
        # Установка степени открытия клапана
        self.components['outlet_valve'].set_opening(valve_opening)
        
        # Получение текущего состояния бака
        tank_state = self.components['tank'].get_state()
        
        # Расчет расхода через клапан
        valve_inputs = {
            'pressure': tank_state['pressure'],
            'density': self.config.get('liquid_density', 1000.0)
        }
        valve_outputs = self.components['outlet_valve'].calculate(valve_inputs, self.time_step)
        
        # Расчет нового состояния бака
        tank_inputs = {
            'inlet_flow': self.config.get('constant_inlet_flow', 100.0),
            'outlet_flow': valve_outputs['flow_rate']
        }
        tank_outputs = self.components['tank'].calculate(tank_inputs, self.time_step)
        
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
        
        return result
    
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
