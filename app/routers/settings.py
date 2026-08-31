from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.database import get_session
from app.models import Client
from app.auth import get_current_client
from app.schemas import AppConfigIn, AppConfigOut

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/whatsapp", response_model=AppConfigOut)
async def get_whatsapp_settings(session: AsyncSession = Depends(get_session), client=Depends(get_current_client)):
    return AppConfigOut(
        id=client.id,
        whatsapp_phone_number_id=client.whatsapp_phone_number_id or "",
        whatsapp_access_token=client.whatsapp_access_token or "",
        updated_at=client.created_at,
    )


@router.put("/whatsapp", response_model=AppConfigOut)
async def update_whatsapp_settings(payload: AppConfigIn, session: AsyncSession = Depends(get_session), client=Depends(get_current_client)):
    updates = {}
    if payload.whatsapp_phone_number_id is not None:
        updates["whatsapp_phone_number_id"] = payload.whatsapp_phone_number_id
    if payload.whatsapp_access_token is not None:
        updates["whatsapp_access_token"] = payload.whatsapp_access_token
    if updates:
        await session.execute(update(Client).where(Client.id == client.id).values(**updates))
        await session.commit()
        await session.refresh(client)
    return AppConfigOut(
        id=client.id,
        whatsapp_phone_number_id=client.whatsapp_phone_number_id or "",
        whatsapp_access_token=client.whatsapp_access_token or "",
        updated_at=client.created_at,
    )
