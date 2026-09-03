from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import init_db, get_session, get_session_factory
from app.routers import contacts, campaigns, templates, settings as settings_router, ai, internal, optouts
from app.auth import router as auth_router
from app.services import run_due_campaigns_on_startup, process_opt_out_webhook


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await run_due_campaigns_on_startup(get_session_factory())
    yield


app = FastAPI(title="Bulk WhatsApp Sender", version="0.1.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(contacts.router)
app.include_router(campaigns.router)
app.include_router(templates.router)
app.include_router(settings_router.router)
app.include_router(ai.router)
app.include_router(auth_router)
app.include_router(internal.router)
app.include_router(optouts.router)


@app.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    result = await process_opt_out_webhook(session, body)
    return result


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse("""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Bulk WhatsApp Sender</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: Inter, system-ui, sans-serif; background: #0f172a; color: #f8fafc; }
    .wrap { max-width: 420px; margin: 0 auto; padding: 80px 20px; text-align: center; }
    h1 { font-size: 28px; font-weight: 800; margin-bottom: 8px; }
    p { color: #94a3b8; margin-bottom: 28px; }
    .btn { display: inline-flex; align-items: center; justify-content: center; width: 100%; padding: 14px; border-radius: 12px; border: 0; font-size: 15px; font-weight: 700; cursor: pointer; text-decoration: none; margin: 8px 0; }
    .btn-primary { background: #0ea5e9; color: #fff; }
    .btn-secondary { background: #334155; color: #f8fafc; }
    footer { margin-top: 40px; color: #64748b; font-size: 12px; }
    footer a { color: #0ea5e9; text-decoration: none; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Bulk WhatsApp Sender</h1>
    <p>Send WhatsApp campaigns, manage contacts, and track delivery.</p>
    <a class="btn btn-primary" href="/static/index.html">Open Dashboard</a>
    <a class="btn btn-secondary" href="/docs">View API Docs</a>
    <footer>Powered by <a href="https://tisementmedia.com" target="_blank">Tisement Media</a></footer>
  </div>
</body>
</html>
""")
