from fastapi import APIRouter
from datetime import datetime, timezone
from packages.imh_core.config import IMHConfig

router = APIRouter()
config = IMHConfig.load()

@router.get("/health")
async def health_check():
    """
    Server Liveness Probe.
    Returns status, version, and current timestamp.
    """
    return {
        "status": "ok",
        "version": config.VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
