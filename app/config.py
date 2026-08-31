import os
from pathlib import Path

# Resolve base directories
BASE_DIR = Path(__file__).resolve().parent.parent

# Check if /config exists (standard in Unraid / Docker container)
# Otherwise fall back to a local data directory for development
CONTAINER_CONFIG_DIR = Path("/config")
if CONTAINER_CONFIG_DIR.exists():
    CONFIG_DIR = CONTAINER_CONFIG_DIR
else:
    CONFIG_DIR = BASE_DIR / "data"
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = CONFIG_DIR / "dealmonitor.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH.as_posix()}")

PORT = int(os.getenv("PORT", "8080"))
HOST = os.getenv("HOST", "0.0.0.0")
DEFAULT_POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "120"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
