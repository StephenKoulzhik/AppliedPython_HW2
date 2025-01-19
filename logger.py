from aiogram import BaseMiddleware
from aiogram.types import Message
import logging

class Logger(BaseMiddleware):
    async def __call__(self, handler, event: Message, data: dict):
        logging.info(f"Received message: {event.text}")
        return await handler(event, data)