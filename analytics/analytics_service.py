"""
Сервис аналитики и отчетности для цифрового двойника
Предоставляет REST API для получения исторических данных, статистики и отчетов
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
from opcua import Client

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Глобальное подключение к БД
db_connection = None

# OPC UA клиент для изменения уставки
opcua_client = None


def init_database():
    """Инициализация подключения к базе данных"""
    global db_connection
    try:
        db_connection = psycopg2.connect(
            host=os.getenv('DB_HOST', 'database'),
            port=int(os.getenv('DB_PORT', '5432')),
            database=os.getenv('DB_NAME', 'digital_twin_db'),
            user=os.getenv('DB_USER', 'process_user'),
            password=os.getenv('DB_PASSWORD', 'process_password')
        )
        logger.info("✅ Сервис аналитики подключен к базе данных")
    except Exception as e:
        logger.error(f"Ошибка подключения к БД: {e}")
        db_connection = None


def init_opcua_client():
    """Инициализация OPC UA клиента для изменения уставки"""
    global opcua_client
    try:
        opcua_server_url = os.getenv('OPCUA_SERVER_URL', 'opc.tcp://opcua-server:4840/freeopcua/server/')
        opcua_client = Client(opcua_server_url)
        opcua_client.connect()
        logger.info("🔗 Сервис аналитики подключен к OPC UA серверу")
    except Exception as e:
        logger.error(f"Ошибка подключения к OPC UA серверу: {e}")
        opcua_client = None


def set_opcua_setpoint(new_setpoint: float) -> bool:
    """Установка новой уставки через OPC UA"""
    global opcua_client
    
    if not opcua_client:
        logger.error("OPC UA клиент не инициализирован")
        return False
    
    try:
        # Node ID для уставки уровня (SP_level)
        setpoint_node_id = "ns=2;i=5"
        setpoint_node = opcua_client.get_node(setpoint_node_id)
        
        # Устанавливаем новое значение уставки
        setpoint_node.set_value(new_setpoint)
        
        logger.info(f"✅ Уставка успешно изменена на {new_setpoint}м")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка установки уставки: {e}")
        return False


def get_opcua_setpoint() -> Optional[float]:
    """Получение текущей уставки через OPC UA"""
    global opcua_client
    
    if not opcua_client:
        logger.error("OPC UA клиент не инициализирован")
        return None
    
    try:
        # Node ID для уставки уровня (SP_level)
        setpoint_node_id = "ns=2;i=5"
        setpoint_node = opcua_client.get_node(setpoint_node_id)
        
        # Получаем текущее значение уставки
        current_setpoint = setpoint_node.get_value()
        
        logger.info(f"📊 Текущая уставка: {current_setpoint}м")
        return current_setpoint
        
    except Exception as e:
        logger.error(f"Ошибка получения уставки: {e}")
        return None


@app.route('/health', methods=['GET'])
def health_check():
    """Проверка состояния сервиса"""
    return jsonify({
        'status': 'healthy',
        'service': 'analytics',
        'timestamp': datetime.now().isoformat(),
        'database_connected': db_connection is not None
    })


@app.route('/api/process/latest', methods=['GET'])
def get_latest_process_data():
    """Получение последних данных процесса"""
    if not db_connection:
        return jsonify({'error': 'База данных не подключена'}), 500
    
    try:
        limit = int(request.args.get('limit', 10))
        
        with db_connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT timestamp, pv_level, sp_level, op_valve, outlet_flow, inlet_flow, tank_pressure, valve_position
                FROM process_data.process_variables 
                ORDER BY timestamp DESC 
                LIMIT %s
            """, (limit,))
            
            records = cursor.fetchall()
            
            # Преобразуем datetime в строки для JSON
            data = []
            for record in records:
                record_dict = dict(record)
                if 'timestamp' in record_dict:
                    record_dict['timestamp'] = record_dict['timestamp'].isoformat()
                data.append(record_dict)
            
            return jsonify({
                'success': True,
                'count': len(data),
                'data': data
            })
            
    except Exception as e:
        logger.error(f"Ошибка получения данных процесса: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/process/statistics', methods=['GET'])
def get_process_statistics():
    """Получение статистики процесса за период"""
    if not db_connection:
        return jsonify({'error': 'База данных не подключена'}), 500
    
    try:
        hours = int(request.args.get('hours', 24))
        
        with db_connection.cursor(cursor_factory=RealDictCursor) as cursor:
            # Общая статистика
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_records,
                    AVG(pv_level) as avg_level,
                    MIN(pv_level) as min_level,
                    MAX(pv_level) as max_level,
                    AVG(op_valve) as avg_valve,
                    AVG(outlet_flow) as avg_outlet_flow,
                    AVG(inlet_flow) as avg_inlet_flow
                FROM process_data.process_variables 
                WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '%s hours'
            """, (hours,))
            
            stats = cursor.fetchone()
            
            # Статистика по точности поддержания уровня
            cursor.execute("""
                SELECT 
                    COUNT(*) * 100.0 / (SELECT COUNT(*) FROM process_data.process_variables 
                                       WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '%s hours') as percentage
                FROM process_data.process_variables 
                WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '%s hours'
                AND ABS(pv_level - sp_level) / sp_level <= 0.05
            """, (hours, hours))
            
            level_accuracy = cursor.fetchone()
            
            return jsonify({
                'success': True,
                'period_hours': hours,
                'total_records': stats['total_records'] if stats else 0,
                'level_statistics': {
                    'average': float(stats['avg_level']) if stats and stats['avg_level'] else 0,
                    'minimum': float(stats['min_level']) if stats and stats['min_level'] else 0,
                    'maximum': float(stats['max_level']) if stats and stats['max_level'] else 0
                },
                'valve_statistics': {
                    'average_opening': float(stats['avg_valve']) if stats and stats['avg_valve'] else 0
                },
                'flow_statistics': {
                    'average_outlet': float(stats['avg_outlet_flow']) if stats and stats['avg_outlet_flow'] else 0,
                    'average_inlet': float(stats['avg_inlet_flow']) if stats and stats['avg_inlet_flow'] else 0
                },
                'level_accuracy_percentage': float(level_accuracy['percentage']) if level_accuracy and level_accuracy['percentage'] else 0
            })
            
    except Exception as e:
        logger.error(f"Ошибка получения статистики процесса: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/controller/pid-history', methods=['GET'])
def get_pid_history():
    """Получение истории PID контроллера"""
    if not db_connection:
        return jsonify({'error': 'База данных не подключена'}), 500
    
    try:
        limit = int(request.args.get('limit', 100))
        controller_id = request.args.get('controller_id', 'primary')
        
        with db_connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT timestamp, controller_id, is_active, kp, ki, kd, 
                       integral, previous_error, previous_derivative,
                       setpoint, process_value, output, error_value
                FROM controller_data.pid_states 
                WHERE controller_id = %s
                ORDER BY timestamp DESC 
                LIMIT %s
            """, (controller_id, limit))
            
            records = cursor.fetchall()
            
            # Преобразуем datetime в строки для JSON
            data = []
            for record in records:
                record_dict = dict(record)
                if 'timestamp' in record_dict:
                    record_dict['timestamp'] = record_dict['timestamp'].isoformat()
                data.append(record_dict)
            
            return jsonify({
                'success': True,
                'count': len(data),
                'controller_id': controller_id,
                'data': data
            })
            
    except Exception as e:
        logger.error(f"Ошибка получения истории PID: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/system/failover-events', methods=['GET'])
def get_failover_events():
    """Получение событий переключения контроллеров"""
    if not db_connection:
        return jsonify({'error': 'База данных не подключена'}), 500
    
    try:
        limit = int(request.args.get('limit', 50))
        
        with db_connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT timestamp, event_type, from_controller, to_controller, 
                       reason, duration_seconds, pid_state_before, pid_state_after
                FROM controller_data.failover_events 
                ORDER BY timestamp DESC 
                LIMIT %s
            """, (limit,))
            
            records = cursor.fetchall()
            
            # Преобразуем datetime в строки для JSON
            data = []
            for record in records:
                record_dict = dict(record)
                if 'timestamp' in record_dict:
                    record_dict['timestamp'] = record_dict['timestamp'].isoformat()
                data.append(record_dict)
            
            return jsonify({
                'success': True,
                'count': len(data),
                'data': data
            })
            
    except Exception as e:
        logger.error(f"Ошибка получения событий переключения: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/system/performance', methods=['GET'])
def get_performance_metrics():
    """Получение метрик производительности системы"""
    if not db_connection:
        return jsonify({'error': 'База данных не подключена'}), 500
    
    try:
        hours = int(request.args.get('hours', 24))
        
        with db_connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT 
                    AVG(CASE WHEN metric_name = 'controller_response_time' THEN metric_value END) as avg_controller_response,
                    AVG(CASE WHEN metric_name = 'model_calculation_time' THEN metric_value END) as avg_model_calculation,
                    AVG(CASE WHEN metric_name = 'opcua_communication_time' THEN metric_value END) as avg_opcua_communication,
                    COUNT(*) as total_measurements
                FROM process_data.performance_metrics 
                WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '%s hours'
            """, (hours,))
            
            metrics = cursor.fetchone()
            
            return jsonify({
                'success': True,
                'period_hours': hours,
                'metrics': {
                    'average_controller_response_time': float(metrics['avg_controller_response']) if metrics and metrics['avg_controller_response'] else 0,
                    'average_model_calculation_time': float(metrics['avg_model_calculation']) if metrics and metrics['avg_model_calculation'] else 0,
                    'average_opcua_communication_time': float(metrics['avg_opcua_communication']) if metrics and metrics['avg_opcua_communication'] else 0,
                    'total_measurements': metrics['total_measurements'] if metrics else 0
                }
            })
            
    except Exception as e:
        logger.error(f"Ошибка получения метрик производительности: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/config/current', methods=['GET'])
def get_current_config():
    """Получение текущей конфигурации системы"""
    if not db_connection:
        return jsonify({'error': 'База данных не подключена'}), 500
    
    try:
        with db_connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT config_name, config_data, description, created_at
                FROM configurations.system_configs 
                WHERE is_active = true
                ORDER BY config_name
            """)
            
            records = cursor.fetchall()
            
            # Преобразуем datetime в строки для JSON
            config = {}
            for record in records:
                record_dict = dict(record)
                if 'created_at' in record_dict:
                    record_dict['created_at'] = record_dict['created_at'].isoformat()
                config[record_dict['config_name']] = record_dict
            
            return jsonify({
                'success': True,
                'config': config
            })
            
    except Exception as e:
        logger.error(f"Ошибка получения конфигурации: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/setpoint/current', methods=['GET'])
def get_current_setpoint():
    """Получение текущей уставки уровня"""
    try:
        current_setpoint = get_opcua_setpoint()
        
        if current_setpoint is None:
            return jsonify({
                'success': False,
                'error': 'Не удалось получить текущую уставку'
            }), 500
        
        return jsonify({
            'success': True,
            'setpoint': current_setpoint,
            'unit': 'м',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения уставки: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/setpoint', methods=['POST'])
def set_setpoint():
    """Установка новой уставки уровня"""
    try:
        # Получаем данные из запроса
        data = request.get_json()
        
        if not data or 'setpoint' not in data:
            return jsonify({
                'success': False,
                'error': 'Не указана уставка в запросе'
            }), 400
        
        new_setpoint = float(data['setpoint'])
        
        # Проверяем диапазон значений (0.5 - 2.5 метра)
        if new_setpoint < 0.5 or new_setpoint > 2.5:
            return jsonify({
                'success': False,
                'error': 'Уставка должна быть в диапазоне от 0.5 до 2.5 метров'
            }), 400
        
        # Получаем старую уставку для логирования
        old_setpoint = get_opcua_setpoint()
        
        # Устанавливаем новую уставку
        success = set_opcua_setpoint(new_setpoint)
        
        if not success:
            return jsonify({
                'success': False,
                'error': 'Не удалось установить новую уставку'
            }), 500
        
        # Логируем изменение в базу данных
        if db_connection:
            try:
                with db_connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO controller_data.setpoint_changes 
                        (old_setpoint, new_setpoint, changed_by, change_reason, timestamp)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        old_setpoint,
                        new_setpoint,
                        'api',
                        data.get('reason', 'API request'),
                        datetime.now()
                    ))
                    db_connection.commit()
            except Exception as e:
                logger.warning(f"Не удалось сохранить изменение уставки в БД: {e}")
        
        return jsonify({
            'success': True,
            'message': f'Уставка успешно изменена с {old_setpoint}м на {new_setpoint}м',
            'old_setpoint': old_setpoint,
            'new_setpoint': new_setpoint,
            'timestamp': datetime.now().isoformat()
        })
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': 'Некорректное значение уставки'
        }), 400
    except Exception as e:
        logger.error(f"Ошибка установки уставки: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/setpoint/history', methods=['GET'])
def get_setpoint_history():
    """Получение истории изменений уставки"""
    if not db_connection:
        return jsonify({'error': 'База данных не подключена'}), 500
    
    try:
        limit = int(request.args.get('limit', 50))
        
        with db_connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT timestamp, old_setpoint, new_setpoint, changed_by, change_reason
                FROM controller_data.setpoint_changes 
                ORDER BY timestamp DESC 
                LIMIT %s
            """, (limit,))
            
            records = cursor.fetchall()
            
            # Преобразуем datetime в строки для JSON
            data = []
            for record in records:
                record_dict = dict(record)
                if 'timestamp' in record_dict:
                    record_dict['timestamp'] = record_dict['timestamp'].isoformat()
                data.append(record_dict)
            
            return jsonify({
                'success': True,
                'count': len(data),
                'data': data
            })
            
    except Exception as e:
        logger.error(f"Ошибка получения истории уставки: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Инициализация базы данных
    init_database()
    
    # Инициализация OPC UA клиента
    init_opcua_client()
    
    # Запуск сервера
    port = int(os.getenv('ANALYTICS_PORT', '8080'))
    host = os.getenv('ANALYTICS_HOST', '0.0.0.0')
    
    logger.info(f"🚀 Запуск сервиса аналитики на {host}:{port}")
    app.run(host=host, port=port, debug=False)