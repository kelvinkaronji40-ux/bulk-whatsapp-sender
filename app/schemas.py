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


class CampaignMediaIn(BaseModel):
    media_type: str = "image"
    media_url: str
    caption: Optional[str] = None
    sort_order: int = 0


class CampaignMediaOut(CampaignMediaIn):
    id: int
    campaign_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CampaignOut(CampaignIn):
    id: int
    status: str
    created_at: datetime
    media: list[CampaignMediaOut] = []

    model_config = ConfigDict(from_attributes=True)


class CampaignDetail(CampaignOut):
    contacts: list[dict] = []
    stats: dict = {}


class CSVUploadResponse(BaseModel):
    imported: int
    skipped: int
    duplicates: int


class TemplateIn(BaseModel):
    name: str
    language: str = "en_US"
    category: str = "MARKETING"
    body: str
    header: Optional[str] = None
    footer: Optional[str] = None


class TemplateOut(TemplateIn):
    id: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppConfigIn(BaseModel):
    whatsapp_phone_number_id: str
    whatsapp_access_token: str
    ai_provider: Optional[str] = None
    ai_api_key: Optional[str] = None


class AppConfigOut(AppConfigIn):
    id: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AIGenerateIn(BaseModel):
    prompt: str
    context: str = "campaign"  # campaign | template
    provider: Optional[str] = None


class AIGenerateOut(BaseModel):
    text: str

    model_config = ConfigDict(from_attributes=True)
