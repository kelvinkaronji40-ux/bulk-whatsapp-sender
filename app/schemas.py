from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class ContactIn(BaseModel):
    phone: str
    name: Optional[str] = None
    source: Optional[str] = None


class ContactOut(ContactIn):
    id: int
    opted_out: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CampaignIn(BaseModel):
    name: str
    body_text: str
    template_name: Optional[str] = None
    scheduled_at: Optional[datetime] = None


class CampaignOut(CampaignIn):
    id: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CampaignDetail(CampaignOut):
    contacts: list[dict] = []
    stats: dict = {}


class CSVUploadResponse(BaseModel):
    imported: int
    skipped: int
    duplicates: int
