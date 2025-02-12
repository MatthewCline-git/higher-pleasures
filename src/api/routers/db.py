from datetime import date, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from src.db.client import SQLiteClient


router = APIRouter(prefix="/db", tags=["database"])

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


@router.get("/health")
async def heath_check() -> dict[str, str]:
    """Return health status of the API."""
    return {"status": "healthy", "version": "0.1.0"}


@router.get("/entries")
async def get_entries() -> list[Entry]:
    """Return all entries in entries table."""
    return db_client.get_entries()
