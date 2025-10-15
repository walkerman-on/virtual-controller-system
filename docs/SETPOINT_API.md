# API для изменения уставки уровня

## Обзор

Система цифрового двойника теперь поддерживает изменение уставки уровня жидкости через REST API. API предоставляет возможность:

- Получать текущую уставку
- Устанавливать новую уставку
- Просматривать историю изменений уставки

## Базовый URL

```
http://localhost:8080
```

## Endpoints

### 1. Получение текущей уставки

**GET** `/api/setpoint/current`

Возвращает текущее значение уставки уровня жидкости.

#### Ответ

```json
{
  "success": true,
  "setpoint": 1.8,
  "unit": "м",
  "timestamp": "2025-10-03T12:38:31.437210"
}
```

#### Пример использования

```bash
curl http://localhost:8080/api/setpoint/current
```

### 2. Установка новой уставки

**POST** `/api/setpoint`

Устанавливает новое значение уставки уровня жидкости.

#### Параметры запроса

```json
{
  "setpoint": 1.5,
  "reason": "Описание причины изменения"
}
```

- `setpoint` (обязательный): Новое значение уставки в метрах (0.5 - 2.5)
- `reason` (опциональный): Описание причины изменения

#### Ответ

```json
{
  "success": true,
  "message": "Уставка успешно изменена с 1.8м на 1.5м",
  "old_setpoint": 1.8,
  "new_setpoint": 1.5,
  "timestamp": "2025-10-03T12:38:31.437210"
}
```

#### Пример использования

```bash
curl -X POST http://localhost:8080/api/setpoint \
  -H "Content-Type: application/json" \
  -d '{"setpoint": 1.5, "reason": "Оптимизация процесса"}'
```

### 3. История изменений уставки

**GET** `/api/setpoint/history`

Возвращает историю изменений уставки.

#### Параметры запроса

- `limit` (опциональный): Количество записей для возврата (по умолчанию 50)

#### Ответ

```json
{
  "success": true,
  "count": 3,
  "data": [
    {
      "timestamp": "2025-10-03T12:38:31.437210+00:00",
      "old_setpoint": 1.8,
      "new_setpoint": 1.5,
      "changed_by": "api",
      "change_reason": "Оптимизация процесса"
    }
  ]
}
```

#### Пример использования

```bash
curl "http://localhost:8080/api/setpoint/history?limit=10"
```

## Обработка ошибок

### Некорректные значения уставки

Если уставка выходит за допустимый диапазон (0.5 - 2.5 метра):

```json
{
  "success": false,
  "error": "Уставка должна быть в диапазоне от 0.5 до 2.5 метров"
}
```

### Некорректный формат данных

Если не указана уставка в запросе:

```json
{
  "success": false,
  "error": "Не указана уставка в запросе"
}
```

### Ошибки подключения

Если OPC UA сервер недоступен:

```json
{
  "success": false,
  "error": "Не удалось получить текущую уставку"
}
```

## Примеры использования

### Python

```python
import requests

# Получение текущей уставки
response = requests.get("http://localhost:8080/api/setpoint/current")
current = response.json()["setpoint"]

# Установка новой уставки
new_setpoint = 1.6
payload = {
    "setpoint": new_setpoint,
    "reason": "Автоматическая оптимизация"
}
response = requests.post(
    "http://localhost:8080/api/setpoint",
    json=payload
)
print(response.json()["message"])
```

### JavaScript

```javascript
// Получение текущей уставки
fetch('http://localhost:8080/api/setpoint/current')
  .then(response => response.json())
  .then(data => console.log('Текущая уставка:', data.setpoint));

// Установка новой уставки
fetch('http://localhost:8080/api/setpoint', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    setpoint: 1.6,
    reason: 'Оптимизация процесса'
  })
})
.then(response => response.json())
.then(data => console.log(data.message));
```

### cURL

```bash
# Получение текущей уставки
curl http://localhost:8080/api/setpoint/current

# Установка новой уставки
curl -X POST http://localhost:8080/api/setpoint \
  -H "Content-Type: application/json" \
  -d '{"setpoint": 1.6, "reason": "Ручная настройка"}'

# Получение истории
curl http://localhost:8080/api/setpoint/history
```

## Безопасность

- API не требует аутентификации (для демонстрационных целей)
- Все изменения уставки логируются в базу данных
- Валидация входных данных предотвращает некорректные значения
- Диапазон допустимых значений: 0.5 - 2.5 метра

## Мониторинг

- Все изменения уставки сохраняются в таблице `controller_data.setpoint_changes`
- Доступна история всех изменений с указанием времени и причины
- Логи изменений доступны через API истории

## Тестирование

Для тестирования API используйте предоставленный скрипт:

```bash
./test_setpoint_api.sh
```

Скрипт автоматически:
- Проверяет доступность API
- Тестирует получение текущей уставки
- Тестирует установку различных значений
- Проверяет обработку некорректных значений
- Просматривает историю изменений
- Возвращает исходную уставку


