from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text
from app.models import Base

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///" + str(Path.home() / ".bulk_whatsapp" / "bulk.db"),
)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)

def get_session_factory():
    return async_session


async def init_db() -> None:
    db_path = Path(DATABASE_URL.replace("sqlite+aiosqlite:///", ""))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight migration for existing databases
        def migrate(sync_conn):
            try:
                sync_conn.execute(text("CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, api_key TEXT UNIQUE, whatsapp_phone_number_id TEXT, whatsapp_access_token TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
                cols = [r[1] for r in sync_conn.execute(text("PRAGMA table_info(contacts)")).fetchall()]
                if "client_id" not in cols:
                    sync_conn.execute(text("ALTER TABLE contacts ADD COLUMN client_id INTEGER"))
                    sync_conn.execute(text("CREATE INDEX IF NOT EXISTS ix_contacts_client_id ON contacts(client_id)"))
                cols = [r[1] for r in sync_conn.execute(text("PRAGMA table_info(campaigns)")).fetchall()]
                if "client_id" not in cols:
                    sync_conn.execute(text("ALTER TABLE campaigns ADD COLUMN client_id INTEGER"))
                    sync_conn.execute(text("CREATE INDEX IF NOT EXISTS ix_campaigns_client_id ON campaigns(client_id)"))
                cols = [r[1] for r in sync_conn.execute(text("PRAGMA table_info(campaign_contacts)")).fetchall()]
                if "client_id" not in cols:
                    sync_conn.execute(text("ALTER TABLE campaign_contacts ADD COLUMN client_id INTEGER"))
                    sync_conn.execute(text("CREATE INDEX IF NOT EXISTS ix_campaign_contacts_client_id ON campaign_contacts(client_id)"))
                cols = [r[1] for r in sync_conn.execute(text("PRAGMA table_info(templates)")).fetchall()]
                if "client_id" not in cols:
                    sync_conn.execute(text("ALTER TABLE templates ADD COLUMN client_id INTEGER"))
                    sync_conn.execute(text("CREATE INDEX IF NOT EXISTS ix_templates_client_id ON templates(client_id)"))
                if "error" not in cols:
                    sync_conn.execute(text("ALTER TABLE templates ADD COLUMN error TEXT"))
                sync_conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_templates_client_name ON templates(client_id, name)"))
                cols_contacts = [r[1] for r in sync_conn.execute(text("PRAGMA table_info(contacts)")).fetchall()]
                if "opted_out_at" not in cols_contacts:
                    sync_conn.execute(text("ALTER TABLE contacts ADD COLUMN opted_out_at TIMESTAMP"))
                sync_conn.execute(text("CREATE TABLE IF NOT EXISTS opt_outs (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, contact_id INTEGER, reason TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
                sync_conn.execute(text("CREATE INDEX IF NOT EXISTS ix_opt_outs_client_contact ON opt_outs(client_id, contact_id)"))
                sync_conn.execute(text("CREATE TABLE IF NOT EXISTS campaign_media (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, campaign_id INTEGER, media_type TEXT DEFAULT 'image', media_url TEXT, caption TEXT, sort_order INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
                sync_conn.execute(text("CREATE INDEX IF NOT EXISTS ix_campaign_media_campaign ON campaign_media(campaign_id)"))
                # Ensure a default client exists for single-tenant mode
                row = sync_conn.execute(text("SELECT id FROM clients LIMIT 1")).fetchone()
                if not row:
                    default_key = os.getenv("DEFAULT_CLIENT_API_KEY") or secrets.token_hex(24)
                    sync_conn.execute(text("INSERT INTO clients (name, api_key) VALUES ('Default', :k)"), {"k": default_key})
                    print(f"Created default client. API key: {default_key}")
            except Exception:
                pass
        await conn.run_sync(migrate)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
