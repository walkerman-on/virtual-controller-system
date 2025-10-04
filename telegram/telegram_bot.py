"""
Telegram бот для уведомлений о критических ситуациях в системе виртуального контроллера
"""

import asyncio
import json
import logging
import os
import sys
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta

import aiohttp
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


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
            if os.path.exists('telegram_subscribers.json'):
                with open('telegram_subscribers.json', 'r', encoding='utf-8') as f:
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
            with open('telegram_subscribers.json', 'w', encoding='utf-8') as f:
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
        
        # Проверка фильтров пользователя
        if chat_id in self.notification_filters:
            filters = self.notification_filters[chat_id]
            
            # Проверка уровня важности
            min_level = filters.get('min_level', 'DEBUG')
            level_priority = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2, 'ERROR': 3, 'CRITICAL': 4}
            if level_priority.get(level, 0) < level_priority.get(min_level, 0):
                return False
            
            # Проверка компонентов
            allowed_components = filters.get('components', [])
            if allowed_components and component not in allowed_components:
                return False
        
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
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        # Основное сообщение
        text = f"{emoji} *{level}* [{timestamp}]\n"
        text += f"🔧 *Компонент:* {component}\n"
        text += f"📝 *Сообщение:* {message}\n"
        
        # Добавление дополнительных данных
        if additional_data:
            text += "\n📊 *Дополнительные данные:*\n"
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
                parse_mode='Markdown',
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
            text += f"⏰ *Время:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            
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
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        chat_id = str(update.effective_chat.id)
        
        text = """
🤖 *Добро пожаловать в систему мониторинга!*

Доступные команды:
/start - Начать работу
/subscribe - Подписаться на уведомления
/unsubscribe - Отписаться от уведомлений
/status - Статус системы
/filters - Настройка фильтров
/help - Помощь

Для получения уведомлений используйте /subscribe
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
📖 *Помощь по командам*

*Основные команды:*
/start - Начать работу с ботом
/subscribe - Подписаться на уведомления
/unsubscribe - Отписаться от уведомлений
/status - Получить отчет о состоянии системы

*Мониторинг параметров:*
/params - Все параметры системы
/tank - Состояние резервуара
/valve - Состояние клапана
/pid - Параметры PID контроллера
/opcua - Статус OPC UA сервера
/database - Статус базы данных
/analytics - Статус аналитики
/controllers - Статус контроллеров
/system - Общее состояние системы
/alerts - Активные предупреждения
/history - История событий
/logs - Последние логи

*Настройка фильтров:*
/filters - Информация о фильтрах
/filter_level LEVEL - Установить минимальный уровень уведомлений
/filter_components COMPONENTS - Установить отслеживаемые компоненты

*Примеры:*
/filter_level ERROR
/filter_components tank,valve,controller

*Уровни важности:*
DEBUG - Отладочная информация
INFO - Информационные сообщения
WARNING - Предупреждения
ERROR - Ошибки
CRITICAL - Критические ошибки
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

⏰ *Время обновления:* {datetime.now().strftime('%H:%M:%S')}
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

⏰ *Время обновления:* {datetime.now().strftime('%H:%M:%S')}
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

⏰ *Время обновления:* {datetime.now().strftime('%H:%M:%S')}
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

⏰ *Время проверки:* {datetime.now().strftime('%H:%M:%S')}
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

⏰ *Время проверки:* {datetime.now().strftime('%H:%M:%S')}
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

⏰ *Время проверки:* {datetime.now().strftime('%H:%M:%S')}
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

⏰ *Время проверки:* {datetime.now().strftime('%H:%M:%S')}
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

⏰ *Время проверки:* {datetime.now().strftime('%H:%M:%S')}
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
            
            text += f"\n⏰ *Время проверки:* {datetime.now().strftime('%H:%M:%S')}"
            
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
            
            text += f"\n⏰ *Время проверки:* {datetime.now().strftime('%H:%M:%S')}"
            
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
            
            text += f"\n⏰ *Время проверки:* {datetime.now().strftime('%H:%M:%S')}"
            
            await update.message.reply_text(text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения логов: {str(e)}")
    
    # Вспомогательные методы для получения данных
    async def _get_tank_data(self) -> Dict:
        """Получение данных резервуара"""
        try:
            # Здесь можно добавить реальные запросы к API или базе данных
            # Пока возвращаем тестовые данные
            return {
                'level': 2.5,
                'volume': 12.5,
                'mass': 12500,
                'pressure': 101325
            }
        except Exception as e:
            logger.error(f"Ошибка получения данных резервуара: {e}")
            return {}
    
    async def _get_valve_data(self) -> Dict:
        """Получение данных клапана"""
        try:
            return {
                'opening': 45.0,
                'flow_rate': 0.025,
                'change_rate': 2.5
            }
        except Exception as e:
            logger.error(f"Ошибка получения данных клапана: {e}")
            return {}
    
    async def _get_pid_data(self) -> Dict:
        """Получение данных PID контроллера"""
        try:
            return {
                'setpoint': 3.0,
                'process_value': 2.5,
                'error': 0.5,
                'output': 45.0,
                'kp': 1.0,
                'ki': 0.1,
                'kd': 0.05,
                'proportional': 0.5,
                'integral': 0.1,
                'derivative': 0.05
            }
        except Exception as e:
            logger.error(f"Ошибка получения данных PID: {e}")
            return {}
    
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
        """Получение данных контроллеров"""
        try:
            return {
                'primary': {
                    'status': 'active',
                    'uptime': '2h 15m',
                    'last_heartbeat': '19:04:30'
                },
                'backup': {
                    'status': 'standby',
                    'uptime': '2h 15m',
                    'last_heartbeat': '19:04:25'
                },
                'failover_enabled': True,
                'failover_time': '2.5s'
            }
        except Exception as e:
            logger.error(f"Ошибка получения данных контроллеров: {e}")
            return {}
    
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
    
    def setup_handlers(self, application: Application):
        """Настройка обработчиков команд"""
        self.application = application
        
        # Основные команды
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("subscribe", self.subscribe_command))
        application.add_handler(CommandHandler("unsubscribe", self.unsubscribe_command))
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
        
        # Команды фильтров
        application.add_handler(CommandHandler("filters", self.filters_command))
        application.add_handler(CommandHandler("filter_level", self.filter_level_command))
        application.add_handler(CommandHandler("filter_components", self.filter_components_command))


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
    
    # Создание приложения
    application = Application.builder().token(bot_token).build()
    bot_handler.setup_handlers(application)
    
    # Запуск бота
    logger.info("🚀 Запуск Telegram бота...")
    try:
        application.run_polling()
    except Exception as e:
        logger.error(f"❌ Ошибка в Telegram боте: {e}")


async def start_telegram_bot(bot_token: str, admin_chat_id: Optional[str] = None):
    """Запуск Telegram бота"""
    notifier = init_telegram_bot(bot_token, admin_chat_id)
    bot_handler = TelegramBotHandler(notifier)
    
    # Создание приложения
    application = Application.builder().token(bot_token).build()
    bot_handler.setup_handlers(application)
    
    # Запуск бота
    logger.info("🚀 Запуск Telegram бота...")
    try:
        await application.run_polling(stop_signals=None)
    except Exception as e:
        logger.error(f"❌ Ошибка в Telegram боте: {e}")


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
