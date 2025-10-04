#!/bin/bash

# Скрипт для тестирования API изменения уставки
API_BASE_URL="http://localhost:8080"

echo "🚀 Запуск тестирования API изменения уставки"
echo "=================================================="

# Проверяем доступность API
echo "🔍 Проверка доступности API..."
if curl -s "$API_BASE_URL/health" > /dev/null; then
    echo "✅ Analytics сервис доступен"
else
    echo "❌ Analytics сервис недоступен"
    exit 1
fi

echo

# Получаем текущую уставку
echo "🔍 Получение текущей уставки..."
CURRENT_SETPOINT=$(curl -s "$API_BASE_URL/api/setpoint/current" | jq -r '.setpoint')
if [ "$CURRENT_SETPOINT" != "null" ]; then
    echo "✅ Текущая уставка: ${CURRENT_SETPOINT}м"
else
    echo "❌ Не удалось получить текущую уставку"
    exit 1
fi

echo

# Тестируем изменение уставки
echo "🔧 Тестирование изменения уставки..."

# Тест 1: Установка уставки на 1.2м
echo "   Тест 1: Установка уставки на 1.2м..."
RESPONSE=$(curl -s -X POST "$API_BASE_URL/api/setpoint" \
  -H "Content-Type: application/json" \
  -d '{"setpoint": 1.2, "reason": "Тест 1 - автоматическое тестирование"}')
echo "   Ответ: $(echo $RESPONSE | jq -r '.message')"

sleep 1

# Тест 2: Установка уставки на 1.8м
echo "   Тест 2: Установка уставки на 1.8м..."
RESPONSE=$(curl -s -X POST "$API_BASE_URL/api/setpoint" \
  -H "Content-Type: application/json" \
  -d '{"setpoint": 1.8, "reason": "Тест 2 - автоматическое тестирование"}')
echo "   Ответ: $(echo $RESPONSE | jq -r '.message')"

sleep 1

# Тест 3: Установка уставки на 2.0м
echo "   Тест 3: Установка уставки на 2.0м..."
RESPONSE=$(curl -s -X POST "$API_BASE_URL/api/setpoint" \
  -H "Content-Type: application/json" \
  -d '{"setpoint": 2.0, "reason": "Тест 3 - автоматическое тестирование"}')
echo "   Ответ: $(echo $RESPONSE | jq -r '.message')"

echo

# Тестируем некорректные значения
echo "🚫 Тестирование некорректных значений..."

# Тест с отрицательным значением
echo "   Тест с отрицательным значением (-1.0)..."
RESPONSE=$(curl -s -X POST "$API_BASE_URL/api/setpoint" \
  -H "Content-Type: application/json" \
  -d '{"setpoint": -1.0, "reason": "Тест отрицательного значения"}')
if echo $RESPONSE | jq -e '.success == false' > /dev/null; then
    echo "   ✅ Корректно обработана ошибка: $(echo $RESPONSE | jq -r '.error')"
else
    echo "   ❌ Ошибка не была обработана"
fi

# Тест со слишком большим значением
echo "   Тест со слишком большим значением (5.0)..."
RESPONSE=$(curl -s -X POST "$API_BASE_URL/api/setpoint" \
  -H "Content-Type: application/json" \
  -d '{"setpoint": 5.0, "reason": "Тест большого значения"}')
if echo $RESPONSE | jq -e '.success == false' > /dev/null; then
    echo "   ✅ Корректно обработана ошибка: $(echo $RESPONSE | jq -r '.error')"
else
    echo "   ❌ Ошибка не была обработана"
fi

echo

# Получаем историю изменений
echo "📊 Получение истории изменений уставки..."
HISTORY=$(curl -s "$API_BASE_URL/api/setpoint/history")
COUNT=$(echo $HISTORY | jq -r '.count')
echo "✅ Найдено $COUNT записей в истории"

if [ "$COUNT" -gt 0 ]; then
    echo "   Последние изменения:"
    echo $HISTORY | jq -r '.data[] | "   📝 \(.timestamp): \(.old_setpoint)м → \(.new_setpoint)м (\(.change_reason))"'
fi

echo

# Возвращаем исходную уставку
echo "🔄 Возврат к исходной уставке ${CURRENT_SETPOINT}м..."
RESPONSE=$(curl -s -X POST "$API_BASE_URL/api/setpoint" \
  -H "Content-Type: application/json" \
  -d "{\"setpoint\": $CURRENT_SETPOINT, \"reason\": \"Возврат к исходному значению\"}")
echo "Ответ: $(echo $RESPONSE | jq -r '.message')"

echo
echo "✅ Тестирование завершено!"


