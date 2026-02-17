"""
Менеджер форумных топиков.

Управляет созданием, кэшированием и отправкой сообщений
в форумные топики Telegram-группы.

Категории топиков:
- payments    — Оплаты и пополнения баланса
- new_users   — Новые пользователи
- key_events  — Создание, продление, удаление ключей
- expirations — Истечение подписок и уведомления
- errors      — Ошибки и предупреждения
- support     — Тикеты поддержки (по пользователям)
"""

import asyncio

from datetime import datetime
from typing import Any

import pytz

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.settings.forum_config import FORUM_CONFIG
from database.models import Setting
from logger import logger


moscow_tz = pytz.timezone("Europe/Moscow")

CATEGORY_CONFIG: dict[str, dict[str, str]] = {
    "payments": {
        "name": "💳 Платежи",
        "icon_color": 7322096,
        "setting_key": "TOPIC_PAYMENTS",
    },
    "new_users": {
        "name": "👤 Новые пользователи",
        "icon_color": 16766590,
        "setting_key": "TOPIC_NEW_USERS",
    },
    "key_events": {
        "name": "🔑 Ключи",
        "icon_color": 13338331,
        "setting_key": "TOPIC_KEY_EVENTS",
    },
    "expirations": {
        "name": "⏳ Истечение подписок",
        "icon_color": 16749490,
        "setting_key": "TOPIC_EXPIRATIONS",
    },
    "errors": {
        "name": "🚨 Ошибки",
        "icon_color": 16478047,
        "setting_key": "TOPIC_ERRORS",
    },
    "support": {
        "name": "📨 Поддержка",
        "icon_color": 6559999,
        "setting_key": "TOPIC_SUPPORT",
    },
}

_topic_cache: dict[str, int] = {}
_cache_lock = asyncio.Lock()

SETTING_KEY = "FORUM_TOPIC_IDS"


async def _load_topic_cache(session: AsyncSession) -> dict[str, int]:
    """Загружает кэш topic_id из базы данных."""
    stmt = select(Setting).where(Setting.key == SETTING_KEY)
    result = await session.execute(stmt)
    setting = result.scalar_one_or_none()
    if setting and setting.value:
        return {str(k): int(v) for k, v in setting.value.items()}
    return {}


async def _save_topic_cache(session: AsyncSession, cache: dict[str, int]) -> None:
    """Сохраняет кэш topic_id в базу данных."""
    stmt = select(Setting).where(Setting.key == SETTING_KEY)
    result = await session.execute(stmt)
    setting = result.scalar_one_or_none()

    value = {str(k): int(v) for k, v in cache.items()}
    if setting is None:
        setting = Setting(
            key=SETTING_KEY,
            value=value,
            description="Кэш ID форумных топиков",
        )
        session.add(setting)
    else:
        setting.value = value

    await session.flush()


def is_forum_enabled() -> bool:
    """Проверяет, включены ли форумные топики."""
    return bool(FORUM_CONFIG.get("FORUM_ENABLED")) and FORUM_CONFIG.get("FORUM_GROUP_ID") is not None


def get_forum_group_id() -> int | None:
    """Возвращает ID группы с форумом."""
    gid = FORUM_CONFIG.get("FORUM_GROUP_ID")
    return int(gid) if gid is not None else None


def is_category_enabled(category: str) -> bool:
    """Проверяет, включена ли конкретная категория топиков."""
    if not is_forum_enabled():
        return False
    config = CATEGORY_CONFIG.get(category)
    if not config:
        return False
    return bool(FORUM_CONFIG.get(config["setting_key"], True))


async def get_or_create_topic(
    bot: Bot,
    session: AsyncSession,
    category: str,
) -> int | None:
    """
    Получает или создаёт форумный топик для указанной категории.

    Возвращает message_thread_id топика или None при ошибке.
    """
    if not is_category_enabled(category):
        return None

    group_id = get_forum_group_id()
    if group_id is None:
        return None

    cache_key = f"{group_id}:{category}"

    async with _cache_lock:
        if cache_key in _topic_cache:
            return _topic_cache[cache_key]

        db_cache = await _load_topic_cache(session)
        if cache_key in db_cache:
            _topic_cache[cache_key] = db_cache[cache_key]
            return db_cache[cache_key]

    config = CATEGORY_CONFIG.get(category)
    if not config:
        return None

    try:
        result = await bot.create_forum_topic(
            chat_id=group_id,
            name=config["name"],
            icon_color=config.get("icon_color"),
        )
        topic_id = result.message_thread_id

        async with _cache_lock:
            _topic_cache[cache_key] = topic_id
            db_cache = await _load_topic_cache(session)
            db_cache[cache_key] = topic_id
            await _save_topic_cache(session, db_cache)
            await session.commit()

        logger.info(f"[Forum] Создан топик '{config['name']}' (id={topic_id}) в группе {group_id}")
        return topic_id

    except TelegramBadRequest as e:
        if "TOPIC_NOT_MODIFIED" in str(e):
            pass
        else:
            logger.error(f"[Forum] Ошибка создания топика '{category}': {e}")
        return None
    except TelegramForbiddenError:
        logger.error(f"[Forum] Бот не имеет прав для управления топиками в группе {group_id}")
        return None
    except Exception as e:
        logger.error(f"[Forum] Непредвиденная ошибка при создании топика '{category}': {e}")
        return None


async def get_or_create_user_support_topic(
    bot: Bot,
    session: AsyncSession,
    tg_id: int,
    username: str | None = None,
    first_name: str | None = None,
) -> int | None:
    """
    Создаёт или получает персональный топик поддержки для пользователя.

    Каждый пользователь получает свой топик в формате:
    "Тикет #<tg_id> — <имя>"
    """
    if not is_category_enabled("support"):
        return None

    group_id = get_forum_group_id()
    if group_id is None:
        return None

    cache_key = f"{group_id}:support:{tg_id}"

    async with _cache_lock:
        if cache_key in _topic_cache:
            return _topic_cache[cache_key]

        db_cache = await _load_topic_cache(session)
        if cache_key in db_cache:
            _topic_cache[cache_key] = db_cache[cache_key]
            return db_cache[cache_key]

    display_name = first_name or ""
    if username:
        display_name = f"@{username}" if display_name else f"@{username}"
        if first_name:
            display_name = f"{first_name} (@{username})"

    topic_name = f"Тикет #{tg_id}"
    if display_name:
        topic_name = f"Тикет #{tg_id} — {display_name}"

    if len(topic_name) > 128:
        topic_name = topic_name[:125] + "..."

    try:
        result = await bot.create_forum_topic(
            chat_id=group_id,
            name=topic_name,
            icon_color=6559999,
        )
        topic_id = result.message_thread_id

        async with _cache_lock:
            _topic_cache[cache_key] = topic_id
            db_cache = await _load_topic_cache(session)
            db_cache[cache_key] = topic_id
            await _save_topic_cache(session, db_cache)
            await session.commit()

        logger.info(f"[Forum] Создан тикет поддержки для {tg_id} (topic_id={topic_id})")
        return topic_id

    except Exception as e:
        logger.error(f"[Forum] Ошибка создания тикета поддержки для {tg_id}: {e}")
        return None


async def send_to_topic(
    bot: Bot,
    session: AsyncSession,
    category: str,
    text: str,
    parse_mode: str = "HTML",
) -> bool:
    """Отправляет сообщение в топик указанной категории."""
    topic_id = await get_or_create_topic(bot, session, category)
    if topic_id is None:
        return False

    group_id = get_forum_group_id()
    if group_id is None:
        return False

    try:
        await bot.send_message(
            chat_id=group_id,
            message_thread_id=topic_id,
            text=text,
            parse_mode=parse_mode,
        )
        return True
    except TelegramBadRequest as e:
        if "message thread not found" in str(e).lower():
            cache_key = f"{group_id}:{category}"
            async with _cache_lock:
                _topic_cache.pop(cache_key, None)
                db_cache = await _load_topic_cache(session)
                db_cache.pop(cache_key, None)
                await _save_topic_cache(session, db_cache)
                await session.commit()

            topic_id = await get_or_create_topic(bot, session, category)
            if topic_id is None:
                return False
            try:
                await bot.send_message(
                    chat_id=group_id,
                    message_thread_id=topic_id,
                    text=text,
                    parse_mode=parse_mode,
                )
                return True
            except Exception as retry_error:
                logger.error(f"[Forum] Повторная ошибка отправки в '{category}': {retry_error}")
                return False
        logger.error(f"[Forum] Ошибка отправки в топик '{category}': {e}")
        return False
    except Exception as e:
        logger.error(f"[Forum] Ошибка отправки в топик '{category}': {e}")
        return False


async def send_to_user_support_topic(
    bot: Bot,
    session: AsyncSession,
    tg_id: int,
    text: str,
    username: str | None = None,
    first_name: str | None = None,
    parse_mode: str = "HTML",
) -> bool:
    """Отправляет сообщение в персональный тикет пользователя."""
    topic_id = await get_or_create_user_support_topic(
        bot, session, tg_id, username, first_name
    )
    if topic_id is None:
        return False

    group_id = get_forum_group_id()
    if group_id is None:
        return False

    try:
        await bot.send_message(
            chat_id=group_id,
            message_thread_id=topic_id,
            text=text,
            parse_mode=parse_mode,
        )
        return True
    except Exception as e:
        logger.error(f"[Forum] Ошибка отправки в тикет пользователя {tg_id}: {e}")
        return False


def now_formatted() -> str:
    """Возвращает текущее время в формате для логов."""
    return datetime.now(moscow_tz).strftime("%d.%m.%Y %H:%M:%S")


def invalidate_cache() -> None:
    """Очищает весь кэш топиков (при смене группы)."""
    _topic_cache.clear()
