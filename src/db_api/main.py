from datetime import date, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.db.client import SQLiteClient


app = FastAPI(title="Higher Pleasures Database API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_client = SQLiteClient()


class UserBase(BaseModel):
    first_name: str
    last_name: str
    email: str | None = None
    cell: str
    telegram_id: str


class User(UserBase):
    user_id: str
    created_at: datetime


class Entry(BaseModel):
    user_id: int
    user_activity_id: int
    date: date
    duration_minutes: int
    raw_input: str


@app.get("/db_api/v1/health")
async def heath_check() -> dict[str, str]:
    """Return health status of the API."""
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/db_api/v1/entries")
async def get_entries() -> list[Entry]:
    """Return all entries in entries table."""
    return db_client.get_entries()
