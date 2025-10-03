"""
Модуль для работы с базой данных PostgreSQL
Обеспечивает сохранение и получение данных процесса, контроллеров и логов
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

import asyncpg
import psycopg2
from psycopg2.extras import RealDictCursor

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Менеджер базы данных для цифрового двойника
    Обеспечивает асинхронное и синхронное подключение к PostgreSQL
    """
    
    def __init__(self, 
                 host: str = "localhost",
                 port: int = 5432,
                 database: str = "digital_twin_db",
                 user: str = "process_user",
                 password: str = "process_password"):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.connection_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        self.async_pool: Optional[asyncpg.Pool] = None
        self.sync_connection: Optional[psycopg2.extensions.connection] = None
        
    async def init_async_pool(self, min_size: int = 5, max_size: int = 20):
        """Инициализация пула асинхронных подключений"""
        try:
            self.async_pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=min_size,
                max_size=max_size,
                command_timeout=30
            )
            logger.info(f"✓ Асинхронный пул подключений к БД инициализирован (размер: {min_size}-{max_size})")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации асинхронного пула БД: {e}")
            raise
    
    def init_sync_connection(self):
        """Инициализация синхронного подключения"""
        try:
            self.sync_connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                cursor_factory=RealDictCursor
            )
            self.sync_connection.autocommit = True
            logger.info("✓ Синхронное подключение к БД установлено")
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к БД: {e}")
            raise
    
    async def close_async_pool(self):
        """Закрытие пула асинхронных подключений"""
        if self.async_pool:
            await self.async_pool.close()
            logger.info("Асинхронный пул подключений закрыт")
    
    def close_sync_connection(self):
        """Закрытие синхронного подключения"""
        if self.sync_connection:
            self.sync_connection.close()
            logger.info("Синхронное подключение к БД закрыто")
    
    # === МЕТОДЫ ДЛЯ РАБОТЫ С ДАННЫМИ ПРОЦЕССА ===
    
    async def save_process_data(self, 
                               pv_level: float,
                               sp_level: float,
                               op_valve: float,
                               outlet_flow: float,
                               inlet_flow: float,
                               tank_pressure: Optional[float] = None,
                               valve_position: Optional[float] = None) -> bool:
        """Сохранение данных процесса"""
        if not self.async_pool:
            logger.error("Асинхронный пул не инициализирован")
            return False
        
        try:
            async with self.async_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO process_data.process_variables 
                    (pv_level, sp_level, op_valve, outlet_flow, inlet_flow, tank_pressure, valve_position)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, pv_level, sp_level, op_valve, outlet_flow, inlet_flow, tank_pressure, valve_position)
            
            logger.debug(f"Данные процесса сохранены: PV={pv_level:.3f}, SP={sp_level:.3f}, OP={op_valve:.1f}%")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения данных процесса: {e}")
            return False
    
    def save_process_data_sync(self, 
                              pv_level: float,
                              sp_level: float,
                              op_valve: float,
                              outlet_flow: float,
                              inlet_flow: float,
                              tank_pressure: Optional[float] = None,
                              valve_position: Optional[float] = None) -> bool:
        """Синхронное сохранение данных процесса"""
        if not self.sync_connection:
            logger.error("Синхронное подключение не установлено")
            return False
        
        try:
            with self.sync_connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO process_data.process_variables 
                    (pv_level, sp_level, op_valve, outlet_flow, inlet_flow, tank_pressure, valve_position)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (pv_level, sp_level, op_valve, outlet_flow, inlet_flow, tank_pressure, valve_position))
            
            logger.debug(f"Данные процесса сохранены: PV={pv_level:.3f}, SP={sp_level:.3f}, OP={op_valve:.1f}%")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения данных процесса: {e}")
            return False
    
    # === МЕТОДЫ ДЛЯ РАБОТЫ С СОСТОЯНИЕМ PID ===
    
    async def save_pid_state(self,
                            controller_id: str,
                            is_active: bool,
                            kp: float, ki: float, kd: float,
                            integral: float,
                            previous_error: float,
                            previous_derivative: float,
                            setpoint: float,
                            process_value: float,
                            output: float,
                            error_value: float) -> bool:
        """Сохранение состояния PID контроллера"""
        if not self.async_pool:
            logger.error("Асинхронный пул не инициализирован")
            return False
        
        try:
            async with self.async_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO controller_data.pid_states 
                    (controller_id, is_active, kp, ki, kd, integral, previous_error, 
                     previous_derivative, setpoint, process_value, output, error_value)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """, controller_id, is_active, kp, ki, kd, integral, previous_error,
                     previous_derivative, setpoint, process_value, output, error_value)
            
            logger.debug(f"Состояние PID сохранено: {controller_id}, active={is_active}, integral={integral:.3f}")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения состояния PID: {e}")
            return False
    
    def save_pid_state_sync(self,
                           controller_id: str,
                           is_active: bool,
                           kp: float, ki: float, kd: float,
                           integral: float,
                           previous_error: float,
                           previous_derivative: float,
                           setpoint: float,
                           process_value: float,
                           output: float,
                           error_value: float) -> bool:
        """Синхронное сохранение состояния PID контроллера"""
        if not self.sync_connection:
            logger.error("Синхронное подключение не установлено")
            return False
        
        try:
            with self.sync_connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO controller_data.pid_states 
                    (controller_id, is_active, kp, ki, kd, integral, previous_error, 
                     previous_derivative, setpoint, process_value, output, error_value)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (controller_id, is_active, kp, ki, kd, integral, previous_error,
                      previous_derivative, setpoint, process_value, output, error_value))
            
            logger.debug(f"Состояние PID сохранено: {controller_id}, active={is_active}, integral={integral:.3f}")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения состояния PID: {e}")
            return False
    
    # === МЕТОДЫ ДЛЯ РАБОТЫ С СОБЫТИЯМИ ОТКАЗОУСТОЙЧИВОСТИ ===
    
    async def save_failover_event(self,
                                 event_type: str,
                                 from_controller: Optional[str] = None,
                                 to_controller: Optional[str] = None,
                                 reason: Optional[str] = None,
                                 duration_seconds: Optional[float] = None,
                                 pid_state_before: Optional[Dict] = None,
                                 pid_state_after: Optional[Dict] = None) -> bool:
        """Сохранение события отказоустойчивости"""
        if not self.async_pool:
            logger.error("Асинхронный пул не инициализирован")
            return False
        
        try:
            async with self.async_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO controller_data.failover_events 
                    (event_type, from_controller, to_controller, reason, duration_seconds, 
                     pid_state_before, pid_state_after)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, event_type, from_controller, to_controller, reason, duration_seconds,
                     json.dumps(pid_state_before) if pid_state_before else None,
                     json.dumps(pid_state_after) if pid_state_after else None)
            
            logger.info(f"Событие отказоустойчивости сохранено: {event_type} ({from_controller} -> {to_controller})")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения события отказоустойчивости: {e}")
            return False
    
    # === МЕТОДЫ ДЛЯ РАБОТЫ с HEARTBEAT ===
    
    async def save_heartbeat(self,
                            controller_id: str,
                            heartbeat_time: float,
                            status: str,
                            response_time_ms: Optional[float] = None) -> bool:
        """Сохранение heartbeat данных"""
        if not self.async_pool:
            return False
        
        try:
            async with self.async_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO controller_data.heartbeats 
                    (controller_id, heartbeat_time, status, response_time_ms)
                    VALUES ($1, $2, $3, $4)
                """, controller_id, heartbeat_time, status, response_time_ms)
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения heartbeat: {e}")
            return False
    
    # === МЕТОДЫ ДЛЯ РАБОТЫ С ЛОГАМИ ===
    
    async def save_log(self,
                      service_name: str,
                      log_level: str,
                      message: str,
                      module: Optional[str] = None,
                      function_name: Optional[str] = None,
                      line_number: Optional[int] = None,
                      extra_data: Optional[Dict] = None) -> bool:
        """Сохранение лога приложения"""
        if not self.async_pool:
            return False
        
        try:
            async with self.async_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO system_logs.application_logs 
                    (service_name, log_level, message, module, function_name, line_number, extra_data)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, service_name, log_level, message, module, function_name, line_number,
                     json.dumps(extra_data) if extra_data else None)
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения лога: {e}")
            return False
    
    # === МЕТОДЫ ДЛЯ РАБОТЫ С АЛАРМАМИ ===
    
    async def save_alarm(self,
                        alarm_type: str,
                        severity: str,
                        source: str,
                        message: str,
                        value: Optional[float] = None,
                        threshold: Optional[float] = None) -> bool:
        """Сохранение аларма"""
        if not self.async_pool:
            return False
        
        try:
            async with self.async_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO system_logs.alarms 
                    (alarm_type, severity, source, message, value, threshold)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, alarm_type, severity, source, message, value, threshold)
            
            logger.warning(f"АЛАРМ: {severity} - {alarm_type} от {source}: {message}")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения аларма: {e}")
            return False
    
    # === МЕТОДЫ ДЛЯ ПОЛУЧЕНИЯ ДАННЫХ ===
    
    async def get_latest_process_data(self, limit: int = 100) -> List[Dict]:
        """Получение последних данных процесса"""
        if not self.async_pool:
            return []
        
        try:
            async with self.async_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM process_data.process_variables 
                    ORDER BY timestamp DESC 
                    LIMIT $1
                """, limit)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения данных процесса: {e}")
            return []
    
    async def get_controller_statistics(self, controller_id: str, hours: int = 24) -> Dict:
        """Получение статистики контроллера за период"""
        if not self.async_pool:
            return {}
        
        try:
            async with self.async_pool.acquire() as conn:
                # Статистика PID состояний
                pid_stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_records,
                        AVG(integral) as avg_integral,
                        AVG(ABS(error_value)) as avg_error,
                        AVG(output) as avg_output,
                        SUM(CASE WHEN is_active THEN 1 ELSE 0 END) as active_time_records
                    FROM controller_data.pid_states 
                    WHERE controller_id = $1 
                    AND timestamp > CURRENT_TIMESTAMP - INTERVAL '%s hours'
                """, controller_id, str(hours))
                
                # События отказоустойчивости
                failover_count = await conn.fetchval("""
                    SELECT COUNT(*) FROM controller_data.failover_events 
                    WHERE (from_controller = $1 OR to_controller = $1)
                    AND timestamp > CURRENT_TIMESTAMP - INTERVAL '%s hours'
                """, controller_id, str(hours))
                
                return {
                    'controller_id': controller_id,
                    'period_hours': hours,
                    'total_records': pid_stats['total_records'] if pid_stats else 0,
                    'avg_integral': float(pid_stats['avg_integral']) if pid_stats and pid_stats['avg_integral'] else 0.0,
                    'avg_error': float(pid_stats['avg_error']) if pid_stats and pid_stats['avg_error'] else 0.0,
                    'avg_output': float(pid_stats['avg_output']) if pid_stats and pid_stats['avg_output'] else 0.0,
                    'active_time_records': pid_stats['active_time_records'] if pid_stats else 0,
                    'failover_events': failover_count if failover_count else 0
                }
        except Exception as e:
            logger.error(f"Ошибка получения статистики контроллера: {e}")
            return {}
    
    # === МЕТОДЫ ДЛЯ РАБОТЫ С КОНФИГУРАЦИЯМИ ===
    
    async def save_configuration(self,
                                config_name: str,
                                config_data: Dict,
                                description: Optional[str] = None,
                                created_by: str = "system") -> bool:
        """Сохранение конфигурации"""
        if not self.async_pool:
            return False
        
        try:
            async with self.async_pool.acquire() as conn:
                # Деактивируем предыдущую активную конфигурацию
                await conn.execute("""
                    UPDATE configurations.system_configs 
                    SET is_active = FALSE 
                    WHERE is_active = TRUE
                """)
                
                # Вставляем новую конфигурацию
                await conn.execute("""
                    INSERT INTO configurations.system_configs 
                    (config_name, config_data, description, is_active, created_by)
                    VALUES ($1, $2, $3, TRUE, $4)
                    ON CONFLICT (config_name) DO UPDATE SET
                    config_data = EXCLUDED.config_data,
                    description = EXCLUDED.description,
                    is_active = TRUE,
                    timestamp = CURRENT_TIMESTAMP
                """, config_name, json.dumps(config_data), description, created_by)
            
            logger.info(f"Конфигурация '{config_name}' сохранена")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации: {e}")
            return False
    
    async def get_active_configuration(self) -> Optional[Dict]:
        """Получение активной конфигурации"""
        if not self.async_pool:
            return None
        
        try:
            async with self.async_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT config_name, config_data, description, timestamp 
                    FROM configurations.system_configs 
                    WHERE is_active = TRUE 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """)
                
                if row:
                    return {
                        'config_name': row['config_name'],
                        'config_data': json.loads(row['config_data']),
                        'description': row['description'],
                        'timestamp': row['timestamp']
                    }
                return None
        except Exception as e:
            logger.error(f"Ошибка получения активной конфигурации: {e}")
            return None


class DatabaseLogger:
    """
    Кастомный логгер для записи в базу данных
    """
    
    def __init__(self, db_manager: DatabaseManager, service_name: str):
        self.db_manager = db_manager
        self.service_name = service_name
    
    async def log_info(self, message: str, **kwargs):
        """Запись INFO лога"""
        await self.db_manager.save_log(
            service_name=self.service_name,
            log_level='INFO',
            message=message,
            extra_data=kwargs if kwargs else None
        )
    
    async def log_warning(self, message: str, **kwargs):
        """Запись WARNING лога"""
        await self.db_manager.save_log(
            service_name=self.service_name,
            log_level='WARNING',
            message=message,
            extra_data=kwargs if kwargs else None
        )
    
    async def log_error(self, message: str, **kwargs):
        """Запись ERROR лога"""
        await self.db_manager.save_log(
            service_name=self.service_name,
            log_level='ERROR',
            message=message,
            extra_data=kwargs if kwargs else None
        )


# Глобальный экземпляр менеджера БД
db_manager = None

def get_db_manager() -> DatabaseManager:
    """Получение глобального экземпляра менеджера БД"""
    global db_manager
    if db_manager is None:
        # Получение параметров подключения из переменных окружения
        host = os.getenv('DB_HOST', 'localhost')
        port = int(os.getenv('DB_PORT', '5432'))
        database = os.getenv('DB_NAME', 'digital_twin_db')
        user = os.getenv('DB_USER', 'process_user')
        password = os.getenv('DB_PASSWORD', 'process_password')
        
        db_manager = DatabaseManager(host, port, database, user, password)
    
    return db_manager


async def test_database_connection():
    """Тестирование подключения к базе данных"""
    db = get_db_manager()
    
    try:
        await db.init_async_pool(min_size=1, max_size=5)
        
        # Тест записи данных процесса
        success = await db.save_process_data(
            pv_level=1.5,
            sp_level=2.0,
            op_valve=50.0,
            outlet_flow=75.0,
            inlet_flow=100.0
        )
        
        if success:
            logger.info("✓ Тест записи данных процесса успешен")
        
        # Тест получения данных
        data = await db.get_latest_process_data(limit=1)
        if data:
            logger.info(f"✓ Тест получения данных успешен: {len(data)} записей")
        
        await db.close_async_pool()
        logger.info("✓ Тестирование БД завершено успешно")
        
    except Exception as e:
        logger.error(f"❌ Ошибка тестирования БД: {e}")


if __name__ == "__main__":
    # Запуск теста подключения
    asyncio.run(test_database_connection())
