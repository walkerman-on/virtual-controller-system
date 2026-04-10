# Экспресс нагрузочное тестирование (10-15 минут)

Этот гайд проверяет, как система с виртуальными контроллерами выдерживает нагрузку десятков контуров, не меняя штатные контейнеры:

- `pid-controller-primary`
- `pid-controller-backup`

Нагрузка создается отдельным тестовым контейнером `load-generator`.

## Что именно тестируется

- Масштабируемость OPC UA-сервера при росте числа виртуальных клиентов.
- Задержка цикла обмена (read/write), включая `p95/p99`.
- Частота ошибок и пропущенных дедлайнов цикла.
- Устойчивость сервисов `opcua-server`, `digital-twin-db`, `analytics-service` под пиком.

## Подготовка

1. Поднять основную систему:

```bash
docker compose up -d
```

2. Убедиться, что сервисы healthy:

```bash
docker compose ps
```

3. Сделать скрипт запуска исполняемым (один раз):

```bash
chmod +x load-test/run_profiles.sh
```

## Быстрый запуск всех 3 тестов

```bash
./load-test/run_profiles.sh
```

По умолчанию включён **`FULL_PID_CYCLE=true`**: каждый эмулятор выполняет цикл как боевой контроллер (SP/PV → PID из `config.json` → запись клапана). Перед тестами выполняется **`docker compose … build load-generator`**, чтобы образ совпадал с текущим кодом в `load-test/`.

Скрипт прогоняет 3 профиля:

1. `baseline`: `N=10`, `cycle=1000ms`, `3 мин`
2. `workload`: `N=30`, `cycle=500ms`, `5 мин`
3. `spike`: `N=50`, `cycle=200ms`, `3 мин`

Результаты:

- JSON-отчеты: `load-test/results/*.json`
- Логи запусков + срезы `docker stats`: `load-test/results/*.log`
- Понятный отчет: `load-test/results/LOAD_TEST_REPORT.md`

Скрипт сам:

- поднимает систему (`docker compose up -d`);
- прогоняет 3 сценария;
- формирует итоговый markdown-отчет с таблицей и статусами `PASS/WARNING/FAIL`.

## Ручной запуск одного сценария

Пример для рабочего профиля:

```bash
docker compose -f docker-compose.yml -f docker-compose.loadtest.yml run --rm \
  -e CONTROLLERS=30 \
  -e CYCLE_MS=500 \
  -e DURATION_SEC=300 \
  -e WRITE_ENABLED=false \
  load-generator
```

Параметры:

- `CONTROLLERS` — число виртуальных контроллеров.
- `CYCLE_MS` — период цикла каждого контроллера в миллисекундах.
- `DURATION_SEC` — длительность теста.
- `WRITE_ENABLED` — включить запись `OP_valve` (`true/false`).
- `FULL_PID_CYCLE` — цикл как у боевого контроллера: чтение SP/PV из `controller_loops`, расчёт PID (как в `universal_controller`), запись MV; при `CONTROLLERS=1` дополнительно пишется состояние PID в OPC. При `N>1` состояние PID у каждого воркера своё в памяти, в OPC пишется только выход клапана (общий тег — нагрузочный стресс).

Пример полного PID-цикла:

```bash
docker compose -f docker-compose.yml -f docker-compose.loadtest.yml run --rm \
  -e CONTROLLERS=10 \
  -e CYCLE_MS=500 \
  -e DURATION_SEC=180 \
  -e FULL_PID_CYCLE=true \
  load-generator
```

## Как читать JSON-результат

Основные поля:

- `summary.total_cycles` — сколько циклов выполнено суммарно.
- `summary.total_errors` — сколько циклов завершились ошибкой.
- `summary.error_rate_pct` — процент ошибок.
- `summary.missed_deadlines` — циклы, не уложившиеся в `CYCLE_MS`.
- `summary.missed_deadline_rate_pct` — доля пропущенных дедлайнов.
- `summary.latency_ms.p95/p99/max` — задержка цикла.

Если не хочешь смотреть JSON вручную, используй готовый файл:

- `load-test/results/LOAD_TEST_REPORT.md`

В нем уже есть:

- сводная таблица по всем сценариям;
- вывод по каждому сценарию;
- общий итог стенда.

## Практическая интерпретация

### Зеленая зона

- `error_rate_pct < 1-2%`
- `latency p95` стабильный, без резких скачков между профилями
- `missed_deadline_rate_pct` низкий и не растет лавинообразно
- по `docker stats` нет постоянного упора в 95-100% CPU

Вывод: конфигурация пригодна для такого уровня нагрузки.

### Желтая зона

- ошибки низкие, но `p99/max` сильно растут
- заметный рост `missed_deadlines` на `workload/spike`

Вывод: система работает, но без запаса; нужны оптимизации частоты опроса, записи в БД, логирования.

### Красная зона

- `error_rate_pct` быстро растет
- `missed_deadline_rate_pct` высокий
- после `spike` сервисы долго восстанавливаются или требуют ручных действий

Вывод: текущая конфигурация не подходит для десятков контроллеров без доработок.

## Что включать в отчет (для сравнения с ПЛК)

- Параметры стенда: CPU/RAM хоста, версия контейнеров.
- Профиль теста: `N`, `CYCLE_MS`, `DURATION_SEC`.
- Метрики: `error_rate`, `p95/p99/max`, `missed_deadline_rate`, CPU/RAM сервисов.
- Итог: pass/fail и максимальная стабильная нагрузка.
