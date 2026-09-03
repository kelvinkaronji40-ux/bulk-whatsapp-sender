from __future__ import annotations

import asyncio
import csv
import io
import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, load_settings_from_db
from app.models import Campaign, CampaignContact, Contact, OptOut, CampaignMedia, Client
from app.schemas import CampaignMediaIn


async def _get_settings(session: AsyncSession, client_id: int | None = None) -> Settings:
    settings = Settings.load()
    db_settings = await load_settings_from_db(session)
    if db_settings.whatsapp_phone_number_id:
        settings.whatsapp_phone_number_id = db_settings.whatsapp_phone_number_id
    if db_settings.whatsapp_access_token:
        settings.whatsapp_access_token = db_settings.whatsapp_access_token
    if client_id is not None:
        client = (await session.execute(select(Client).where(Client.id == client_id))).scalar_one_or_none()
        if client:
            if client.whatsapp_phone_number_id:
                settings.whatsapp_phone_number_id = client.whatsapp_phone_number_id
            if client.whatsapp_access_token:
                settings.whatsapp_access_token = client.whatsapp_access_token
    return settings


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


async def _send_whatsapp_text(session: AsyncSession, phone: str, body: str, client_id: int | None = None, media: list[dict] | None = None) -> tuple[bool, str | None]:
    settings = await _get_settings(session, client_id=client_id)
    if not settings.whatsapp_phone_number_id or not settings.whatsapp_access_token:
        return False, "missing_whatsapp_config"
    url = f"https://graph.facebook.com/v19.0/{settings.whatsapp_phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    text = body.rstrip()
    if not text.endswith("Tisement Media"):
        text += "\n\n- Powered by Tisement Media"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if media:
                for item in media:
                    payload: dict[str, Any] = {
                        "messaging_product": "whatsapp",
                        "to": phone,
                        "type": item.get("media_type", "image"),
                    }
                    mtype = item.get("media_type", "image")
                    if mtype == "document":
                        payload["document"] = {"link": item["media_url"]}
                        if item.get("caption"):
                            payload["document"]["caption"] = item["caption"]
                    else:
                        payload[mtype] = {"link": item["media_url"]}
                        if item.get("caption"):
                            payload[mtype]["caption"] = item["caption"]
                    r = await client.post(url, json=payload, headers=headers)
                    if r.status_code == 429 or r.status_code >= 500:
                        for attempt in range(3):
                            await asyncio.sleep(1.5 * (attempt + 1))
                            r = await client.post(url, json=payload, headers=headers)
                            if r.status_code < 400:
                                break
                    if r.status_code >= 400:
                        return False, f"http_{r.status_code}: {r.text}"
            payload = {
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "text",
                "text": {"body": text, "preview_url": True},
            }
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code == 429 or r.status_code >= 500:
                for attempt in range(3):
                    await asyncio.sleep(1.5 * (attempt + 1))
                    r = await client.post(url, json=payload, headers=headers)
                    if r.status_code < 400:
                        return True, None
            r.raise_for_status()
            return True, None
    except httpx.HTTPStatusError as e:
        return False, f"http_{e.response.status_code}"
    except Exception as e:
        return False, str(e)


async def create_meta_template(name: str, language: str, category: str, body: str, header: str | None = None, footer: str | None = None) -> tuple[bool, dict | str]:
    if not settings.whatsapp_phone_number_id or not settings.whatsapp_access_token:
        return False, "missing_whatsapp_config"
    url = f"https://graph.facebook.com/v19.0/{settings.whatsapp_phone_number_id}/message_templates"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}", "Content-Type": "application/json"}
    payload: dict[str, Any] = {
        "name": name,
        "language": language,
        "category": category,
        "components": [{"type": "body", "text": body}],
    }
    if header:
        payload["components"].insert(0, {"type": "header", "format": "TEXT", "text": header})
    if footer:
        payload["components"].append({"type": "footer", "text": footer})
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, json=payload, headers=headers)
            data = r.json()
            if r.status_code >= 400:
                return False, data.get("error", {}).get("message", str(data))
            return True, data
    except Exception as e:
        return False, str(e)


async def import_contacts_csv(session: AsyncSession, content: bytes, client_id: int) -> dict[str, int]:
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
        existing = (await session.execute(select(Contact).where(Contact.client_id == client_id, Contact.phone == phone))).scalar_one_or_none()
        if existing:
            duplicates += 1
            continue
        contact = Contact(
            client_id=client_id,
            phone=phone,
            name=row.get("name") or row.get("Name") or None,
            source=row.get("source") or "csv",
        )
        session.add(contact)
        imported += 1
    await session.commit()
    return {"imported": imported, "skipped": skipped, "duplicates": duplicates}


async def create_campaign(session: AsyncSession, payload: dict[str, Any]) -> Campaign:
    client_id = payload.get("client_id")
    scheduled_at = payload.get("scheduled_at")
    status = "draft"
    if scheduled_at:
        if isinstance(scheduled_at, str):
            scheduled_at = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
        if scheduled_at > datetime.now(timezone.utc):
            status = "scheduled"
    campaign = Campaign(
        client_id=client_id,
        name=payload["name"],
        body_text=payload["body_text"],
        template_name=payload.get("template_name"),
        status=status,
        scheduled_at=scheduled_at,
    )
    session.add(campaign)
    await session.commit()
    await session.refresh(campaign)
    return campaign


async def add_recipients_to_campaign(session: AsyncSession, campaign_id: int, contact_ids: list[int], client_id: int | None = None) -> int:
    campaign = (await session.execute(select(Campaign).where(Campaign.id == campaign_id))).scalar_one_or_none()
    if not campaign:
        return 0
    if client_id is None:
        client_id = campaign.client_id
    added = 0
    for cid in contact_ids:
        contact = (await session.execute(select(Contact).where(Contact.id == cid))).scalar_one_or_none()
        if not contact or contact.client_id != client_id:
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
        cc = CampaignContact(client_id=client_id, campaign_id=campaign_id, contact_id=cid, status="queued")
        session.add(cc)
        added += 1
    await session.commit()
    return added


async def send_campaign(session: AsyncSession, campaign_id: int, client_id: int | None = None, limit: int | None = None) -> dict[str, int]:
    campaign = (await session.execute(select(Campaign).where(Campaign.id == campaign_id))).scalar_one_or_none()
    if not campaign:
        return {"sent": 0, "failed": 0, "skipped": 0}
    if client_id is None:
        client_id = campaign.client_id
    q = select(CampaignContact).where(CampaignContact.campaign_id == campaign_id, CampaignContact.client_id == client_id, CampaignContact.status == "queued")
    if limit:
        q = q.limit(limit)
    rows = (await session.execute(q)).scalars().all()
    media = (await session.execute(
        select(CampaignMedia).where(CampaignMedia.campaign_id == campaign_id, CampaignMedia.client_id == client_id).order_by(CampaignMedia.sort_order.asc())
    )).scalars().all()
    media_payload = [
        {"media_type": m.media_type, "media_url": m.media_url, "caption": m.caption}
        for m in media
    ]
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
        ok, err = await _send_whatsapp_text(session, contact.phone, campaign.body_text, client_id=client_id, media=media_payload)
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


async def run_send_job(session: AsyncSession, campaign_id: int) -> dict[str, int]:
    campaign = (await session.execute(select(Campaign).where(Campaign.id == campaign_id))).scalar_one_or_none()
    if not campaign:
        return {"sent": 0, "failed": 0, "skipped": 0}
    if campaign.status in {"sent", "partial", "sending"}:
        return {"sent": 0, "failed": 0, "skipped": 0}
    campaign.status = "sending"
    await session.commit()
    return await send_campaign(session, campaign_id)


async def run_due_campaigns_on_startup(session_factory):
    async with session_factory() as session:
        now = datetime.now(timezone.utc)
        due = (await session.execute(
            select(Campaign).where(
                Campaign.scheduled_at != None,
                Campaign.status == "scheduled",
                Campaign.scheduled_at <= now,
            )
        )).scalars().all()
        for camp in due:
            await run_send_job(session, camp.id)


async def process_opt_out_webhook(session: AsyncSession, payload: dict) -> dict:
    changes = payload.get("changes", [])
    for change in changes:
        value = change.get("value", {})
        if value.get("statuses"):
            for status in value["statuses"]:
                recipient = status.get("recipient_id") or status.get("to")
                if not recipient:
                    continue
                contact = (await session.execute(select(Contact).where(Contact.phone == recipient))).scalar_one_or_none()
                if not contact:
                    continue
                if status.get("status") == "read":
                    pass
        if value.get("messages"):
            for message in value["messages"]:
                text = message.get("text", {}).get("body", "").lower()
                phone = message.get("from")
                if not phone:
                    continue
                contact = (await session.execute(select(Contact).where(Contact.phone == phone))).scalar_one_or_none()
                if not contact:
                    continue
                if any(t in text for t in ["stop", "unsubscribe", "opt out"]):
                    contact.opted_out = True
                    contact.opted_out_at = datetime.utcnow()
                    session.add(OptOut(client_id=contact.client_id, contact_id=contact.id, reason=text[:255]))
                    await session.commit()
    return {"status": "ok"}
