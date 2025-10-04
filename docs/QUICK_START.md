# 🚀 Система виртуального контроллера

## Быстрый старт

### 1. Клонирование и настройка

```bash
# Клонируйте репозиторий
git clone <repository-url>
cd virtual-controller-system

# Скопируйте файл с примерами переменных окружения
cp .env.example .env

# Отредактируйте файл .env
nano .env
```

### 2. Обязательные настройки

В файле `.env` **ОБЯЗАТЕЛЬНО** измените:

#### 🤖 Telegram Bot
```bash
# Получите токен от @BotFather в Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# Получите ваш Chat ID от @userinfobot
ADMIN_CHAT_ID=your_chat_id_here
```

#### 🗄️ База данных
```bash
# Измените пароли для безопасности
DB_PASSWORD=your_secure_password
DB_ADMIN_PASSWORD=your_secure_admin_password
```

### 3. Запуск системы

```bash
# Запустите все сервисы
docker-compose up -d

# Проверьте статус
docker-compose ps

# Проверьте логи Telegram бота
docker-compose logs telegram-bot
```

### 4. Проверка работы

- **Веб-интерфейс аналитики**: http://localhost:8080
- **OPC UA сервер**: opc.tcp://localhost:4840/freeopcua/server/
- **База данных**: localhost:5432

## 📋 Подробная настройка

### Получение Telegram Bot токена

1. Откройте Telegram и найдите [@BotFather](https://t.me/botfather)
2. Отправьте команду `/newbot`
3. Введите имя бота (например: "Virtual Controller Bot")
4. Введите username бота (например: "virtual_controller_bot")
5. Скопируйте полученный токен в `TELEGRAM_BOT_TOKEN`

### Получение Chat ID

1. Найдите [@userinfobot](https://t.me/userinfobot) в Telegram
2. Отправьте любое сообщение
3. Скопируйте ваш ID в `ADMIN_CHAT_ID`

### Настройка базы данных

Для продакшена обязательно измените:
- `DB_PASSWORD` - пароль пользователя базы данных
- `DB_ADMIN_PASSWORD` - пароль администратора PostgreSQL

## 🔧 Дополнительные настройки

### Уровни логирования
```bash
# Для отладки
LOGGING_LEVEL=DEBUG
DEBUG_MODE=true

# Для продакшена
LOGGING_LEVEL=INFO
DEBUG_MODE=false
```

### Порты
```bash
# Если порт 8080 занят
ANALYTICS_PORT=8081
```

## 🐛 Устранение проблем

### Telegram Bot не запускается
```bash
# Проверьте токен
docker-compose logs telegram-bot

# Убедитесь, что токен указан в .env
grep TELEGRAM_BOT_TOKEN .env
```

### База данных недоступна
```bash
# Проверьте статус БД
docker-compose logs database

# Перезапустите БД
docker-compose restart database
```

### OPC UA сервер не отвечает
```bash
# Проверьте логи сервера
docker-compose logs opcua-server

# Проверьте подключение
telnet localhost 4840
```

## 📚 Документация

- [Настройка переменных окружения](ENV_CONFIGURATION.md)
- [Интеграция с Telegram](TELEGRAM_INTEGRATION.md)
- [Архитектура системы](ARCHITECTURE.md)

## 🆘 Поддержка

При возникновении проблем:
1. Проверьте логи: `docker-compose logs <service-name>`
2. Убедитесь, что все переменные в `.env` настроены правильно
3. Проверьте, что порты не заняты другими приложениями
4. Создайте issue в репозитории с описанием проблемы
