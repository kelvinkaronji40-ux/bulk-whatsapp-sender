from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_session
from app.models import Template
from app.schemas import TemplateIn, TemplateOut

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("/", response_model=list[TemplateOut])
async def list_templates(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Template).order_by(Template.created_at.desc()))).scalars().all()
    return rows


@router.post("/", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(payload: TemplateIn, session: AsyncSession = Depends(get_session)):
    t = Template(**payload.model_dump())
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return t


@router.get("/{template_id}", response_model=TemplateOut)
async def get_template(template_id: int, session: AsyncSession = Depends(get_session)):
    t = (await session.execute(select(Template).where(Template.id == template_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="template_not_found")
    return t
