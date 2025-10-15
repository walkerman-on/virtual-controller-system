#!/usr/bin/env python3
"""
Упрощенная версия TelegramNotifier для watchdog сервисов
"""

import json
import logging
import os
import asyncio
import aiohttp
from typing import Dict, Set, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

def get_moscow_time():
    """Получение текущего времени по МСК (UTC+3)"""
    moscow_tz = timezone(timedelta(hours=3))
    return datetime.now(moscow_tz)

class SimpleTelegramNotifier:
    """Упрощенный класс для отправки уведомлений через Telegram"""
    
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.subscribers: Set[str] = set()
        self.enabled = True
        
        # Загружаем подписчиков из файла
        self._load_subscribers()
        
        logger.info("🤖 Simple Telegram уведомления инициализированы")
    
    def _load_subscribers(self):
        """Загрузка списка подписчиков из файла"""
        try:
            subscribers_file = '/app/data/telegram_subscribers.json'
            if os.path.exists(subscribers_file):
                with open(subscribers_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.subscribers = set(data.get('subscribers', []))
                logger.info(f"📋 Загружено {len(self.subscribers)} подписчиков")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки подписчиков: {e}")
    
    async def send_notification(self, level: str, component: str, message: str, 
                              additional_data: Optional[Dict] = None):
        """Отправка уведомления всем подписчикам"""
        if not self.enabled or not self.subscribers:
            logger.warning("⚠️ Уведомления отключены или нет подписчиков")
            return
        
        # Формируем текст сообщения
        moscow_time = get_moscow_time().strftime('%H:%M:%S')
        
        if level == "CRITICAL":
            emoji = "🚨"
            level_text = "КРИТИЧЕСКАЯ ОШИБКА"
        elif level == "ERROR":
            emoji = "❌"
            level_text = "ОШИБКА"
        elif level == "WARNING":
            emoji = "⚠️"
            level_text = "ПРЕДУПРЕЖДЕНИЕ"
        elif level == "INFO":
            emoji = "ℹ️"
            level_text = "ИНФОРМАЦИЯ"
        else:
            emoji = "📢"
            level_text = level
        
        text = f"{emoji} {level_text}\n"
        text += f"🕐 {moscow_time}\n"
        text += f"🔧 Компонент: {component}\n"
        text += f"📝 {message}\n"
        
        if additional_data:
            text += "\n📊 Дополнительная информация:\n"
            for key, value in additional_data.items():
                text += f"• {key}: {value}\n"
        
        # Отправляем всем подписчикам
        tasks = []
        for chat_id in self.subscribers:
            tasks.append(self._send_to_chat(chat_id, text))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _send_to_chat(self, chat_id: str, text: str):
        """Отправка сообщения в конкретный чат"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': text,
                'disable_web_page_preview': True
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as response:
                    if response.status == 200:
                        logger.debug(f"📤 Уведомление отправлено в {chat_id}")
                    else:
                        logger.error(f"❌ Ошибка отправки в {chat_id}: HTTP {response.status}")
                        
        except Exception as e:
            logger.error(f"❌ Ошибка отправки в {chat_id}: {e}")
