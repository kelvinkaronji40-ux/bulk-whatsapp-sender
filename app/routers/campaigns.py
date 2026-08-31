from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_session
from app.models import Campaign, CampaignContact, Contact
from app.schemas import CampaignIn, CampaignOut, CampaignDetail
from app.services import create_campaign, add_recipients_to_campaign, send_campaign
from app.auth import get_current_client

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("/", response_model=list[CampaignOut])
async def list_campaigns(session: AsyncSession = Depends(get_session), client=Depends(get_current_client)):
    rows = (await session.execute(select(Campaign).where(Campaign.client_id == client.id).order_by(Campaign.created_at.desc()))).scalars().all()
    return rows


@router.post("/", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
async def create_campaign_endpoint(payload: CampaignIn, session: AsyncSession = Depends(get_session), client=Depends(get_current_client)):
    camp = await create_campaign(session, {**payload.model_dump(), "client_id": client.id})
    return camp


@router.get("/{campaign_id}", response_model=CampaignDetail)
async def get_campaign(campaign_id: int, session: AsyncSession = Depends(get_session), client=Depends(get_current_client)):
    camp = (await session.execute(select(Campaign).where(Campaign.client_id == client.id, Campaign.id == campaign_id))).scalar_one_or_none()
    if not camp:
        raise HTTPException(status_code=404, detail="campaign_not_found")
    ccs = (await session.execute(
        select(CampaignContact).where(CampaignContact.campaign_id == campaign_id, CampaignContact.client_id == client.id)
    )).scalars().all()
    contact_ids = [cc.contact_id for cc in ccs]
    contacts = []
    if contact_ids:
        rows = (await session.execute(select(Contact).where(Contact.client_id == client.id, Contact.id.in_(contact_ids)))).scalars().all()
        contacts = [{"id": r.id, "phone": r.phone, "name": r.name} for r in rows]
    stats = {
        "queued": sum(1 for cc in ccs if cc.status == "queued"),
        "sent": sum(1 for cc in ccs if cc.status == "sent"),
        "failed": sum(1 for cc in ccs if cc.status == "failed"),
        "skipped": sum(1 for cc in ccs if cc.status == "skipped"),
    }
    return CampaignDetail(
        id=camp.id, name=camp.name, body_text=camp.body_text, template_name=camp.template_name,
        status=camp.status, scheduled_at=camp.scheduled_at, created_at=camp.created_at,
        contacts=contacts, stats=stats
    )


@router.post("/{campaign_id}/recipients")
async def add_recipients(campaign_id: int, contact_ids: list[int], session: AsyncSession = Depends(get_session), client=Depends(get_current_client)):
    added = await add_recipients_to_campaign(session, campaign_id, contact_ids, client_id=client.id)
    return {"added": added}


@router.post("/{campaign_id}/send")
async def send_campaign_endpoint(campaign_id: int, limit: int | None = None, session: AsyncSession = Depends(get_session), client=Depends(get_current_client)):
    result = await send_campaign(session, campaign_id, client_id=client.id, limit=limit)
    return result
