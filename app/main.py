import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import CONFIG_DIR, DATABASE_PATH, PORT
from app.database import init_db
from app.routers import dashboard, rules, settings, api
from app.services.poller import poller

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure directory and initialize DB
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Initializing SQLite database at: {DATABASE_PATH}")
    init_db()

    # Start background poller
    logger.info("Starting background deal poller...")
    poller.start()

    yield

    # Shutdown
    logger.info("Shutting down background deal poller...")
    poller.stop()


app = FastAPI(
    title="eBay Deal Monitor",
    description="Lightweight containerized eBay Deal Monitor optimized for Unraid.",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static directory
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Include Routers
app.include_router(dashboard.router)
app.include_router(rules.router)
app.include_router(settings.router)
app.include_router(api.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, reload=False)
