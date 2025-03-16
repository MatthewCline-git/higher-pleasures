from datetime import date, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from src.db.postgres_client import PostgresClient


router = APIRouter(prefix="/db", tags=["database"])

db_client = PostgresClient()


class UserBase(BaseModel):
    first_name: str
    last_name: str
    email: str | None = None
    cell: str
    telegram_id: int


class User(UserBase):
    user_id: str
    created_at: datetime


# this corresponds to the actual DB data model
class Entry(BaseModel):
    user_id: str
    user_activity_id: int
    date: date
    duration_minutes: int
    raw_input: str


class ActivitySummary(BaseModel):
    full_name: str
    activities: list[str]
    dates: list[str]
    date_entries: list[dict[str, str | int]]


@router.get("/entries")
async def get_entries() -> list[Entry]:
    """Return all entries in entries table."""
    return db_client.get_entries()


@router.get("/{user_id}/entries")
async def get_user_entries(user_id: str) -> list[Entry]:
    """Return all entries for a specific user."""
    return db_client.get_user_entries(user_id)


@router.get("/{user_id}/entries/activity-summary")
async def get_user_activity_summary(user_id: str) -> ActivitySummary:
    """Return summary of user's activity."""
    return db_client.get_user_activity_summary(user_id)
