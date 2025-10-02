# Используем тот же базовый образ что и у контроллеров
FROM test_cursor-controller-primary:latest

# Копирование упрощенного watchdog файла
COPY simple_watchdog.py /app/

# Остаемся под непривилегированным пользователем
USER appuser

WORKDIR /app

CMD ["python", "simple_watchdog.py"]