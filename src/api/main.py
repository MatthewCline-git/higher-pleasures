from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import db


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

# api_v1.include_router(auth.router)
api_v1.include_router(db.router)

app.include_router(api_v1)
