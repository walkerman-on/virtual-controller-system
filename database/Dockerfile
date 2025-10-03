# Dockerfile для PostgreSQL с инициализацией схемы
FROM postgres:15-alpine

# Установка переменных окружения
ENV POSTGRES_DB=digital_twin_db
ENV POSTGRES_USER=postgres
ENV POSTGRES_PASSWORD=postgres_password

# Копирование скриптов инициализации
COPY init/ /docker-entrypoint-initdb.d/

# Создание директории для данных
RUN mkdir -p /var/lib/postgresql/data

# Установка прав доступа
RUN chown -R postgres:postgres /var/lib/postgresql/data

# Экспорт порта
EXPOSE 5432

# Добавление healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
	CMD pg_isready -U postgres -d digital_twin_db || exit 1

# Команда запуска с настройками производительности
CMD ["postgres", "-c", "shared_preload_libraries=pg_stat_statements", \
	"-c", "max_connections=100", \
	"-c", "shared_buffers=256MB", \
	"-c", "effective_cache_size=1GB", \
	"-c", "maintenance_work_mem=64MB", \
	"-c", "checkpoint_completion_target=0.9", \
	"-c", "wal_buffers=16MB", \
	"-c", "default_statistics_target=100", \
	"-c", "random_page_cost=1.1", \
	"-c", "effective_io_concurrency=200"]
