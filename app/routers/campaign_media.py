from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sqla_delete

from app.database import get_session
from app.models import Campaign, CampaignMedia
from app.schemas import CampaignMediaIn, CampaignMediaOut
from app.auth import get_current_client

router = APIRouter(prefix="/campaigns", tags=["campaign-media"])


@router.get("/{campaign_id}/media", response_model=list[CampaignMediaOut])
async def list_media(campaign_id: int, session: AsyncSession = Depends(get_session), client=Depends(get_current_client)):
    campaign = (await session.execute(select(Campaign).where(Campaign.id == campaign_id, Campaign.client_id == client.id))).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign_not_found")
    rows = (await session.execute(
        select(CampaignMedia).where(CampaignMedia.campaign_id == campaign_id, CampaignMedia.client_id == client.id).order_by(CampaignMedia.sort_order.asc())
    )).scalars().all()
    return rows


@router.post("/{campaign_id}/media", response_model=CampaignMediaOut)
async def add_media(campaign_id: int, payload: CampaignMediaIn, session: AsyncSession = Depends(get_session), client=Depends(get_current_client)):
    campaign = (await session.execute(select(Campaign).where(Campaign.id == campaign_id, Campaign.client_id == client.id))).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign_not_found")
    m = CampaignMedia(client_id=client.id, campaign_id=campaign_id, media_type=payload.media_type, media_url=payload.media_url, caption=payload.caption, sort_order=payload.sort_order)
    session.add(m)
    await session.commit()
    await session.refresh(m)
    return m


@router.delete("/{campaign_id}/media/{media_id}")
async def delete_media(campaign_id: int, media_id: int, session: AsyncSession = Depends(get_session), client=Depends(get_current_client)):
    campaign = (await session.execute(select(Campaign).where(Campaign.id == campaign_id, Campaign.client_id == client.id))).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign_not_found")
    await session.execute(sqla_delete(CampaignMedia).where(CampaignMedia.id == media_id, CampaignMedia.campaign_id == campaign_id, CampaignMedia.client_id == client.id))
    await session.commit()
    return {"status": "ok"}
