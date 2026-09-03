from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, delete
from datetime import datetime

from app.database import get_session
from app.models import Contact, OptOut
from app.auth import get_current_client

router = APIRouter(prefix="/opt-outs", tags=["opt-outs"])


@router.get("/")
async def list_opt_outs(session: AsyncSession = Depends(get_session), client=Depends(get_current_client)):
    rows = (await session.execute(
        select(OptOut.id, OptOut.contact_id, OptOut.reason, OptOut.created_at)
        .where(OptOut.client_id == client.id)
        .order_by(OptOut.created_at.desc())
    )).all()
    return [dict(r._mapping) for r in rows]


@router.post("/")
async def opt_out(contact_id: int = Body(...), reason: str | None = Body(None), session: AsyncSession = Depends(get_session), client=Depends(get_current_client)):
    contact = (await session.execute(select(Contact).where(Contact.id == contact_id, Contact.client_id == client.id))).scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="contact_not_found")
    contact.opted_out = True
    contact.opted_out_at = datetime.utcnow()
    session.add(OptOut(client_id=client.id, contact_id=contact.id, reason=reason))
    await session.commit()
    return {"status": "ok"}


@router.delete("/{contact_id}")
async def opt_in(contact_id: int, session: AsyncSession = Depends(get_session), client=Depends(get_current_client)):
    contact = (await session.execute(select(Contact).where(Contact.id == contact_id, Contact.client_id == client.id))).scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="contact_not_found")
    contact.opted_out = False
    contact.opted_out_at = None
    await session.execute(delete(OptOut).where(OptOut.contact_id == contact_id, OptOut.client_id == client.id))
    await session.commit()
    return {"status": "ok"}
