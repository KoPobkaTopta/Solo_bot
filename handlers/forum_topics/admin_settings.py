"""
Административные настройки форумных топиков.

Добавляет в настройки бота раздел "Топики" с возможностью:
- Включить/выключить форумные топики
- Задать ID группы с форумом
- Включить/выключить отдельные категории
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from core.settings.forum_config import FORUM_CONFIG, update_forum_config
from filters.admin import IsAdminFilter
from handlers.admin.panel.keyboard import AdminPanelCallback, build_admin_back_btn
from handlers.buttons import BACK
from logger import logger

from .topic_manager import invalidate_cache


router = Router(name="admin_forum_settings")
router.callback_query.filter(IsAdminFilter())
router.message.filter(IsAdminFilter())


FORUM_TOGGLE_TITLES: dict[str, str] = {
    "FORUM_ENABLED": "Форумные топики",
    "TOPIC_PAYMENTS": "Топик: Платежи",
    "TOPIC_NEW_USERS": "Топик: Новые юзеры",
    "TOPIC_KEY_EVENTS": "Топик: Ключи",
    "TOPIC_EXPIRATIONS": "Топик: Истечения",
    "TOPIC_ERRORS": "Топик: Ошибки",
    "TOPIC_SUPPORT": "Топик: Поддержка",
}


class ForumGroupIdState(StatesGroup):
    waiting_for_group_id = State()


def build_forum_settings_kb() -> InlineKeyboardBuilder:
    """Строит клавиатуру настроек форумных топиков."""
    builder = InlineKeyboardBuilder()

    for index, (key, title) in enumerate(FORUM_TOGGLE_TITLES.items(), start=1):
        current = bool(FORUM_CONFIG.get(key, False))
        prefix = "✅" if current else "❌"
        builder.button(
            text=f"{prefix} {title}",
            callback_data=AdminPanelCallback(
                action="forum_toggle",
                page=index,
            ).pack(),
        )

    builder.adjust(1)

    group_id = FORUM_CONFIG.get("FORUM_GROUP_ID")
    group_text = f"Группа: {group_id}" if group_id else "Группа: не задана"
    builder.row(
        InlineKeyboardButton(
            text=f"🔗 {group_text}",
            callback_data=AdminPanelCallback(action="forum_set_group").pack(),
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🔄 Сбросить кэш топиков",
            callback_data=AdminPanelCallback(action="forum_reset_cache").pack(),
        )
    )

    builder.row(
        InlineKeyboardButton(
            text=BACK,
            callback_data=AdminPanelCallback(action="settings").pack(),
        )
    )

    return builder


@router.callback_query(AdminPanelCallback.filter(F.action == "settings_forum"))
async def open_forum_settings(callback: CallbackQuery) -> None:
    """Открывает меню настроек форумных топиков."""
    text = (
        "<b>🗂 Настройки форумных топиков</b>\n\n"
        "Форумные топики позволяют автоматически логировать "
        "события бота в отдельные темы Telegram-группы.\n\n"
        "<b>Как настроить:</b>\n"
        "1. Создайте группу или используйте существующую\n"
        "2. Включите режим «Темы» в настройках группы\n"
        "3. Добавьте бота в группу как администратора\n"
        "4. Дайте боту право «Управлять темами»\n"
        "5. Укажите ID группы ниже\n"
        "6. Включите нужные категории\n\n"
        "<i>Бот автоматически создаст топики при первом событии.</i>"
    )
    await callback.message.edit_text(
        text=text,
        reply_markup=build_forum_settings_kb().as_markup(),
    )
    await callback.answer()


@router.callback_query(AdminPanelCallback.filter(F.action == "forum_toggle"))
async def toggle_forum_setting(
    callback: CallbackQuery,
    callback_data: AdminPanelCallback,
    session: AsyncSession,
) -> None:
    """Переключает настройку форумных топиков."""
    keys = list(FORUM_TOGGLE_TITLES.keys())
    idx = callback_data.page

    if not 1 <= idx <= len(keys):
        await callback.answer("Неизвестная настройка", show_alert=True)
        return

    key = keys[idx - 1]
    config = dict(FORUM_CONFIG or {})
    current = bool(config.get(key, False))
    config[key] = not current

    await update_forum_config(session, config)

    await callback.message.edit_reply_markup(
        reply_markup=build_forum_settings_kb().as_markup(),
    )
    await callback.answer("Настройка обновлена")


@router.callback_query(AdminPanelCallback.filter(F.action == "forum_set_group"))
async def prompt_forum_group_id(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Запрашивает ID группы."""
    current = FORUM_CONFIG.get("FORUM_GROUP_ID")
    text = (
        "<b>Укажите ID группы с форумом</b>\n\n"
        "Отправьте числовой ID группы (обычно отрицательное число).\n"
        "Например: <code>-1001234567890</code>\n\n"
        "Чтобы узнать ID, добавьте бота @userinfobot в группу "
        "или перешлите сообщение из группы боту @getmyid_bot.\n\n"
    )
    if current:
        text += f"Текущее значение: <code>{current}</code>\n"
        text += "Отправьте <code>0</code> чтобы сбросить."

    builder = InlineKeyboardBuilder()
    builder.row(build_admin_back_btn("settings_forum"))
    await callback.message.edit_text(text=text, reply_markup=builder.as_markup())
    await state.set_state(ForumGroupIdState.waiting_for_group_id)
    await callback.answer()


@router.message(ForumGroupIdState.waiting_for_group_id, IsAdminFilter())
async def handle_forum_group_id_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Обрабатывает ввод ID группы."""
    text = (message.text or "").strip()

    try:
        group_id = int(text)
    except ValueError:
        await message.answer("Введите числовой ID группы.")
        return

    config = dict(FORUM_CONFIG or {})

    if group_id == 0:
        config["FORUM_GROUP_ID"] = None
        invalidate_cache()
        await update_forum_config(session, config)
        await state.clear()
        await message.answer(
            "Группа сброшена.",
            reply_markup=build_forum_settings_kb().as_markup(),
        )
        return

    config["FORUM_GROUP_ID"] = group_id
    invalidate_cache()
    await update_forum_config(session, config)
    await state.clear()

    await message.answer(
        f"✅ Группа установлена: <code>{group_id}</code>",
        reply_markup=build_forum_settings_kb().as_markup(),
    )


@router.callback_query(AdminPanelCallback.filter(F.action == "forum_reset_cache"))
async def reset_forum_cache(callback: CallbackQuery) -> None:
    """Сбрасывает кэш ID топиков."""
    invalidate_cache()
    await callback.answer("Кэш топиков сброшен. Топики будут пересозданы.", show_alert=True)
