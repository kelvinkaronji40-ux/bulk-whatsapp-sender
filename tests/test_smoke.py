import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.main import app
from app.database import get_session
from app.models import Base


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
    async def _override():
        yield db_session
    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
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
    payload = {"name": "Launch", "body_text": "Hello {{name}}", "template_name": None}
    r = await client.post("/campaigns/", json=payload)
    assert r.status_code == 201
    cid = r.json()["id"]

    r = await client.get(f"/campaigns/{cid}")
    assert r.status_code == 200
    detail = r.json()
    assert detail["name"] == "Launch"
    assert detail["stats"]["queued"] == 0


@pytest.mark.asyncio
async def test_csv_import(client: AsyncClient):
    csv_data = b"name,phone,source\nAlice,254700000001,web\nBob,254700000002,web\n"
    r = await client.post("/contacts/import-csv", files={"file": ("leads.csv", csv_data, "text/csv")})
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 2
    assert body["duplicates"] == 0
