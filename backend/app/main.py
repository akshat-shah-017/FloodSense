import logging
import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

sys.path.insert(0, "/app")

from app.routers.alerts import router as alerts_router
from app.routers.health import router as health_router
from app.routers.internal import router as internal_router
from app.routers.predictions import router as predictions_router
from app.routers.weather import router as weather_router

app = FastAPI(title="FloodSense API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.include_router(health_router)
app.include_router(predictions_router)
app.include_router(alerts_router)
app.include_router(internal_router)
app.include_router(weather_router)

logger = logging.getLogger("uvicorn.error")


@app.on_event("startup")
async def on_startup() -> None:
    ml_path = os.getenv("ML_PATH", "/app")
    if ml_path not in sys.path:
        sys.path.insert(0, ml_path)
    logger.info("FloodSense API started. ML path: /app")
