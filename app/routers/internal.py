from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_session
from app.models import Campaign
from app.services import run_send_job

router = APIRouter()

CRON_TOKEN = "cron_bws_7f3a9c2e8d1a4b6f0e5c7a9d2b4f6e8a"


@router.get("/internal/due-campaigns")
async def run_due_campaigns(x_cron_token: str | None = None, session: AsyncSession = Depends(get_session)):
    if x_cron_token != CRON_TOKEN:
        raise HTTPException(status_code=403, detail="forbidden")
    async with session:
        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        due = (await session.execute(
            select(Campaign).where(
                Campaign.scheduled_at != None,
                Campaign.status == "scheduled",
                Campaign.scheduled_at <= now,
            )
        )).scalars().all()
        results = []
        for camp in due:
            res = await run_send_job(session, camp.id)
            results.append({"id": camp.id, **res})
        return {"due": len(due), "results": results}
