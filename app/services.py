from __future__ import annotations

import csv
import io
import os
import re
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Campaign, CampaignContact, Contact


settings = Settings.load()


def _normalize_phone(raw: str) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    if len(digits) < 7 or len(digits) > 15:
        return None
    if len(digits) == 10 and raw.strip().startswith("0"):
        digits = "254" + digits[1:]
    return digits


async def _send_whatsapp_text(phone: str, body: str) -> tuple[bool, str | None]:
    if not settings.whatsapp_phone_number_id or not settings.whatsapp_access_token:
        return False, "missing_whatsapp_config"
    url = f"https://graph.facebook.com/v19.0/{settings.whatsapp_phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": body},
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            return True, None
    except httpx.HTTPStatusError as e:
        return False, f"http_{e.response.status_code}"
    except Exception as e:
        return False, str(e)


async def import_contacts_csv(session: AsyncSession, content: bytes) -> dict[str, int]:
    text = content.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    imported = 0
    skipped = 0
    duplicates = 0
    seen: set[str] = set()
    for row in reader:
        raw_phone = row.get("phone") or row.get("Phone") or row.get("mobile") or ""
        phone = _normalize_phone(raw_phone)
        if not phone:
            skipped += 1
            continue
        if phone in seen:
            duplicates += 1
            continue
        seen.add(phone)
        existing = (await session.execute(select(Contact).where(Contact.phone == phone))).scalar_one_or_none()
        if existing:
            duplicates += 1
            continue
        contact = Contact(
            phone=phone,
            name=row.get("name") or row.get("Name") or None,
            source=row.get("source") or "csv",
        )
        session.add(contact)
        imported += 1
    await session.commit()
    return {"imported": imported, "skipped": skipped, "duplicates": duplicates}


async def create_campaign(session: AsyncSession, payload: dict[str, Any]) -> Campaign:
    campaign = Campaign(
        name=payload["name"],
        body_text=payload["body_text"],
        template_name=payload.get("template_name"),
        status="draft",
        scheduled_at=payload.get("scheduled_at"),
    )
    session.add(campaign)
    await session.commit()
    await session.refresh(campaign)
    return campaign


async def add_recipients_to_campaign(session: AsyncSession, campaign_id: int, contact_ids: list[int]) -> int:
    campaign = (await session.execute(select(Campaign).where(Campaign.id == campaign_id))).scalar_one_or_none()
    if not campaign:
        return 0
    added = 0
    for cid in contact_ids:
        contact = (await session.execute(select(Contact).where(Contact.id == cid))).scalar_one_or_none()
        if not contact:
            continue
        if contact.opted_out:
            continue
        exists = (await session.execute(
            select(CampaignContact).where(
                CampaignContact.campaign_id == campaign_id,
                CampaignContact.contact_id == cid,
            )
        )).scalar_one_or_none()
        if exists:
            continue
        cc = CampaignContact(campaign_id=campaign_id, contact_id=cid, status="queued")
        session.add(cc)
        added += 1
    await session.commit()
    return added


async def send_campaign(session: AsyncSession, campaign_id: int, limit: int | None = None) -> dict[str, int]:
    campaign = (await session.execute(select(Campaign).where(Campaign.id == campaign_id))).scalar_one_or_none()
    if not campaign:
        return {"sent": 0, "failed": 0, "skipped": 0}
    q = select(CampaignContact).where(CampaignContact.campaign_id == campaign_id, CampaignContact.status == "queued")
    if limit:
        q = q.limit(limit)
    rows = (await session.execute(q)).scalars().all()
    sent = 0
    failed = 0
    skipped = 0
    for cc in rows:
        contact = (await session.execute(select(Contact).where(Contact.id == cc.contact_id))).scalar_one_or_none()
        if not contact or contact.opted_out:
            cc.status = "skipped"
            cc.error = "opted_out"
            skipped += 1
            continue
        ok, err = await _send_whatsapp_text(contact.phone, campaign.body_text)
        cc.sent_at = datetime.utcnow()
        if ok:
            cc.status = "sent"
            sent += 1
        else:
            cc.status = "failed"
            cc.error = err
            failed += 1
    if sent or failed:
        campaign.status = "sent" if failed == 0 else ("partial" if sent > 0 else "failed")
        await session.commit()
    return {"sent": sent, "failed": failed, "skipped": skipped}
