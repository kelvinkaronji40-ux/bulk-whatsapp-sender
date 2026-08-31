from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_session
from app.models import Template
from app.schemas import TemplateOut
from app.services import create_meta_template
from app.auth import get_current_client

router = APIRouter(prefix="/templates", tags=["templates"])


class MetaCreateRequest(BaseModel):
    name: str
    language: str = "en_US"
    category: str = "MARKETING"
    body: str
    header: str | None = None
    footer: str | None = None


@router.get("/", response_model=list[TemplateOut])
async def list_templates(session: AsyncSession = Depends(get_session), client=Depends(get_current_client)):
    rows = (await session.execute(select(Template).where(Template.client_id == client.id).order_by(Template.created_at.desc()))).scalars().all()
    return rows


@router.post("/", response_model=TemplateOut)
async def create_local_template(payload: MetaCreateRequest, session: AsyncSession = Depends(get_session), client=Depends(get_current_client)):
    t = Template(
        client_id=client.id,
        name=payload.name,
        language=payload.language,
        category=payload.category,
        body=payload.body,
        header=payload.header,
        footer=payload.footer,
        status="pending_meta",
    )
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return t


@router.post("/submit-meta")
async def submit_to_meta(payload: MetaCreateRequest, session: AsyncSession = Depends(get_session), client=Depends(get_current_client)):
    ok, result = await create_meta_template(
        name=payload.name,
        language=payload.language,
        category=payload.category,
        body=payload.body,
        header=payload.header,
        footer=payload.footer,
    )
    t = (await session.execute(select(Template).where(Template.client_id == client.id, Template.name == payload.name))).scalar_one_or_none()
    if not t:
        t = Template(
            client_id=client.id,
            name=payload.name,
            language=payload.language,
            category=payload.category,
            body=payload.body,
            header=payload.header,
            footer=payload.footer,
        )
        session.add(t)
    if not ok:
        t.status = "failed"
        t.error = str(result)
        await session.commit()
        await session.refresh(t)
        return {"status": "failed", "template": TemplateOut.model_validate(t, from_attributes=True)}
    data = result if isinstance(result, dict) else {}
    t.status = "submitted"
    t.meta_template_id = str(data.get("id", ""))
    t.error = None
    await session.commit()
    await session.refresh(t)
    return {"status": "submitted", "template": TemplateOut.model_validate(t, from_attributes=True)}

