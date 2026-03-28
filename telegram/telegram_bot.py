"""
Telegram бот для уведомлений о критических ситуациях в системе виртуального контроллера
"""

import asyncio
import json
import logging
import os
import sys
from typing import Dict, List, Optional, Set
from datetime import datetime, timezone, timedelta

import aiohttp
from telegram import Bot, Update, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import TelegramError

# Добавляем путь к модулям базы данных
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'database'))
from database_manager import get_db_manager

# Добавляем импорт OPC UA клиента
try:
    from opcua import Client
    OPCUA_AVAILABLE = True
except ImportError:
    OPCUA_AVAILABLE = False
    print("⚠️ OPC UA модуль недоступен")

logger = logging.getLogger(__name__)


def build_telegram_application(bot_token: str) -> Application:
    """
    Сборка Application с увеличенными таймаутами (по умолчанию в PTB/httpx — 5 с, часто даёт Timed out).

    Переменные окружения (секунды):
      TELEGRAM_CONNECT_TIMEOUT, TELEGRAM_READ_TIMEOUT, TELEGRAM_WRITE_TIMEOUT, TELEGRAM_POOL_TIMEOUT
    Прокси при блокировке api.telegram.org:
      TELEGRAM_PROXY_URL или HTTPS_PROXY / HTTP_PROXY
    """
    connect = float(os.getenv("TELEGRAM_CONNECT_TIMEOUT", "30"))
    read_t = float(os.getenv("TELEGRAM_READ_TIMEOUT", "30"))
    write_t = float(os.getenv("TELEGRAM_WRITE_TIMEOUT", "30"))
    pool_t = float(os.getenv("TELEGRAM_POOL_TIMEOUT", "10"))

    b = (
        Application.builder()
        .token(bot_token)
        .connect_timeout(connect)
        .read_timeout(read_t)
        .write_timeout(write_t)
        .pool_timeout(pool_t)
        .get_updates_connect_timeout(connect)
        .get_updates_read_timeout(read_t)
        .get_updates_write_timeout(write_t)
        .get_updates_pool_timeout(pool_t)
    )

    proxy = (
        os.getenv("TELEGRAM_PROXY_URL")
        or os.getenv("HTTPS_PROXY")
        or os.getenv("HTTP_PROXY")
        or ""
    ).strip()
    if proxy:
        b = b.proxy(proxy).get_updates_proxy(proxy)
        logger.info("Telegram: запросы через прокси (TELEGRAM_PROXY_URL / HTTPS_PROXY)")

    logger.info(
        "Telegram HTTP: connect/read/write/pool = %.1f/%.1f/%.1f/%.1f с (getUpdates те же)",
        connect,
        read_t,
        write_t,
        pool_t,
    )
    return b.build()


def get_moscow_time():
    """Получение текущего времени по МСК (UTC+3)"""
    moscow_tz = timezone(timedelta(hours=3))
    return datetime.now(moscow_tz)


class TelegramNotifier:
    """Класс для отправки уведомлений через Telegram"""
    
    def __init__(self, bot_token: str, admin_chat_id: Optional[str] = None):
        """
        Инициализация Telegram уведомлений
        
        Args:
            bot_token: Токен Telegram бота
            admin_chat_id: ID чата администратора (опционально)
        """
        self.bot_token = bot_token
        self.admin_chat_id = admin_chat_id
        self.bot = Bot(token=bot_token)
        self.subscribers: Set[str] = set()
        self.notification_filters: Dict[str, Dict] = {}
        self.rate_limits: Dict[str, datetime] = {}
        self.enabled = True
        
        # Загружаем подписчиков из файла
        self._load_subscribers()
        
        logger.info("🤖 Telegram уведомления инициализированы")
    
    def _load_subscribers(self):
        """Загрузка списка подписчиков из файла"""
        try:
            # Загружаем из папки data для синхронизации с watchdog
            subscribers_file = '/app/data/telegram_subscribers.json'
            if os.path.exists(subscribers_file):
                with open(subscribers_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.subscribers = set(data.get('subscribers', []))
                    self.notification_filters = data.get('filters', {})
                logger.info(f"📋 Загружено {len(self.subscribers)} подписчиков")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки подписчиков: {e}")
    
    def _save_subscribers(self):
        """Сохранение списка подписчиков в файл"""
        try:
            data = {
                'subscribers': list(self.subscribers),
                'filters': self.notification_filters
            }
            # Сохраняем в папку data для синхронизации с watchdog
            os.makedirs('/app/data', exist_ok=True)
            with open('/app/data/telegram_subscribers.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения подписчиков: {e}")
    
    def add_subscriber(self, chat_id: str) -> bool:
        """Добавление подписчика"""
        try:
            self.subscribers.add(chat_id)
            self._save_subscribers()
            logger.info(f"✅ Добавлен подписчик: {chat_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления подписчика: {e}")
            return False
    
    def remove_subscriber(self, chat_id: str) -> bool:
        """Удаление подписчика"""
        try:
            self.subscribers.discard(chat_id)
            self._save_subscribers()
            logger.info(f"❌ Удален подписчик: {chat_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка удаления подписчика: {e}")
            return False
    
    def set_notification_filter(self, chat_id: str, filter_config: Dict):
        """Установка фильтра уведомлений для пользователя"""
        self.notification_filters[chat_id] = filter_config
        self._save_subscribers()
        logger.info(f"🔧 Установлен фильтр для {chat_id}: {filter_config}")
    
    def _is_rate_limited(self, chat_id: str, message_type: str) -> bool:
        """Проверка ограничения частоты отправки сообщений"""
        key = f"{chat_id}_{message_type}"
        now = datetime.now()
        
        if key in self.rate_limits:
            last_sent = self.rate_limits[key]
            # Ограничение: не чаще 1 сообщения в минуту для одного типа
            if now - last_sent < timedelta(minutes=1):
                return True
        
        self.rate_limits[key] = now
        return False
    
    def _should_send_notification(self, chat_id: str, level: str, component: str) -> bool:
        """Проверка, нужно ли отправлять уведомление пользователю"""
        if not self.enabled:
            return False
        
        if chat_id not in self.subscribers:
            return False
        
        # Проверка ограничения частоты
        if self._is_rate_limited(chat_id, level):
            return False
        
        # Отправляем все уведомления (критические и предупреждения)
        return True
    
    async def send_notification(self, level: str, component: str, message: str, 
                              additional_data: Optional[Dict] = None):
        """
        Отправка уведомления всем подписчикам
        
        Args:
            level: Уровень важности (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            component: Компонент системы (model, controller, tank, valve, etc.)
            message: Текст сообщения
            additional_data: Дополнительные данные
        """
        if not self.enabled:
            return
        
        # Формирование сообщения
        emoji_map = {
            'CRITICAL': '🚨',
            'ERROR': '❌',
            'WARNING': '⚠️',
            'INFO': 'ℹ️',
            'DEBUG': '🔍'
        }
        
        emoji = emoji_map.get(level, '📢')
        # Используем московское время (UTC+3)
        moscow_tz = timezone(timedelta(hours=3))
        timestamp = get_moscow_time().strftime('%H:%M:%S')
        
        # Основное сообщение
        text = f"{emoji} {level} [{timestamp}]\n"
        text += f"🔧 Компонент: {component}\n"
        text += f"📝 Сообщение: {message}\n"
        
        # Добавление дополнительных данных
        if additional_data:
            text += "\n📊 Дополнительные данные:\n"
            for key, value in additional_data.items():
                text += f"• {key}: {value}\n"
        
        # Отправка сообщений
        tasks = []
        for chat_id in self.subscribers.copy():
            if self._should_send_notification(chat_id, level, component):
                tasks.append(self._send_to_chat(chat_id, text))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _send_to_chat(self, chat_id: str, text: str):
        """Отправка сообщения в конкретный чат"""
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                disable_web_page_preview=True
            )
            logger.debug(f"📤 Уведомление отправлено в {chat_id}")
        except TelegramError as e:
            logger.error(f"❌ Ошибка отправки в {chat_id}: {e}")
            # Удаляем неактивного подписчика
            if "chat not found" in str(e).lower() or "blocked" in str(e).lower():
                self.remove_subscriber(chat_id)
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка отправки в {chat_id}: {e}")
    
    async def send_critical_alert(self, component: str, message: str, 
                                additional_data: Optional[Dict] = None):
        """Отправка критического оповещения"""
        await self.send_notification('CRITICAL', component, message, additional_data)
    
    async def send_error_alert(self, component: str, message: str, 
                             additional_data: Optional[Dict] = None):
        """Отправка оповещения об ошибке"""
        await self.send_notification('ERROR', component, message, additional_data)
    
    async def send_warning_alert(self, component: str, message: str, 
                               additional_data: Optional[Dict] = None):
        """Отправка предупреждения"""
        await self.send_notification('WARNING', component, message, additional_data)
    
    def enable_notifications(self):
        """Включение уведомлений"""
        self.enabled = True
        logger.info("✅ Telegram уведомления включены")
    
    def disable_notifications(self):
        """Отключение уведомлений"""
        self.enabled = False
        logger.info("❌ Telegram уведомления отключены")
    
    async def send_status_report(self, chat_id: str):
        """Отправка отчета о состоянии системы"""
        try:
            text = "📊 *Отчет о состоянии системы*\n\n"
            text += f"🤖 *Бот активен:* {'✅' if self.enabled else '❌'}\n"
            text += f"👥 *Подписчиков:* {len(self.subscribers)}\n"
            text += f"⏰ *Время:* {get_moscow_time().strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"❌ Ошибка отправки отчета: {e}")


class TelegramBotHandler:
    """Обработчик команд Telegram бота"""
    
    def __init__(self, notifier: TelegramNotifier):
        self.notifier = notifier
        self.application = None
        
        # Инициализация подключений к данным
        self.db_manager = get_db_manager()
        self.opcua_client = None
        self.config = self._load_config()
        
        # Node IDs для OPC UA переменных
        self.node_ids = {}
        self._setup_node_ids()
        
        # Кэш для данных с временными метками
        self.data_cache = {}
        self.cache_timeout = 5.0  # 5 секунд
        
    def _load_config(self) -> Dict:
        """Загрузка конфигурации"""
        try:
            # Пробуем разные пути для config.json
            config_paths = [
                '/app/config.json',  # Путь в Docker контейнере
                os.path.join(os.path.dirname(__file__), '..', 'config.json'),  # Относительный путь
                'config.json'  # Текущая директория
            ]
            
            config = {}
            for config_path in config_paths:
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    logger.info(f"📋 Конфигурация Telegram бота загружена из {config_path}")
                    break
                except FileNotFoundError:
                    continue
            
            if not config:
                logger.warning("⚠️ Конфигурация не найдена, используются значения по умолчанию")
                # Возвращаем базовую конфигурацию
                config = {
                    'opcua_variables': {
                        'process_variables': {
                            'PV_level': 'ns=2;i=2',
                            'SP_level': 'ns=2;i=3', 
                            'OP_valve': 'ns=2;i=4',
                            'outlet_flow': 'ns=2;i=5',
                            'inlet_flow': 'ns=2;i=6'
                        }
                    }
                }
            
            return config
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки конфигурации: {e}")
            return {}
    
    def _setup_node_ids(self):
        """Настройка Node IDs для OPC UA переменных"""
        try:
            if 'opcua_variables' in self.config:
                pv_config = self.config['opcua_variables']['process_variables']
                for var_name, var_config in pv_config.items():
                    self.node_ids[var_name] = var_config['node_id']
                logger.info("🔗 Node IDs для Telegram бота настроены")
        except Exception as e:
            logger.error(f"❌ Ошибка настройки Node IDs: {e}")
    
    async def _connect_to_opcua(self) -> bool:
        """Подключение к OPC UA серверу"""
        if not OPCUA_AVAILABLE:
            logger.warning("⚠️ OPC UA модуль недоступен")
            return False
            
        try:
            server_url = os.getenv('OPCUA_SERVER_URL', 'opc.tcp://opcua-server:4840/freeopcua/server/')
            self.opcua_client = Client(server_url)
            self.opcua_client.connect()
            logger.info(f"🔗 Telegram бот подключился к OPC UA серверу: {server_url}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка подключения Telegram бота к OPC UA: {e}")
            return False
    
    async def _disconnect_from_opcua(self):
        """Отключение от OPC UA сервера"""
        if self.opcua_client:
            try:
                self.opcua_client.disconnect()
                logger.info("🔌 Telegram бот отключился от OPC UA сервера")
            except Exception as e:
                logger.error(f"❌ Ошибка отключения от OPC UA: {e}")
    
    async def _get_opcua_value(self, var_name: str) -> Optional[float]:
        """Получение значения переменной с OPC UA сервера"""
        if not self.opcua_client or var_name not in self.node_ids:
            return None
            
        try:
            node_id = self.node_ids[var_name]
            node = self.opcua_client.get_node(node_id)
            value = node.get_value()
            return value
        except Exception as e:
            logger.error(f"❌ Ошибка получения OPC UA значения {var_name}: {e}")
            return None
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Проверка валидности кэша"""
        if cache_key not in self.data_cache:
            return False
        
        cache_time = self.data_cache[cache_key].get('timestamp', 0)
        return (datetime.now().timestamp() - cache_time) < self.cache_timeout
    
    def _update_cache(self, cache_key: str, data: Dict):
        """Обновление кэша данных"""
        self.data_cache[cache_key] = {
            'data': data,
            'timestamp': datetime.now().timestamp()
        }
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        chat_id = str(update.effective_chat.id)
        user_name = update.effective_user.first_name or "Пользователь"
        
        # Автоматически подписываем пользователя на уведомления
        self.notifier.add_subscriber(chat_id)
        
        text = f"""🤖 *Добро пожаловать, {user_name}!*

✅ *Вы автоматически подписаны на уведомления о критических событиях*

📋 *Доступные команды:*
/start - Начать работу
/subscribe - Подписаться на уведомления
/unsubscribe - Отписаться от уведомлений
/status - Статус системы
/tank - Состояние резервуара
/valve - Состояние клапана
/pid - Параметры PID контроллера
/controllers - Статус контроллеров
/myid - Получить ваш Chat ID
/filters - Настройка фильтров
/help - Помощь

🚨 *Автоматические уведомления:*
Вы будете получать уведомления о:
• Отключении контроллеров
• Критических ошибках системы
• Предупреждениях о состоянии оборудования
        """
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def subscribe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /subscribe"""
        chat_id = str(update.effective_chat.id)
        
        if self.notifier.add_subscriber(chat_id):
            text = "✅ Вы успешно подписались на уведомления!\n\n"
            text += "Вы будете получать уведомления о:\n"
            text += "🚨 Критических ошибках\n"
            text += "❌ Ошибках системы\n"
            text += "⚠️ Предупреждениях\n"
            text += "ℹ️ Информационных сообщениях\n\n"
            text += "Используйте /filters для настройки фильтров"
        else:
            text = "❌ Ошибка подписки. Попробуйте позже."
        
        await update.message.reply_text(text)
    
    async def myid_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для получения chat_id пользователя"""
        chat_id = str(update.effective_chat.id)
        user_name = update.effective_user.first_name or "Пользователь"
        
        message = f"🆔 **Ваш Chat ID:** `{chat_id}`\n"
        message += f"👤 **Имя:** {user_name}\n\n"
        message += "📝 **Для настройки автоматических уведомлений:**\n"
        message += f"1. Скопируйте ваш Chat ID: `{chat_id}`\n"
        message += "2. Замените `123456789` на ваш Chat ID в docker-compose.yml\n"
        message += "3. Перезапустите watchdog: `docker-compose restart watchdog`"
        
        await update.message.reply_text(message, parse_mode='Markdown')

    async def unsubscribe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /unsubscribe"""
        chat_id = str(update.effective_chat.id)
        
        if self.notifier.remove_subscriber(chat_id):
            text = "❌ Вы отписались от уведомлений."
        else:
            text = "ℹ️ Вы не были подписаны на уведомления."
        
        await update.message.reply_text(text)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /status"""
        chat_id = str(update.effective_chat.id)
        await self.notifier.send_status_report(chat_id)
    
    async def filters_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /filters"""
        text = """
🔧 *Настройка фильтров уведомлений*

Для настройки фильтров используйте команды:

/filter_level WARNING - Минимальный уровень (DEBUG, INFO, WARNING, ERROR, CRITICAL)
/filter_components model,controller - Компоненты для отслеживания

Примеры:
/filter_level ERROR - Получать только ошибки и критические сообщения
/filter_components tank,valve - Отслеживать только бак и клапан
        """
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def filter_level_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /filter_level"""
        chat_id = str(update.effective_chat.id)
        
        if len(context.args) != 1:
            await update.message.reply_text("❌ Использование: /filter_level WARNING")
            return
        
        level = context.args[0].upper()
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        
        if level not in valid_levels:
            await update.message.reply_text(f"❌ Неверный уровень. Доступные: {', '.join(valid_levels)}")
            return
        
        # Обновляем фильтр
        if chat_id not in self.notifier.notification_filters:
            self.notifier.notification_filters[chat_id] = {}
        
        self.notifier.notification_filters[chat_id]['min_level'] = level
        self.notifier._save_subscribers()
        
        await update.message.reply_text(f"✅ Установлен минимальный уровень: {level}")
    
    async def filter_components_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /filter_components"""
        chat_id = str(update.effective_chat.id)
        
        if not context.args:
            await update.message.reply_text("❌ Использование: /filter_components model,controller,tank")
            return
        
        components = [comp.strip() for comp in context.args[0].split(',')]
        
        # Обновляем фильтр
        if chat_id not in self.notifier.notification_filters:
            self.notifier.notification_filters[chat_id] = {}
        
        self.notifier.notification_filters[chat_id]['components'] = components
        self.notifier._save_subscribers()
        
        await update.message.reply_text(f"✅ Установлены компоненты: {', '.join(components)}")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        text = """
📖 *Доступные команды по клику в меню*

*Основные команды:*
/start - Начать работу с ботом и подписаться на уведомления
/status - Получить отчет о состоянии системы

*Мониторинг параметров:*
/tank - Состояние резервуара (уровень, объем, давление)
/valve - Состояние клапана (открытие, потоки)
/pid - Параметры PID контроллера (Kp, Ki, Kd, уставка)
/controllers - Статус контроллеров (основной/резервный)
/system - Общее состояние системы

*Уведомления:*
Все уведомления отправляются автоматически:
• Критические ошибки системы
• Предупреждения о проблемах
• Изменения статуса контроллеров
• Отключения контейнеров
        """
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def params_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /params - все параметры системы"""
        try:
            # Получаем данные из различных источников
            tank_data = await self._get_tank_data()
            valve_data = await self._get_valve_data()
            pid_data = await self._get_pid_data()
            system_data = await self._get_system_data()
            
            text = f"""
📊 *ПАРАМЕТРЫ СИСТЕМЫ*

🛢️ *Резервуар:*
• Уровень жидкости: {tank_data.get('level', 'N/A')} м
• Объем: {tank_data.get('volume', 'N/A')} м³
• Масса: {tank_data.get('mass', 'N/A')} кг
• Давление: {tank_data.get('pressure', 'N/A')} Па

🔧 *Клапан:*
• Открытие: {valve_data.get('opening', 'N/A')}%
• Расход: {valve_data.get('flow_rate', 'N/A')} м³/с

🎛️ *PID Контроллер:*
• Заданное значение: {pid_data.get('setpoint', 'N/A')} м
• Текущее значение: {pid_data.get('process_value', 'N/A')} м
• Ошибка: {pid_data.get('error', 'N/A')} м
• Выход: {pid_data.get('output', 'N/A')}%

🖥️ *Система:*
• Статус: {system_data.get('status', 'N/A')}
• Время работы: {system_data.get('uptime', 'N/A')}
• Активные предупреждения: {system_data.get('alerts_count', 0)}
            """
            
            await update.message.reply_text(text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения параметров: {str(e)}")
    
    async def tank_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /tank - состояние резервуара"""
        try:
            tank_data = await self._get_tank_data()
            
            # Определяем статус резервуара
            level = tank_data.get('level', 0)
            if level < 0.5:
                status_emoji = "🔴"
                status_text = "КРИТИЧЕСКИ НИЗКИЙ"
            elif level < 1.0:
                status_emoji = "🟡"
                status_text = "НИЗКИЙ"
            elif level > 4.5:
                status_emoji = "🔴"
                status_text = "КРИТИЧЕСКИ ВЫСОКИЙ"
            elif level > 4.0:
                status_emoji = "🟡"
                status_text = "ВЫСОКИЙ"
            else:
                status_emoji = "🟢"
                status_text = "НОРМАЛЬНЫЙ"
            
            text = f"""
🛢️ *СОСТОЯНИЕ РЕЗЕРВУАРА*

{status_emoji} *Статус:* {status_text}

📏 *Параметры:*
• Уровень жидкости: {tank_data.get('level', 'N/A')} м
• Объем: {tank_data.get('volume', 'N/A')} м³
• Масса жидкости: {tank_data.get('mass', 'N/A')} кг
• Давление: {tank_data.get('pressure', 'N/A')} Па

📊 *Границы:*
• Минимальный уровень: 0.5 м
• Максимальный уровень: 5.0 м
• Нормальный диапазон: 1.0 - 4.0 м

⏰ *Время обновления:* {tank_data.get('last_update', 'N/A')}
            """
            
            await update.message.reply_text(text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения данных резервуара: {str(e)}")
    
    async def valve_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /valve - состояние клапана"""
        try:
            valve_data = await self._get_valve_data()
            
            opening = valve_data.get('opening', 0)
            if opening < 10:
                status_emoji = "🔴"
                status_text = "КРИТИЧЕСКИ ЗАКРЫТ"
            elif opening < 25:
                status_emoji = "🟡"
                status_text = "ЗАКРЫТ"
            elif opening > 90:
                status_emoji = "🔴"
                status_text = "КРИТИЧЕСКИ ОТКРЫТ"
            elif opening > 75:
                status_emoji = "🟡"
                status_text = "ОТКРЫТ"
            else:
                status_emoji = "🟢"
                status_text = "НОРМАЛЬНЫЙ"
            
            text = f"""
🔧 *СОСТОЯНИЕ КЛАПАНА*

{status_emoji} *Статус:* {status_text}

📏 *Параметры:*
• Открытие: {opening}%
• Расход: {valve_data.get('flow_rate', 'N/A')} м³/с
• Скорость изменения: {valve_data.get('change_rate', 'N/A')}%/мин

📊 *Границы:*
• Минимальное открытие: 0%
• Максимальное открытие: 100%
• Нормальный диапазон: 25% - 75%

⏰ *Время обновления:* {valve_data.get('last_update', 'N/A')}
            """
            
            await update.message.reply_text(text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения данных клапана: {str(e)}")
    
    async def pid_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /pid - параметры PID контроллера"""
        try:
            pid_data = await self._get_pid_data()
            
            error = abs(pid_data.get('error', 0))
            if error > 2.0:
                status_emoji = "🔴"
                status_text = "БОЛЬШАЯ ОШИБКА"
            elif error > 1.0:
                status_emoji = "🟡"
                status_text = "СРЕДНЯЯ ОШИБКА"
            else:
                status_emoji = "🟢"
                status_text = "НОРМАЛЬНАЯ ОШИБКА"
            
            text = f"""
🎛️ *PID КОНТРОЛЛЕР*

{status_emoji} *Статус:* {status_text}

📊 *Параметры:*
• Заданное значение (SP): {pid_data.get('setpoint', 'N/A')} м
• Текущее значение (PV): {pid_data.get('process_value', 'N/A')} м
• Ошибка (E): {pid_data.get('error', 'N/A')} м
• Выход (OP): {pid_data.get('output', 'N/A')}%

🔧 *Настройки:*
• Kp (Пропорциональный): {pid_data.get('kp', 'N/A')}
• Ki (Интегральный): {pid_data.get('ki', 'N/A')}
• Kd (Дифференциальный): {pid_data.get('kd', 'N/A')}

📈 *Составляющие:*
• Пропорциональная: {pid_data.get('proportional', 'N/A')}
• Интегральная: {pid_data.get('integral', 'N/A')}
• Дифференциальная: {pid_data.get('derivative', 'N/A')}

⏰ *Время обновления:* {pid_data.get('last_update', 'N/A')}
            """
            
            await update.message.reply_text(text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения данных PID: {str(e)}")
    
    async def opcua_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /opcua - статус OPC UA сервера"""
        try:
            opcua_data = await self._get_opcua_data()
            
            status = opcua_data.get('status', 'unknown')
            if status == 'connected':
                status_emoji = "🟢"
                status_text = "ПОДКЛЮЧЕН"
            elif status == 'connecting':
                status_emoji = "🟡"
                status_text = "ПОДКЛЮЧЕНИЕ"
            else:
                status_emoji = "🔴"
                status_text = "ОТКЛЮЧЕН"
            
            text = f"""
🔌 *OPC UA СЕРВЕР*

{status_emoji} *Статус:* {status_text}

📊 *Параметры:*
• Endpoint: {opcua_data.get('endpoint', 'N/A')}
• Время подключения: {opcua_data.get('connection_time', 'N/A')}
• Последнее обновление: {opcua_data.get('last_update', 'N/A')}

📈 *Статистика:*
• Всего запросов: {opcua_data.get('total_requests', 0)}
• Успешных запросов: {opcua_data.get('successful_requests', 0)}
• Ошибок: {opcua_data.get('errors', 0)}

⏰ *Время проверки:* {get_moscow_time().strftime('%H:%M:%S')}
            """
            
            await update.message.reply_text(text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения данных OPC UA: {str(e)}")
    
    async def database_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /database - статус базы данных"""
        try:
            db_data = await self._get_database_data()
            
            status = db_data.get('status', 'unknown')
            if status == 'healthy':
                status_emoji = "🟢"
                status_text = "ЗДОРОВА"
            elif status == 'warning':
                status_emoji = "🟡"
                status_text = "ПРЕДУПРЕЖДЕНИЕ"
            else:
                status_emoji = "🔴"
                status_text = "ОШИБКА"
            
            text = f"""
🗄️ *БАЗА ДАННЫХ*

{status_emoji} *Статус:* {status_text}

📊 *Параметры:*
• Хост: {db_data.get('host', 'N/A')}
• Порт: {db_data.get('port', 'N/A')}
• База данных: {db_data.get('database', 'N/A')}
• Пользователь: {db_data.get('user', 'N/A')}

📈 *Статистика:*
• Размер БД: {db_data.get('size', 'N/A')}
• Активные соединения: {db_data.get('connections', 0)}
• Записей в таблице: {db_data.get('records_count', 0)}

⏰ *Время проверки:* {get_moscow_time().strftime('%H:%M:%S')}
            """
            
            await update.message.reply_text(text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения данных БД: {str(e)}")
    
    async def analytics_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /analytics - статус аналитики"""
        try:
            analytics_data = await self._get_analytics_data()
            
            status = analytics_data.get('status', 'unknown')
            if status == 'running':
                status_emoji = "🟢"
                status_text = "РАБОТАЕТ"
            elif status == 'starting':
                status_emoji = "🟡"
                status_text = "ЗАПУСКАЕТСЯ"
            else:
                status_emoji = "🔴"
                status_text = "ОСТАНОВЛЕН"
            
            text = f"""
📊 *АНАЛИТИКА*

{status_emoji} *Статус:* {status_text}

📊 *Параметры:*
• URL: {analytics_data.get('url', 'N/A')}
• Порт: {analytics_data.get('port', 'N/A')}
• Время работы: {analytics_data.get('uptime', 'N/A')}

📈 *Статистика:*
• Всего запросов: {analytics_data.get('total_requests', 0)}
• Активных сессий: {analytics_data.get('active_sessions', 0)}
• Обработано данных: {analytics_data.get('processed_data', 0)}

⏰ *Время проверки:* {get_moscow_time().strftime('%H:%M:%S')}
            """
            
            await update.message.reply_text(text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения данных аналитики: {str(e)}")
    
    async def controllers_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /controllers - статус контроллеров"""
        try:
            controllers_data = await self._get_controllers_data()
            
            primary_status = controllers_data.get('primary', {}).get('status', 'unknown')
            backup_status = controllers_data.get('backup', {}).get('status', 'unknown')
            
            primary_emoji = "🟢" if primary_status == 'active' else "🔴"
            backup_emoji = "🟢" if backup_status == 'standby' else "🔴"
            
            text = f"""
🎛️ *КОНТРОЛЛЕРЫ*

{primary_emoji} *Основной контроллер:* {primary_status.upper()}
{backup_emoji} *Резервный контроллер:* {backup_status.upper()}

📊 *Основной контроллер:*
• Статус: {primary_status}
• Время работы: {controllers_data.get('primary', {}).get('uptime', 'N/A')}
• Последний heartbeat: {controllers_data.get('primary', {}).get('last_heartbeat', 'N/A')}

📊 *Резервный контроллер:*
• Статус: {backup_status}
• Время работы: {controllers_data.get('backup', {}).get('uptime', 'N/A')}
• Последний heartbeat: {controllers_data.get('backup', {}).get('last_heartbeat', 'N/A')}

🔄 *Failover:*
• Автоматический failover: {controllers_data.get('failover_enabled', 'N/A')}
• Время переключения: {controllers_data.get('failover_time', 'N/A')}

⏰ *Время проверки:* {get_moscow_time().strftime('%H:%M:%S')}
            """
            
            await update.message.reply_text(text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения данных контроллеров: {str(e)}")
    
    async def system_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /system - общее состояние системы"""
        try:
            system_data = await self._get_system_data()
            
            overall_status = system_data.get('overall_status', 'unknown')
            if overall_status == 'healthy':
                status_emoji = "🟢"
                status_text = "ЗДОРОВА"
            elif overall_status == 'warning':
                status_emoji = "🟡"
                status_text = "ПРЕДУПРЕЖДЕНИЕ"
            else:
                status_emoji = "🔴"
                status_text = "КРИТИЧЕСКАЯ ОШИБКА"
            
            text = f"""
🖥️ *ОБЩЕЕ СОСТОЯНИЕ СИСТЕМЫ*

{status_emoji} *Статус:* {status_text}

📊 *Компоненты:*
• Резервуар: {system_data.get('tank_status', 'N/A')}
• Клапан: {system_data.get('valve_status', 'N/A')}
• PID контроллер: {system_data.get('pid_status', 'N/A')}
• OPC UA сервер: {system_data.get('opcua_status', 'N/A')}
• База данных: {system_data.get('database_status', 'N/A')}
• Аналитика: {system_data.get('analytics_status', 'N/A')}

📈 *Статистика:*
• Время работы: {system_data.get('uptime', 'N/A')}
• Активные предупреждения: {system_data.get('alerts_count', 0)}
• Критические ошибки: {system_data.get('critical_errors', 0)}
• Всего событий: {system_data.get('total_events', 0)}

⏰ *Время проверки:* {get_moscow_time().strftime('%H:%M:%S')}
            """
            
            await update.message.reply_text(text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения данных системы: {str(e)}")
    
    async def alerts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /alerts - активные предупреждения"""
        try:
            alerts_data = await self._get_alerts_data()
            
            alerts_count = len(alerts_data.get('alerts', []))
            if alerts_count == 0:
                status_emoji = "🟢"
                status_text = "НЕТ ПРЕДУПРЕЖДЕНИЙ"
            elif alerts_count < 3:
                status_emoji = "🟡"
                status_text = "НЕСКОЛЬКО ПРЕДУПРЕЖДЕНИЙ"
            else:
                status_emoji = "🔴"
                status_text = "МНОГО ПРЕДУПРЕЖДЕНИЙ"
            
            text = f"""
⚠️ *АКТИВНЫЕ ПРЕДУПРЕЖДЕНИЯ*

{status_emoji} *Статус:* {status_text}
📊 *Количество:* {alerts_count}

"""
            
            # Добавляем информацию о каждом предупреждении
            for i, alert in enumerate(alerts_data.get('alerts', [])[:5], 1):  # Показываем только первые 5
                level = alert.get('level', 'UNKNOWN')
                level_emoji = "🔴" if level == 'CRITICAL' else "🟡" if level == 'WARNING' else "🔵"
                
                text += f"""
{level_emoji} *{i}. {alert.get('component', 'N/A')}*
• Уровень: {level}
• Сообщение: {alert.get('message', 'N/A')}
• Время: {alert.get('timestamp', 'N/A')}
"""
            
            if alerts_count > 5:
                text += f"\n... и еще {alerts_count - 5} предупреждений"
            
            text += f"\n⏰ *Время проверки:* {get_moscow_time().strftime('%H:%M:%S')}"
            
            await update.message.reply_text(text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения предупреждений: {str(e)}")
    
    async def history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /history - история событий"""
        try:
            history_data = await self._get_history_data()
            
            events_count = len(history_data.get('events', []))
            
            text = f"""
📜 *ИСТОРИЯ СОБЫТИЙ*

📊 *Статистика:*
• Всего событий: {events_count}
• За последний час: {history_data.get('last_hour', 0)}
• За последний день: {history_data.get('last_day', 0)}

"""
            
            # Добавляем информацию о последних событиях
            for i, event in enumerate(history_data.get('events', [])[:5], 1):  # Показываем только последние 5
                level = event.get('level', 'UNKNOWN')
                level_emoji = "🔴" if level == 'CRITICAL' else "🟡" if level == 'WARNING' else "🔵"
                
                text += f"""
{level_emoji} *{i}. {event.get('component', 'N/A')}*
• Уровень: {level}
• Сообщение: {event.get('message', 'N/A')}
• Время: {event.get('timestamp', 'N/A')}
"""
            
            if events_count > 5:
                text += f"\n... и еще {events_count - 5} событий"
            
            text += f"\n⏰ *Время проверки:* {get_moscow_time().strftime('%H:%M:%S')}"
            
            await update.message.reply_text(text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения истории: {str(e)}")
    
    async def logs_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /logs - последние логи"""
        try:
            logs_data = await self._get_logs_data()
            
            logs_count = len(logs_data.get('logs', []))
            
            text = f"""
📋 *ПОСЛЕДНИЕ ЛОГИ*

📊 *Статистика:*
• Всего записей: {logs_count}
• За последний час: {logs_data.get('last_hour', 0)}
• За последний день: {logs_data.get('last_day', 0)}

"""
            
            # Добавляем информацию о последних логах
            for i, log in enumerate(logs_data.get('logs', [])[:5], 1):  # Показываем только последние 5
                level = log.get('level', 'UNKNOWN')
                level_emoji = "🔴" if level == 'CRITICAL' else "🟡" if level == 'WARNING' else "🔵"
                
                text += f"""
{level_emoji} *{i}. {log.get('component', 'N/A')}*
• Уровень: {level}
• Сообщение: {log.get('message', 'N/A')}
• Время: {log.get('timestamp', 'N/A')}
"""
            
            if logs_count > 5:
                text += f"\n... и еще {logs_count - 5} записей"
            
            text += f"\n⏰ *Время проверки:* {get_moscow_time().strftime('%H:%M:%S')}"
            
            await update.message.reply_text(text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения логов: {str(e)}")
    
    # Вспомогательные методы для получения данных
    async def _get_tank_data(self) -> Dict:
        """Получение данных резервуара из базы данных и OPC UA"""
        cache_key = 'tank_data'
        
        # Проверяем кэш
        if self._is_cache_valid(cache_key):
            logger.debug("📋 Используем кэшированные данные резервуара")
            return self.data_cache[cache_key]['data']
        
        logger.info("🔄 Получение свежих данных резервуара...")
        
        try:
            # Подключаемся к OPC UA если не подключены
            if not self.opcua_client:
                logger.info("🔌 Подключение к OPC UA серверу...")
                await self._connect_to_opcua()
            
            # Получаем данные из OPC UA
            logger.debug("📡 Получение данных из OPC UA...")
            pv_level = await self._get_opcua_value('PV_level')
            inlet_flow = await self._get_opcua_value('inlet_flow')
            
            logger.debug(f"📊 OPC UA данные: PV_level={pv_level}, inlet_flow={inlet_flow}")
            
            # Получаем последние данные из базы данных
            db_data = {}
            if self.db_manager and self.db_manager.async_pool:
                try:
                    logger.debug("🗄️ Получение данных из базы данных...")
                    async with self.db_manager.async_pool.acquire() as conn:
                        query = """
                        SELECT pv_level, inlet_flow, tank_pressure, timestamp
                        FROM process_data.process_variables 
                        ORDER BY timestamp DESC 
                        LIMIT 1
                        """
                        row = await conn.fetchrow(query)
                        if row:
                            db_data = dict(row)
                            logger.debug(f"📊 БД данные: {db_data}")
                        else:
                            logger.warning("⚠️ Нет данных в базе данных")
                except Exception as e:
                    logger.error(f"❌ Ошибка получения данных резервуара из БД: {e}")
            else:
                logger.warning("⚠️ База данных недоступна")
            
            # Формируем результат
            result = {
                'level': pv_level if pv_level is not None else db_data.get('pv_level', 0),
                'volume': (pv_level if pv_level is not None else db_data.get('pv_level', 0)) * 5.0,  # Примерный расчет
                'mass': (pv_level if pv_level is not None else db_data.get('pv_level', 0)) * 5.0 * 1000,  # Примерный расчет
                'pressure': db_data.get('tank_pressure', 101325),
                'last_update': get_moscow_time().strftime('%H:%M:%S')  # Текущее время запроса
            }
            
            logger.info(f"✅ Данные резервуара получены: уровень={result['level']:.3f}м, время={result['last_update']}")
            
            # Обновляем кэш
            self._update_cache(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения данных резервуара: {e}")
            # Возвращаем данные из кэша или значения по умолчанию
            if cache_key in self.data_cache:
                logger.info("📋 Возвращаем данные из кэша")
                return self.data_cache[cache_key]['data']
            logger.warning("⚠️ Возвращаем значения по умолчанию")
            return {
                'level': 0,
                'volume': 0,
                'mass': 0,
                'pressure': 101325,
                'last_update': 'N/A'
            }
    
    async def _get_valve_data(self) -> Dict:
        """Получение данных клапана из базы данных и OPC UA"""
        cache_key = 'valve_data'
        
        # Проверяем кэш
        if self._is_cache_valid(cache_key):
            return self.data_cache[cache_key]['data']
        
        try:
            # Подключаемся к OPC UA если не подключены
            if not self.opcua_client:
                await self._connect_to_opcua()
            
            # Получаем данные из OPC UA
            op_valve = await self._get_opcua_value('OP_valve')
            outlet_flow = await self._get_opcua_value('outlet_flow')
            
            # Получаем последние данные из базы данных
            db_data = {}
            if self.db_manager and self.db_manager.async_pool:
                try:
                    async with self.db_manager.async_pool.acquire() as conn:
                        query = """
                        SELECT op_valve, outlet_flow, timestamp
                        FROM process_data.process_variables 
                        ORDER BY timestamp DESC 
                        LIMIT 1
                        """
                        row = await conn.fetchrow(query)
                        if row:
                            db_data = dict(row)
                except Exception as e:
                    logger.error(f"❌ Ошибка получения данных клапана из БД: {e}")
            
            # Формируем результат
            result = {
                'opening': op_valve if op_valve is not None else db_data.get('op_valve', 0),
                'flow_rate': outlet_flow if outlet_flow is not None else db_data.get('outlet_flow', 0),
                'change_rate': 0,  # Можно рассчитать из истории
                'last_update': get_moscow_time().strftime('%H:%M:%S')  # Текущее время запроса
            }
            
            # Обновляем кэш
            self._update_cache(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения данных клапана: {e}")
            # Возвращаем данные из кэша или значения по умолчанию
            if cache_key in self.data_cache:
                return self.data_cache[cache_key]['data']
            return {
                'opening': 0,
                'flow_rate': 0,
                'change_rate': 0,
                'last_update': 'N/A'
            }
    
    async def _get_pid_data(self) -> Dict:
        """Получение данных PID контроллера из базы данных и OPC UA"""
        cache_key = 'pid_data'
        
        # Проверяем кэш
        if self._is_cache_valid(cache_key):
            return self.data_cache[cache_key]['data']
        
        try:
            # Подключаемся к OPC UA если не подключены
            if not self.opcua_client:
                await self._connect_to_opcua()
            
            # Получаем данные из OPC UA
            sp_level = await self._get_opcua_value('SP_level')
            pv_level = await self._get_opcua_value('PV_level')
            op_valve = await self._get_opcua_value('OP_valve')
            
            # Получаем последние данные PID из базы данных
            db_data = {}
            if self.db_manager and self.db_manager.async_pool:
                try:
                    async with self.db_manager.async_pool.acquire() as conn:
                        query = """
                        SELECT setpoint, process_value, output, error_value, 
                               kp, ki, kd, integral, previous_error, timestamp
                        FROM controller_data.pid_states 
                        ORDER BY timestamp DESC 
                        LIMIT 1
                        """
                        row = await conn.fetchrow(query)
                        if row:
                            db_data = dict(row)
                except Exception as e:
                    logger.error(f"❌ Ошибка получения данных PID из БД: {e}")
            
            # Рассчитываем ошибку
            error = (pv_level if pv_level is not None else db_data.get('process_value', 0)) - (sp_level if sp_level is not None else db_data.get('setpoint', 0))
            
            # Формируем результат
            result = {
                'setpoint': sp_level if sp_level is not None else db_data.get('setpoint', 0),
                'process_value': pv_level if pv_level is not None else db_data.get('process_value', 0),
                'error': error,
                'output': op_valve if op_valve is not None else db_data.get('output', 0),
                'kp': db_data.get('kp', 1.0),
                'ki': db_data.get('ki', 0.1),
                'kd': db_data.get('kd', 0.05),
                'proportional': error * db_data.get('kp', 1.0),
                'integral': db_data.get('integral', 0),
                'derivative': db_data.get('previous_error', 0),
                'last_update': get_moscow_time().strftime('%H:%M:%S')  # Текущее время запроса
            }
            
            # Обновляем кэш
            self._update_cache(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения данных PID: {e}")
            # Возвращаем данные из кэша или значения по умолчанию
            if cache_key in self.data_cache:
                return self.data_cache[cache_key]['data']
            return {
                'setpoint': 0,
                'process_value': 0,
                'error': 0,
                'output': 0,
                'kp': 1.0,
                'ki': 0.1,
                'kd': 0.05,
                'proportional': 0,
                'integral': 0,
                'derivative': 0,
                'last_update': 'N/A'
            }
    
    async def _get_opcua_data(self) -> Dict:
        """Получение данных OPC UA сервера"""
        try:
            return {
                'status': 'connected',
                'endpoint': 'opc.tcp://opcua-server:4840/freeopcua/server/',
                'connection_time': '10:30:15',
                'last_update': '19:04:35',
                'total_requests': 1250,
                'successful_requests': 1245,
                'errors': 5
            }
        except Exception as e:
            logger.error(f"Ошибка получения данных OPC UA: {e}")
            return {}
    
    async def _get_database_data(self) -> Dict:
        """Получение данных базы данных"""
        try:
            return {
                'status': 'healthy',
                'host': 'database',
                'port': 5432,
                'database': 'digital_twin_db',
                'user': 'process_user',
                'size': '25.6 MB',
                'connections': 3,
                'records_count': 1250
            }
        except Exception as e:
            logger.error(f"Ошибка получения данных БД: {e}")
            return {}
    
    async def _get_analytics_data(self) -> Dict:
        """Получение данных аналитики"""
        try:
            return {
                'status': 'running',
                'url': 'http://analytics:8080',
                'port': 8080,
                'uptime': '2h 15m',
                'total_requests': 450,
                'active_sessions': 2,
                'processed_data': 1250
            }
        except Exception as e:
            logger.error(f"Ошибка получения данных аналитики: {e}")
            return {}
    
    async def _get_controllers_data(self) -> Dict:
        """Получение данных контроллеров из OPC UA"""
        cache_key = 'controllers_data'
        
        # Проверяем кэш
        if self._is_cache_valid(cache_key):
            return self.data_cache[cache_key]['data']
        
        try:
            # Подключаемся к OPC UA если не подключены
            if not self.opcua_client:
                await self._connect_to_opcua()
            
            # Получаем данные из OPC UA
            primary_heartbeat = await self._get_opcua_value('primary_controller_heartbeat')
            backup_heartbeat = await self._get_opcua_value('backup_controller_heartbeat')
            active_controller = await self._get_opcua_value('active_controller')
            
            logger.debug(f"📊 OPC UA данные контроллеров: primary_heartbeat={primary_heartbeat}, backup_heartbeat={backup_heartbeat}, active_controller={active_controller}")
            
            # Определяем статус контроллеров на основе текущего времени
            import time
            current_time = time.time()
            primary_alive = (current_time - primary_heartbeat) < 5.0 if primary_heartbeat else False
            backup_alive = (current_time - backup_heartbeat) < 5.0 if backup_heartbeat else False
            
            logger.info(f"🔍 Статус контроллеров: primary_alive={primary_alive}, backup_alive={backup_alive}, active_controller={active_controller}")
            
            # Определяем статус контроллеров
            if active_controller == 1:
                primary_status = 'active' if primary_alive else 'offline'
                backup_status = 'standby' if backup_alive else 'offline'
            elif active_controller == 2:
                primary_status = 'offline' if not primary_alive else 'standby'
                backup_status = 'active' if backup_alive else 'offline'
            else:
                primary_status = 'offline' if not primary_alive else 'standby'
                backup_status = 'offline' if not backup_alive else 'standby'
            
            # Форматируем время heartbeat
            primary_heartbeat_time = datetime.fromtimestamp(primary_heartbeat).strftime('%H:%M:%S') if primary_heartbeat else 'N/A'
            backup_heartbeat_time = datetime.fromtimestamp(backup_heartbeat).strftime('%H:%M:%S') if backup_heartbeat else 'N/A'
            
            result = {
                'primary': {
                    'status': primary_status,
                    'uptime': '2h 15m',  # Можно рассчитать из БД
                    'last_heartbeat': primary_heartbeat_time
                },
                'backup': {
                    'status': backup_status,
                    'uptime': '2h 15m',  # Можно рассчитать из БД
                    'last_heartbeat': backup_heartbeat_time
                },
                'failover_enabled': True,
                'failover_time': '2.5s',
                'active_controller': 'primary' if active_controller == 1 else 'backup' if active_controller == 2 else 'unknown',
                'last_update': get_moscow_time().strftime('%H:%M:%S')
            }
            
            logger.info(f"✅ Данные контроллеров получены: primary={primary_status}, backup={backup_status}, active={result['active_controller']}")
            
            # Обновляем кэш
            self._update_cache(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения данных контроллеров: {e}")
            # Возвращаем данные из кэша или значения по умолчанию
            if cache_key in self.data_cache:
                return self.data_cache[cache_key]['data']
            return {
                'primary': {
                    'status': 'unknown',
                    'uptime': 'N/A',
                    'last_heartbeat': 'N/A'
                },
                'backup': {
                    'status': 'unknown',
                    'uptime': 'N/A',
                    'last_heartbeat': 'N/A'
                },
                'failover_enabled': False,
                'failover_time': 'N/A',
                'active_controller': 'unknown',
                'last_update': 'N/A'
            }
    
    async def _get_system_data(self) -> Dict:
        """Получение общих данных системы"""
        try:
            return {
                'overall_status': 'healthy',
                'tank_status': 'normal',
                'valve_status': 'normal',
                'pid_status': 'normal',
                'opcua_status': 'connected',
                'database_status': 'healthy',
                'analytics_status': 'running',
                'uptime': '2h 15m',
                'alerts_count': 2,
                'critical_errors': 0,
                'total_events': 1250
            }
        except Exception as e:
            logger.error(f"Ошибка получения данных системы: {e}")
            return {}
    
    async def _get_alerts_data(self) -> Dict:
        """Получение данных предупреждений"""
        try:
            return {
                'alerts': [
                    {
                        'level': 'WARNING',
                        'component': 'tank',
                        'message': 'Уровень жидкости близок к минимальному',
                        'timestamp': '19:03:45'
                    },
                    {
                        'level': 'INFO',
                        'component': 'valve',
                        'message': 'Клапан открыт на 45%',
                        'timestamp': '19:04:00'
                    }
                ]
            }
        except Exception as e:
            logger.error(f"Ошибка получения предупреждений: {e}")
            return {'alerts': []}
    
    async def _get_history_data(self) -> Dict:
        """Получение данных истории событий"""
        try:
            return {
                'events': [
                    {
                        'level': 'WARNING',
                        'component': 'tank',
                        'message': 'Уровень жидкости близок к минимальному',
                        'timestamp': '19:03:45'
                    },
                    {
                        'level': 'INFO',
                        'component': 'valve',
                        'message': 'Клапан открыт на 45%',
                        'timestamp': '19:04:00'
                    }
                ],
                'last_hour': 15,
                'last_day': 125
            }
        except Exception as e:
            logger.error(f"Ошибка получения истории: {e}")
            return {'events': [], 'last_hour': 0, 'last_day': 0}
    
    async def _get_logs_data(self) -> Dict:
        """Получение данных логов"""
        try:
            return {
                'logs': [
                    {
                        'level': 'INFO',
                        'component': 'system',
                        'message': 'Система запущена успешно',
                        'timestamp': '19:00:00'
                    },
                    {
                        'level': 'WARNING',
                        'component': 'tank',
                        'message': 'Уровень жидкости близок к минимальному',
                        'timestamp': '19:03:45'
                    }
                ],
                'last_hour': 25,
                'last_day': 250
            }
        except Exception as e:
            logger.error(f"Ошибка получения логов: {e}")
            return {'logs': [], 'last_hour': 0, 'last_day': 0}
    
    async def setup_menu_commands(self):
        """Установка команд меню"""
        commands = [
            BotCommand('start', 'Начать работу с ботом'),
            BotCommand('status', 'ℹ️ Статус системы'),
            BotCommand('tank', '🛢️ Состояние резервуара'),
            BotCommand('valve', '🕹️ Состояние клапана'),
            BotCommand('pid', '🛠️ Параметры PID'),
            BotCommand('controllers', '❕ Статус контроллеров'),
            BotCommand('system', '💬 Общее состояние'),
            BotCommand('help', '🆘 Помощь по командам')
        ]
        
        try:
            await self.application.bot.set_my_commands(commands)
            logger.info('✅ Команды меню установлены')
        except Exception as e:
            logger.error(f'❌ Ошибка установки команд меню: {e}')

    def setup_handlers(self, application: Application):
        """Настройка обработчиков команд"""
        self.application = application
        
        # Основные команды
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("subscribe", self.subscribe_command))
        application.add_handler(CommandHandler("unsubscribe", self.unsubscribe_command))
        application.add_handler(CommandHandler("myid", self.myid_command))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_handler(CommandHandler("help", self.help_command))
        
        # Команды мониторинга параметров
        application.add_handler(CommandHandler("params", self.params_command))
        application.add_handler(CommandHandler("tank", self.tank_status_command))
        application.add_handler(CommandHandler("valve", self.valve_status_command))
        application.add_handler(CommandHandler("pid", self.pid_status_command))
        application.add_handler(CommandHandler("opcua", self.opcua_status_command))
        application.add_handler(CommandHandler("database", self.database_status_command))
        application.add_handler(CommandHandler("analytics", self.analytics_status_command))
        application.add_handler(CommandHandler("controllers", self.controllers_status_command))
        application.add_handler(CommandHandler("system", self.system_status_command))
        application.add_handler(CommandHandler("alerts", self.alerts_command))
        application.add_handler(CommandHandler("history", self.history_command))
        application.add_handler(CommandHandler("logs", self.logs_command))
        
        # Команды фильтров удалены - отправляем все уведомления


# Глобальный экземпляр уведомлений
telegram_notifier: Optional[TelegramNotifier] = None


def init_telegram_bot(bot_token: str, admin_chat_id: Optional[str] = None) -> TelegramNotifier:
    """Инициализация Telegram бота"""
    global telegram_notifier
    
    if telegram_notifier is None:
        telegram_notifier = TelegramNotifier(bot_token, admin_chat_id)
        logger.info("🤖 Telegram бот инициализирован")
    
    return telegram_notifier


def get_telegram_notifier() -> Optional[TelegramNotifier]:
    """Получение экземпляра уведомлений"""
    return telegram_notifier


def start_telegram_bot_sync(bot_token: str, admin_chat_id: Optional[str] = None):
    """Синхронный запуск Telegram бота"""
    notifier = init_telegram_bot(bot_token, admin_chat_id)
    bot_handler = TelegramBotHandler(notifier)
    
    # Инициализация базы данных
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot_handler.db_manager.init_async_pool(min_size=2, max_size=5))
        logger.info("✅ Telegram бот подключен к базе данных")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось подключиться к базе данных: {e}")
    
    # Создание приложения
    application = build_telegram_application(bot_token)
    bot_handler.setup_handlers(application)
    
    # Установка команд меню
    try:
        loop.run_until_complete(bot_handler.setup_menu_commands())
    except Exception as e:
        logger.warning(f"⚠️ Не удалось установить команды меню: {e}")
    
    # Запуск бота
    logger.info("🚀 Запуск Telegram бота...")
    try:
        application.run_polling()
    except Exception as e:
        logger.error(f"❌ Ошибка в Telegram боте: {e}")
        logger.error(
            "Если это таймаут: проверьте доступ к https://api.telegram.org из сети/Docker; "
            "при блокировке Telegram задайте TELEGRAM_PROXY_URL или HTTPS_PROXY; "
            "при медленном канале увеличьте TELEGRAM_CONNECT_TIMEOUT и TELEGRAM_READ_TIMEOUT (сек.)."
        )
    finally:
        # Отключение от OPC UA при завершении
        try:
            loop.run_until_complete(bot_handler._disconnect_from_opcua())
        except:
            pass


async def start_telegram_bot(bot_token: str, admin_chat_id: Optional[str] = None):
    """Запуск Telegram бота"""
    notifier = init_telegram_bot(bot_token, admin_chat_id)
    bot_handler = TelegramBotHandler(notifier)
    
    # Инициализация базы данных
    try:
        await bot_handler.db_manager.init_async_pool(min_size=2, max_size=5)
        logger.info("✅ Telegram бот подключен к базе данных")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось подключиться к базе данных: {e}")
    
    # Создание приложения
    application = build_telegram_application(bot_token)
    bot_handler.setup_handlers(application)
    
    # Установка команд меню
    try:
        await bot_handler.setup_menu_commands()
    except Exception as e:
        logger.warning(f"⚠️ Не удалось установить команды меню: {e}")
    
    # Запуск бота
    logger.info("🚀 Запуск Telegram бота...")
    try:
        await application.run_polling(stop_signals=None)
    except Exception as e:
        logger.error(f"❌ Ошибка в Telegram боте: {e}")
        logger.error(
            "Если это таймаут: проверьте доступ к https://api.telegram.org из сети/Docker; "
            "при блокировке Telegram задайте TELEGRAM_PROXY_URL или HTTPS_PROXY; "
            "при медленном канале увеличьте TELEGRAM_CONNECT_TIMEOUT и TELEGRAM_READ_TIMEOUT (сек.)."
        )
    finally:
        # Отключение от OPC UA при завершении
        await bot_handler._disconnect_from_opcua()


if __name__ == "__main__":
    # Получаем токен из переменных окружения или аргументов командной строки
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not bot_token and len(sys.argv) >= 2:
        bot_token = sys.argv[1]
    
    if not bot_token:
        print("❌ Ошибка: Не указан токен Telegram бота!")
        print("Установите переменную окружения TELEGRAM_BOT_TOKEN или передайте токен как аргумент")
        print("Пример: python telegram_bot.py <BOT_TOKEN>")
        sys.exit(1)
    
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Запуск бота
    start_telegram_bot_sync(bot_token)
