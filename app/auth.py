from fastapi import HTTPException, Security, FastAPI, Request, Depends
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_session
from app.models import Client

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_current_client(request: Request, session: AsyncSession = Depends(get_session), api_key: str | None = Security(api_key_header)) -> Client:
    key = api_key or request.headers.get("x-api-key")
    if not key:
        raise HTTPException(status_code=401, detail="Missing API key")
    client = (await session.execute(select(Client).where(Client.api_key == key))).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return client
