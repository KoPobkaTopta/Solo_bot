from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Setting


DEFAULT_FORUM_CONFIG: dict[str, Any] = {
    "FORUM_ENABLED": False,
    "FORUM_GROUP_ID": None,
    "TOPIC_PAYMENTS": True,
    "TOPIC_NEW_USERS": True,
    "TOPIC_KEY_EVENTS": True,
    "TOPIC_EXPIRATIONS": True,
    "TOPIC_ERRORS": True,
    "TOPIC_SUPPORT": True,
}

FORUM_CONFIG: dict[str, Any] = DEFAULT_FORUM_CONFIG.copy()


async def load_forum_config(session: AsyncSession) -> None:
    stmt = select(Setting).where(Setting.key == "FORUM_CONFIG")
    result = await session.execute(stmt)
    setting = result.scalar_one_or_none()

    if setting is None:
        forum_config = DEFAULT_FORUM_CONFIG.copy()
        setting = Setting(
            key="FORUM_CONFIG",
            value=forum_config,
            description="Конфигурация форумных топиков",
        )
        session.add(setting)
    else:
        stored = setting.value or {}
        forum_config = DEFAULT_FORUM_CONFIG.copy()
        forum_config.update(stored)
        setting.value = forum_config

    FORUM_CONFIG.clear()
    FORUM_CONFIG.update(forum_config)
    await session.flush()


async def update_forum_config(session: AsyncSession, new_values: dict[str, Any]) -> None:
    stmt = select(Setting).where(Setting.key == "FORUM_CONFIG")
    result = await session.execute(stmt)
    setting = result.scalar_one_or_none()

    if setting is None:
        setting = Setting(
            key="FORUM_CONFIG",
            value=new_values,
            description="Конфигурация форумных топиков",
        )
        session.add(setting)
    else:
        setting.value = new_values

    await session.commit()

    forum_config = DEFAULT_FORUM_CONFIG.copy()
    forum_config.update(new_values)

    FORUM_CONFIG.clear()
    FORUM_CONFIG.update(forum_config)
