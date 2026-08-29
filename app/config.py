import os
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_session
from app.models import AppConfig


class Settings(BaseModel):
    whatsapp_phone_number_id: Optional[str] = None
    whatsapp_access_token: Optional[str] = None

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            whatsapp_phone_number_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID"),
            whatsapp_access_token=os.getenv("WHATSAPP_ACCESS_TOKEN"),
        )


async def load_settings_from_db(session: AsyncSession) -> Settings:
    settings = Settings.load()
    rows = (await session.execute(
        select(AppConfig).where(AppConfig.key.in_(["whatsapp_phone_number_id", "whatsapp_access_token"]))
    )).scalars().all()
    vals = {r.key: r.value for r in rows}
    if vals.get("whatsapp_phone_number_id"):
        settings.whatsapp_phone_number_id = vals["whatsapp_phone_number_id"]
    if vals.get("whatsapp_access_token"):
        settings.whatsapp_access_token = vals["whatsapp_access_token"]
    return settings
