from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.api.routers import db


class HealthStatus(BaseModel):
    status: str
    version: str


app = FastAPI(title="Higher Pleasures API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create shared API v1 router
api_v1 = APIRouter(prefix="/api/v1")

@api_v1.get("/health")
async def heath_check() -> HealthStatus:
    """Return health status of the API."""
    return {"status": "healthy", "version": "0.1.0"}

# api_v1.include_router(auth.router)
api_v1.include_router(db.router)

app.include_router(api_v1)

