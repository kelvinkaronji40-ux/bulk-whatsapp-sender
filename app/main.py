from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.database import init_db
from app.routers import contacts, campaigns


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Bulk WhatsApp Sender", version="0.1.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(contacts.router)
app.include_router(campaigns.router)


@app.get("/", response_class=HTMLResponse)
async def root():
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Bulk WhatsApp Sender</title>
  <style>
    :root { --bg:#0f172a; --surface:#1e293b; --text:#f8fafc; --muted:#94a3b8; --accent:#0ea5e9; }
    body { font-family: Inter, system-ui, sans-serif; background: var(--bg); color: var(--text); margin: 0; }
    header { padding: 24px; border-bottom: 1px solid #334155; }
    main { padding: 24px; max-width: 960px; margin: 0 auto; }
    h1 { font-size: 22px; margin: 0 0 6px; }
    p { color: var(--muted); }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-top: 24px; }
    .card { background: var(--surface); border: 1px solid #334155; border-radius: 14px; padding: 20px; }
    a { color: var(--accent); text-decoration: none; font-weight: 600; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <header>
    <h1>Bulk WhatsApp Sender</h1>
    <p>Contacts, campaigns, CSV import, and send queue</p>
  </header>
  <main>
    <div class="grid">
      <div class="card"><h3>Contacts</h3><p>Manage your contact list</p><a href="/static/index.html">Open Contacts</a></div>
      <div class="card"><h3>Campaigns</h3><p>Create and send campaigns</p><a href="/static/campaigns.html">Open Campaigns</a></div>
      <div class="card"><h3>API Docs</h3><p>REST API reference</p><a href="/docs">Open API</a></div>
    </div>
  </main>
  <footer style="padding:18px 24px;text-align:center;color:#94a3b8;font-size:12px;border-top:1px solid #334155;margin-top:24px;">
    Powered by <a href="https://tisementmedia.com" target="_blank" style="color:#0ea5e9;text-decoration:none;">Tisement Media</a> • Bulk WhatsApp Sender
  </footer>
</body>
</html>
"""
