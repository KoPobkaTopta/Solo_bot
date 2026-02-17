"""
Логирование событий бота в форумные топики.

Предоставляет удобные функции для логирования:
- Платежей и пополнений
- Новых пользователей
- Создания/продления/удаления ключей
- Истечения подписок
- Ошибок
"""

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from logger import logger

from .topic_manager import (
    is_forum_enabled,
    now_formatted,
    send_to_topic,
    send_to_user_support_topic,
)


async def log_new_user(
    bot: Bot,
    session: AsyncSession,
    tg_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    source: str | None = None,
) -> None:
    """Логирует нового пользователя."""
    if not is_forum_enabled():
        return

    name_parts = []
    if first_name:
        name_parts.append(first_name)
    if last_name:
        name_parts.append(last_name)
    display_name = " ".join(name_parts) or "—"

    lines = [
        "👤 <b>Новый пользователь</b>",
        "",
        f"<b>ID:</b> <code>{tg_id}</code>",
        f"<b>Имя:</b> {display_name}",
    ]
    if username:
        lines.append(f"<b>Username:</b> @{username}")
    if source:
        lines.append(f"<b>Источник:</b> {source}")
    lines.append(f"\n🕐 {now_formatted()}")

    text = "\n".join(lines)

    try:
        await send_to_topic(bot, session, "new_users", text)
    except Exception as e:
        logger.debug(f"[Forum] Не удалось залогировать нового пользователя: {e}")


async def log_payment(
    bot: Bot,
    session: AsyncSession,
    tg_id: int,
    amount: float,
    payment_system: str,
    username: str | None = None,
    first_name: str | None = None,
    currency: str = "RUB",
) -> None:
    """Логирует платёж."""
    if not is_forum_enabled():
        return

    display_name = first_name or "—"
    if username:
        display_name = f"{first_name or ''} (@{username})"

    lines = [
        "💳 <b>Пополнение баланса</b>",
        "",
        f"<b>Пользователь:</b> {display_name}",
        f"<b>ID:</b> <code>{tg_id}</code>",
        f"<b>Сумма:</b> {amount} {currency}",
        f"<b>Способ:</b> {payment_system}",
        f"\n🕐 {now_formatted()}",
    ]

    text = "\n".join(lines)

    try:
        await send_to_topic(bot, session, "payments", text)
    except Exception as e:
        logger.debug(f"[Forum] Не удалось залогировать платёж: {e}")


async def log_key_created(
    bot: Bot,
    session: AsyncSession,
    tg_id: int,
    email: str,
    tariff_name: str | None = None,
    server_name: str | None = None,
    is_trial: bool = False,
) -> None:
    """Логирует создание ключа."""
    if not is_forum_enabled():
        return

    key_type = "🎁 Пробный ключ" if is_trial else "🔑 Новый ключ"
    lines = [
        f"{key_type} <b>создан</b>",
        "",
        f"<b>ID:</b> <code>{tg_id}</code>",
        f"<b>Подписка:</b> <code>{email}</code>",
    ]
    if tariff_name:
        lines.append(f"<b>Тариф:</b> {tariff_name}")
    if server_name:
        lines.append(f"<b>Сервер:</b> {server_name}")
    lines.append(f"\n🕐 {now_formatted()}")

    text = "\n".join(lines)

    try:
        await send_to_topic(bot, session, "key_events", text)
    except Exception as e:
        logger.debug(f"[Forum] Не удалось залогировать создание ключа: {e}")


async def log_key_renewed(
    bot: Bot,
    session: AsyncSession,
    tg_id: int,
    email: str,
    tariff_name: str | None = None,
    cost: float | None = None,
    auto: bool = False,
) -> None:
    """Логирует продление ключа."""
    if not is_forum_enabled():
        return

    renew_type = "🔄 Авто-продление" if auto else "🔄 Продление"
    lines = [
        f"{renew_type}",
        "",
        f"<b>ID:</b> <code>{tg_id}</code>",
        f"<b>Подписка:</b> <code>{email}</code>",
    ]
    if tariff_name:
        lines.append(f"<b>Тариф:</b> {tariff_name}")
    if cost is not None:
        lines.append(f"<b>Списано:</b> {cost} ₽")
    lines.append(f"\n🕐 {now_formatted()}")

    text = "\n".join(lines)

    try:
        await send_to_topic(bot, session, "key_events", text)
    except Exception as e:
        logger.debug(f"[Forum] Не удалось залогировать продление ключа: {e}")


async def log_key_deleted(
    bot: Bot,
    session: AsyncSession,
    tg_id: int,
    email: str,
    reason: str = "вручную",
) -> None:
    """Логирует удаление ключа."""
    if not is_forum_enabled():
        return

    lines = [
        "🗑 <b>Ключ удалён</b>",
        "",
        f"<b>ID:</b> <code>{tg_id}</code>",
        f"<b>Подписка:</b> <code>{email}</code>",
        f"<b>Причина:</b> {reason}",
        f"\n🕐 {now_formatted()}",
    ]

    text = "\n".join(lines)

    try:
        await send_to_topic(bot, session, "key_events", text)
    except Exception as e:
        logger.debug(f"[Forum] Не удалось залогировать удаление ключа: {e}")


async def log_key_expiring(
    bot: Bot,
    session: AsyncSession,
    tg_id: int,
    email: str,
    hours_left: int,
) -> None:
    """Логирует скорое истечение подписки."""
    if not is_forum_enabled():
        return

    lines = [
        "⏳ <b>Подписка истекает</b>",
        "",
        f"<b>ID:</b> <code>{tg_id}</code>",
        f"<b>Подписка:</b> <code>{email}</code>",
        f"<b>Осталось:</b> ~{hours_left} ч.",
        f"\n🕐 {now_formatted()}",
    ]

    text = "\n".join(lines)

    try:
        await send_to_topic(bot, session, "expirations", text)
    except Exception as e:
        logger.debug(f"[Forum] Не удалось залогировать истечение подписки: {e}")


async def log_key_expired(
    bot: Bot,
    session: AsyncSession,
    tg_id: int,
    email: str,
) -> None:
    """Логирует факт истечения подписки."""
    if not is_forum_enabled():
        return

    lines = [
        "❌ <b>Подписка истекла</b>",
        "",
        f"<b>ID:</b> <code>{tg_id}</code>",
        f"<b>Подписка:</b> <code>{email}</code>",
        f"\n🕐 {now_formatted()}",
    ]

    text = "\n".join(lines)

    try:
        await send_to_topic(bot, session, "expirations", text)
    except Exception as e:
        logger.debug(f"[Forum] Не удалось залогировать истечение подписки: {e}")


async def log_error(
    bot: Bot,
    session: AsyncSession,
    error_text: str,
    context: str | None = None,
) -> None:
    """Логирует ошибку."""
    if not is_forum_enabled():
        return

    lines = [
        "🚨 <b>Ошибка</b>",
        "",
    ]
    if context:
        lines.append(f"<b>Контекст:</b> {context}")
    lines.append(f"<pre>{error_text[:3000]}</pre>")
    lines.append(f"\n🕐 {now_formatted()}")

    text = "\n".join(lines)

    try:
        await send_to_topic(bot, session, "errors", text)
    except Exception as e:
        logger.debug(f"[Forum] Не удалось залогировать ошибку: {e}")


async def log_support_message(
    bot: Bot,
    session: AsyncSession,
    tg_id: int,
    message_text: str,
    username: str | None = None,
    first_name: str | None = None,
) -> None:
    """Логирует обращение пользователя в поддержку."""
    if not is_forum_enabled():
        return

    display_name = first_name or "—"
    if username:
        display_name = f"{first_name or ''} (@{username})"

    lines = [
        "📨 <b>Сообщение от пользователя</b>",
        "",
        f"<b>Пользователь:</b> {display_name}",
        f"<b>ID:</b> <code>{tg_id}</code>",
        "",
        f"{message_text[:3000]}",
        f"\n🕐 {now_formatted()}",
    ]

    text = "\n".join(lines)

    try:
        await send_to_user_support_topic(
            bot, session, tg_id, text,
            username=username, first_name=first_name,
        )
    except Exception as e:
        logger.debug(f"[Forum] Не удалось залогировать сообщение поддержки: {e}")
