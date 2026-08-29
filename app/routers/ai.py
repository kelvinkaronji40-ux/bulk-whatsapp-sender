from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

import httpx

from app.config import load_settings_from_db
from app.database import get_session
from app.schemas import AIGenerateIn, AIGenerateOut

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/generate", response_model=AIGenerateOut)
async def generate_ai_text(payload: AIGenerateIn, session: AsyncSession = Depends(get_session)):
    settings = await load_settings_from_db(session)
    provider = (payload.provider or settings.ai_provider or "").lower().strip()
    api_key = settings.ai_api_key
    if not provider or not api_key:
        raise HTTPException(status_code=400, detail="ai_settings_missing")
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="empty_prompt")
    try:
        if provider == "openai":
            generated = await _generate_openai(api_key, prompt)
        elif provider == "openrouter":
            generated = await _generate_openrouter(api_key, prompt)
        else:
            raise HTTPException(status_code=400, detail="unsupported_ai_provider")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"{type(e).__name__}: {e}")
    return AIGenerateOut(text=generated)


async def _generate_openai(api_key: str, prompt: str) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    json = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You write concise WhatsApp messages and templates. Keep it short and clear."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 200,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, headers=headers, json=json)
        r.raise_for_status()
        data = r.json()
        if "choices" not in data:
            raise HTTPException(status_code=400, detail=f"AI provider returned unexpected response: {data}")
        return data["choices"][0]["message"]["content"]


async def _generate_openrouter(api_key: str, prompt: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    json = {
        "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "messages": [
            {"role": "system", "content": "You write concise WhatsApp messages and templates. Keep it short and clear."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 200,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, headers=headers, json=json)
        r.raise_for_status()
        data = r.json()
        if "choices" not in data:
            raise HTTPException(status_code=400, detail=f"AI provider returned unexpected response: {data}")
        return data["choices"][0]["message"]["content"]
