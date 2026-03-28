-- Инициализация базы данных для цифрового двойника
-- Создание схем и таблиц для хранения данных процесса

-- Создание схем
CREATE SCHEMA IF NOT EXISTS process_data;
CREATE SCHEMA IF NOT EXISTS controller_data;
CREATE SCHEMA IF NOT EXISTS system_logs;
CREATE SCHEMA IF NOT EXISTS configurations;

-- Таблица для хранения данных процесса (временные ряды)
CREATE TABLE IF NOT EXISTS process_data.process_variables (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    pv_level REAL NOT NULL,                    -- Текущий уровень жидкости (м)
    sp_level REAL NOT NULL,                    -- Уставка уровня (м)
    op_valve REAL NOT NULL,                    -- Управляющее воздействие (%)
    outlet_flow REAL NOT NULL,                 -- Расход на выходе (м³/ч)
    inlet_flow REAL NOT NULL,                  -- Расход на входе (м³/ч)
    tank_pressure REAL,                        -- Давление в баке (Па)
    valve_position REAL,                       -- Фактическое положение клапана (%)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индекс для быстрого поиска по времени
CREATE INDEX IF NOT EXISTS idx_process_variables_timestamp 
ON process_data.process_variables(timestamp);

-- Таблица для хранения состояния PID контроллеров
CREATE TABLE IF NOT EXISTS controller_data.pid_states (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    controller_id VARCHAR(50) NOT NULL,       -- 'primary' или 'backup'
    is_active BOOLEAN NOT NULL,               -- Активен ли контроллер
    kp REAL NOT NULL,                         -- Пропорциональный коэффициент
    ki REAL NOT NULL,                         -- Интегральный коэффициент
    kd REAL NOT NULL,                         -- Дифференциальный коэффициент
    integral REAL NOT NULL,                   -- Интегральная составляющая
    previous_error REAL NOT NULL,             -- Предыдущая ошибка
    previous_derivative REAL NOT NULL,        -- Предыдущая производная
    setpoint REAL NOT NULL,                   -- Уставка
    process_value REAL NOT NULL,              -- Измеренное значение
    output REAL NOT NULL,                     -- Выходное значение
    error_value REAL NOT NULL,                -- Текущая ошибка
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для контроллеров
CREATE INDEX IF NOT EXISTS idx_pid_states_timestamp 
ON controller_data.pid_states(timestamp);
CREATE INDEX IF NOT EXISTS idx_pid_states_controller 
ON controller_data.pid_states(controller_id);

-- Таблица для хранения событий отказоустойчивости
CREATE TABLE IF NOT EXISTS controller_data.failover_events (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    event_type VARCHAR(50) NOT NULL,          -- 'failover', 'failback', 'controller_start', 'controller_stop'
    from_controller VARCHAR(50),              -- Контроллер, с которого переключились
    to_controller VARCHAR(50),                -- Контроллер, на который переключились
    reason TEXT,                              -- Причина переключения
    duration_seconds REAL,                    -- Длительность переключения
    pid_state_before JSONB,                   -- Состояние PID до переключения
    pid_state_after JSONB,                    -- Состояние PID после переключения
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Таблица для хранения heartbeat данных
CREATE TABLE IF NOT EXISTS controller_data.heartbeats (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    controller_id VARCHAR(50) NOT NULL,
    heartbeat_time REAL NOT NULL,             -- Unix timestamp heartbeat
    status VARCHAR(20) NOT NULL,              -- 'active', 'inactive', 'unknown'
    response_time_ms REAL,                    -- Время отклика (мс)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индекс для heartbeat
CREATE INDEX IF NOT EXISTS idx_heartbeats_timestamp 
ON controller_data.heartbeats(timestamp);
CREATE INDEX IF NOT EXISTS idx_heartbeats_controller 
ON controller_data.heartbeats(controller_id);

-- Таблица для системных логов
CREATE TABLE IF NOT EXISTS system_logs.application_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    service_name VARCHAR(100) NOT NULL,       -- 'opcua-server', 'controller-primary', etc.
    log_level VARCHAR(20) NOT NULL,           -- 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    message TEXT NOT NULL,                    -- Сообщение лога
    module VARCHAR(100),                      -- Модуль/класс
    function_name VARCHAR(100),               -- Функция
    line_number INTEGER,                      -- Номер строки
    extra_data JSONB,                         -- Дополнительные данные в JSON
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для логов
CREATE INDEX IF NOT EXISTS idx_application_logs_timestamp 
ON system_logs.application_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_application_logs_service 
ON system_logs.application_logs(service_name);
CREATE INDEX IF NOT EXISTS idx_application_logs_level 
ON system_logs.application_logs(log_level);

-- Таблица для хранения конфигураций
CREATE TABLE IF NOT EXISTS configurations.system_configs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    config_name VARCHAR(100) NOT NULL UNIQUE, -- 'current', 'backup_20231002', etc.
    config_data JSONB NOT NULL,               -- Полная конфигурация в JSON
    description TEXT,                         -- Описание конфигурации
    is_active BOOLEAN DEFAULT FALSE,          -- Активная конфигурация
    created_by VARCHAR(100),                  -- Кто создал
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Таблица для алармов и событий
CREATE TABLE IF NOT EXISTS system_logs.alarms (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    alarm_type VARCHAR(50) NOT NULL,          -- 'high_level', 'low_level', 'controller_failure', etc.
    severity VARCHAR(20) NOT NULL,            -- 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    source VARCHAR(100) NOT NULL,             -- Источник аларма
    message TEXT NOT NULL,                    -- Описание аларма
    value REAL,                               -- Значение, вызвавшее аларм
    threshold REAL,                           -- Пороговое значение
    acknowledged BOOLEAN DEFAULT FALSE,       -- Подтвержден ли аларм
    acknowledged_by VARCHAR(100),             -- Кем подтвержден
    acknowledged_at TIMESTAMP WITH TIME ZONE, -- Когда подтвержден
    resolved BOOLEAN DEFAULT FALSE,           -- Решен ли аларм
    resolved_at TIMESTAMP WITH TIME ZONE,     -- Когда решен
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для алармов
CREATE INDEX IF NOT EXISTS idx_alarms_timestamp 
ON system_logs.alarms(timestamp);
CREATE INDEX IF NOT EXISTS idx_alarms_type 
ON system_logs.alarms(alarm_type);
CREATE INDEX IF NOT EXISTS idx_alarms_severity 
ON system_logs.alarms(severity);
CREATE INDEX IF NOT EXISTS idx_alarms_acknowledged 
ON system_logs.alarms(acknowledged);

-- Таблица для статистики производительности
CREATE TABLE IF NOT EXISTS process_data.performance_metrics (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metric_name VARCHAR(100) NOT NULL,        -- 'control_loop_time', 'opcua_response_time', etc.
    metric_value REAL NOT NULL,               -- Значение метрики
    unit VARCHAR(20),                         -- Единица измерения
    service_name VARCHAR(100),                -- Сервис, от которого метрика
    tags JSONB,                               -- Дополнительные теги
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для метрик
CREATE INDEX IF NOT EXISTS idx_performance_metrics_timestamp 
ON process_data.performance_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_name 
ON process_data.performance_metrics(metric_name);

-- Таблица для хранения истории изменений уставки
CREATE TABLE IF NOT EXISTS controller_data.setpoint_changes (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    old_setpoint REAL NOT NULL,               -- Старая уставка
    new_setpoint REAL NOT NULL,               -- Новая уставка
    changed_by VARCHAR(100) NOT NULL,         -- Кто изменил ('api', 'operator', 'system')
    change_reason TEXT,                       -- Причина изменения
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для изменений уставки
CREATE INDEX IF NOT EXISTS idx_setpoint_changes_timestamp 
ON controller_data.setpoint_changes(timestamp);
CREATE INDEX IF NOT EXISTS idx_setpoint_changes_changed_by 
ON controller_data.setpoint_changes(changed_by);

-- Создание пользователей и прав доступа
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'process_user') THEN
        CREATE USER process_user WITH PASSWORD 'process_password';
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'readonly_user') THEN
        CREATE USER readonly_user WITH PASSWORD 'readonly_password';
    END IF;
END
$$;

-- Права для process_user (полный доступ к данным процесса)
GRANT USAGE ON SCHEMA process_data TO process_user;
GRANT USAGE ON SCHEMA controller_data TO process_user;
GRANT USAGE ON SCHEMA system_logs TO process_user;
GRANT USAGE ON SCHEMA configurations TO process_user;

GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA process_data TO process_user;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA controller_data TO process_user;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA system_logs TO process_user;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA configurations TO process_user;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA process_data TO process_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA controller_data TO process_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA system_logs TO process_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA configurations TO process_user;

-- Права для readonly_user (только чтение)
GRANT USAGE ON SCHEMA process_data TO readonly_user;
GRANT USAGE ON SCHEMA controller_data TO readonly_user;
GRANT USAGE ON SCHEMA system_logs TO readonly_user;
GRANT USAGE ON SCHEMA configurations TO readonly_user;

GRANT SELECT ON ALL TABLES IN SCHEMA process_data TO readonly_user;
GRANT SELECT ON ALL TABLES IN SCHEMA controller_data TO readonly_user;
GRANT SELECT ON ALL TABLES IN SCHEMA system_logs TO readonly_user;
GRANT SELECT ON ALL TABLES IN SCHEMA configurations TO readonly_user;

-- Вставка начальной конфигурации
INSERT INTO configurations.system_configs (config_name, config_data, description, is_active, created_by)
VALUES (
    'initial_config',
    '{"model_parameters": {"tank_height": 3.0, "tank_diameter": 2.0}, "controller_loops": [{"id": "level", "type": "pid", "params": {"kp": 15.0, "ki": 0.1, "kd": 1.0}}]}',
    'Начальная конфигурация системы',
    true,
    'system'
) ON CONFLICT (config_name) DO NOTHING;

-- Создание функции для очистки старых данных
CREATE OR REPLACE FUNCTION cleanup_old_data(days_to_keep INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER := 0;
    temp_count INTEGER;
BEGIN
    -- Очистка старых данных процесса (оставляем только последние N дней)
    DELETE FROM process_data.process_variables 
    WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '1 day' * days_to_keep;
    GET DIAGNOSTICS temp_count = ROW_COUNT;
    deleted_count := deleted_count + temp_count;
    
    -- Очистка старых heartbeat (оставляем только последние 7 дней)
    DELETE FROM controller_data.heartbeats 
    WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '7 days';
    GET DIAGNOSTICS temp_count = ROW_COUNT;
    deleted_count := deleted_count + temp_count;
    
    -- Очистка старых логов (оставляем только последние 14 дней)
    DELETE FROM system_logs.application_logs 
    WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '14 days';
    GET DIAGNOSTICS temp_count = ROW_COUNT;
    deleted_count := deleted_count + temp_count;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Комментарии к таблицам
COMMENT ON SCHEMA process_data IS 'Схема для хранения данных технологического процесса';
COMMENT ON SCHEMA controller_data IS 'Схема для хранения данных контроллеров и отказоустойчивости';
COMMENT ON SCHEMA system_logs IS 'Схема для хранения системных логов и алармов';
COMMENT ON SCHEMA configurations IS 'Схема для хранения конфигураций системы';

COMMENT ON TABLE process_data.process_variables IS 'Временные ряды переменных процесса';
COMMENT ON TABLE controller_data.pid_states IS 'Состояния PID контроллеров';
COMMENT ON TABLE controller_data.failover_events IS 'События переключения контроллеров';
COMMENT ON TABLE system_logs.alarms IS 'Алармы и события системы';
COMMENT ON TABLE configurations.system_configs IS 'Конфигурации системы с версионированием';
