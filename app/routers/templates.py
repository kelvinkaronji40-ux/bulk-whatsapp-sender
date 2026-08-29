from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_session
from app.models import Template
from app.schemas import TemplateOut
from app.services import create_meta_template

router = APIRouter(prefix="/templates", tags=["templates"])


class MetaCreateRequest(BaseModel):
    name: str
    language: str = "en_US"
    category: str = "MARKETING"
    body: str
    header: str | None = None
    footer: str | None = None


@router.get("/", response_model=list[TemplateOut])
async def list_templates(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Template).order_by(Template.created_at.desc()))).scalars().all()
    return rows


@router.post("/", response_model=TemplateOut)
async def create_local_template(payload: MetaCreateRequest, session: AsyncSession = Depends(get_session)):
    t = Template(
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
async def submit_to_meta(payload: MetaCreateRequest, session: AsyncSession = Depends(get_session)):
    ok, result = await create_meta_template(
        name=payload.name,
        language=payload.language,
        category=payload.category,
        body=payload.body,
        header=payload.header,
        footer=payload.footer,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=result)
    t = Template(
        name=payload.name,
        language=payload.language,
        category=payload.category,
        body=payload.body,
        header=payload.header,
        footer=payload.footer,
        status="submitted",
        meta_template_id=str(result.get("id", "")),
    )
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return {"status": "submitted", "template": t}
