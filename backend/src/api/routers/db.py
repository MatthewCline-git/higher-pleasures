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
    user_id: str
    user_activity_id: int
    date: date
    duration_minutes: int
    raw_input: str


@router.get("/entries")
async def get_entries() -> list[Entry]:
    """Return all entries in entries table."""
    return db_client.get_entries()


@router.get("/{user_id}/entries")
async def get_user_entries(user_id: str) -> list[Entry]:
    """Return all entries for a specific user."""
    return db_client.get_user_entries(user_id)
