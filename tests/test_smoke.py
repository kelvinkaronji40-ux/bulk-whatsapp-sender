import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.main import app
from app.database import get_session
from app.models import Base
from app.auth import get_current_client

TEST_API_KEY = "test_api_key_123"


@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture()
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


@pytest.fixture()
async def client(db_session: AsyncSession):
    from app.models import Client
    c = Client(name="Test Client", api_key=TEST_API_KEY)
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)

    async def _override_session():
        yield db_session
    app.dependency_overrides[get_session] = _override_session

    async def _override_client():
        return c
    app.dependency_overrides[get_current_client] = _override_client

    headers = {"X-API-Key": TEST_API_KEY}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    r = await client.get("/")
    assert r.status_code == 200
    assert "Bulk WhatsApp Sender" in r.text


@pytest.mark.asyncio
async def test_contacts_crud(client: AsyncClient):
    r = await client.post("/contacts/", json={"phone": "+254 704 443 031", "name": "Test", "source": "web"})
    assert r.status_code == 201
    body = r.json()
    assert body["phone"] == "254704443031"
    assert body["name"] == "Test"
    assert body["opted_out"] is False

    r = await client.get("/contacts/")
    assert r.status_code == 200
    assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_campaigns_crud(client: AsyncClient):
    payload = {"name": "Launch", "body_text": "Hello {{name}}", "template_name": None, "client_id": 1}
    r = await client.post("/campaigns/", json=payload)
    assert r.status_code == 201
    cid = r.json()["id"]

    r = await client.get(f"/campaigns/{cid}")
    assert r.status_code == 200
    detail = r.json()
    assert detail["name"] == "Launch"
    assert detail["stats"]["queued"] == 0


@pytest.mark.asyncio
async def test_scheduled_campaign_status(client: AsyncClient):
    from datetime import datetime, timedelta, timezone
    future = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    payload = {"name": "Scheduled", "body_text": "Hi", "template_name": None, "scheduled_at": future, "client_id": 1}
    r = await client.post("/campaigns/", json=payload)
    assert r.status_code == 201
    assert r.json()["status"] == "scheduled"


@pytest.mark.asyncio
async def test_csv_import(client: AsyncClient):
    csv_data = b"name,phone,source\nAlice,254700000001,web\nBob,254700000002,web\n"
    r = await client.post("/contacts/import-csv", files={"file": ("leads.csv", csv_data, "text/csv")})
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 2
    assert body["duplicates"] == 0


@pytest.mark.asyncio
async def test_missing_api_key(client: AsyncClient):
    app.dependency_overrides.pop(get_current_client, None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/contacts/")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_invalid_api_key(client: AsyncClient):
    from fastapi import HTTPException
    app.dependency_overrides[get_current_client] = lambda: (_ for _ in ()).throw(HTTPException(status_code=403, detail="bad"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": "bad"}) as ac:
        r = await ac.get("/contacts/")
    assert r.status_code == 403
