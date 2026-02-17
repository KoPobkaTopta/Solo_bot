__all__ = ("router",)

from aiogram import Router

from .admin_settings import router as admin_settings_router
from .support_tickets import router as support_tickets_router


router = Router(name="forum_topics_main_router")

router.include_routers(
    admin_settings_router,
    support_tickets_router,
)
