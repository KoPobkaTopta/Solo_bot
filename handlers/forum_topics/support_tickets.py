"""
Система тикетов поддержки через форумные топики.

Когда пользователь пишет в бота сообщение, которое не является командой,
оно пересылается в персональный топик в админ-группе.
Админ может ответить прямо в топике, и ответ будет переслан пользователю.
"""

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import BaseFilter
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from core.settings.forum_config import FORUM_CONFIG
from logger import logger

from .topic_manager import (
    get_forum_group_id,
    get_or_create_user_support_topic,
    is_category_enabled,
    is_forum_enabled,
    now_formatted,
    send_to_user_support_topic,
)


router = Router(name="forum_support_tickets")


class IsForumGroupFilter(BaseFilter):
    """Фильтр: сообщение из форумной группы."""

    async def __call__(self, event: Message) -> bool:
        if not is_forum_enabled():
            return False
        group_id = get_forum_group_id()
        if group_id is None:
            return False
        return event.chat.id == group_id and event.chat.type in (
            ChatType.GROUP,
            ChatType.SUPERGROUP,
        )


class IsSupportTopicReply(BaseFilter):
    """
    Фильтр: ответ в топике поддержки в форум-группе.

    Проверяет, что сообщение отправлено в топик,
    созданный для конкретного пользователя (support:*).
    """

    async def __call__(self, event: Message) -> bool:
        if not event.message_thread_id:
            return False
        if not is_category_enabled("support"):
            return False
        return True
