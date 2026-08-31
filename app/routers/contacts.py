from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi import UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_session
from app.models import Contact, Campaign, CampaignContact
from app.schemas import ContactIn, ContactOut, CampaignIn, CampaignOut, CampaignDetail, CSVUploadResponse
from app.services import import_contacts_csv, create_campaign, add_recipients_to_campaign, send_campaign, _normalize_phone
from app.auth import get_current_client

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("/", response_model=list[ContactOut])
async def list_contacts(session: AsyncSession = Depends(get_session), client=Depends(get_current_client)):
    rows = (await session.execute(select(Contact).where(Contact.client_id == client.id).order_by(Contact.created_at.desc()))).scalars().all()
    return rows


@router.post("/", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
async def create_contact(payload: ContactIn, session: AsyncSession = Depends(get_session), client=Depends(get_current_client)):
    from app.services import _normalize_phone
    phone = _normalize_phone(payload.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="invalid_phone")
    existing = (await session.execute(select(Contact).where(Contact.client_id == client.id, Contact.phone == phone))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="duplicate_contact")
    c = Contact(client_id=client.id, phone=phone, name=payload.name, source=payload.source)
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c


@router.post("/import-csv", response_model=CSVUploadResponse)
async def import_csv(file: UploadFile = File(...), session: AsyncSession = Depends(get_session), client=Depends(get_current_client)):
    content = await file.read()
    result = await import_contacts_csv(session, content, client_id=client.id)
    return CSVUploadResponse(**result)


@router.get("/export-csv")
async def export_csv(session: AsyncSession = Depends(get_session), client=Depends(get_current_client)):
    rows = (await session.execute(select(Contact).where(Contact.client_id == client.id))).scalars().all()
    out = "phone,name,source,opted_out\n"
    for c in rows:
        out += f"{c.phone},{c.name or ''},{c.source or ''},{c.opted_out}\n"
    return HTMLResponse(content=out, media_type="text/csv")
