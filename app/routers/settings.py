from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update
from datetime import datetime

from app.database import get_session
from app.models import AppConfig
from app.schemas import AppConfigIn, AppConfigOut

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/whatsapp", response_model=AppConfigOut)
async def get_whatsapp_settings(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(AppConfig).where(AppConfig.key.in_(["whatsapp_phone_number_id", "whatsapp_access_token"])))).scalars().all()
    vals = {r.key: r.value for r in rows}
    return AppConfigOut(
        id=1,
        whatsapp_phone_number_id=vals.get("whatsapp_phone_number_id", ""),
        whatsapp_access_token=vals.get("whatsapp_access_token", ""),
        updated_at=datetime.utcnow(),
    )


@router.put("/whatsapp", response_model=AppConfigOut)
async def update_whatsapp_settings(payload: AppConfigIn, session: AsyncSession = Depends(get_session)):
    for key, value in [
        ("whatsapp_phone_number_id", payload.whatsapp_phone_number_id),
        ("whatsapp_access_token", payload.whatsapp_access_token),
    ]:
        row = (await session.execute(select(AppConfig).where(AppConfig.key == key))).scalar_one_or_none()
        if row:
            await session.execute(update(AppConfig).where(AppConfig.key == key).values(value=value))
        else:
            await session.execute(insert(AppConfig).values(key=key, value=value))
    await session.commit()
    return AppConfigOut(
        id=1,
        whatsapp_phone_number_id=payload.whatsapp_phone_number_id,
        whatsapp_access_token=payload.whatsapp_access_token,
        updated_at=datetime.utcnow(),
    )
