from httpx import ASGITransport, AsyncClient
from rm_api.main import app


async def test_health_is_public_and_dbless() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
