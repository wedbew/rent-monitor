from fastapi import FastAPI

app = FastAPI(title="RentMonitor API")


@app.get("/api/health", include_in_schema=False)
async def health() -> dict[str, str]:
    """Public liveness for the uptime monitor; touches no database (blueprint §4.7)."""
    return {"status": "ok"}
