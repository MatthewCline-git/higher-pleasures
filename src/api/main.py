from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from db_client.db_client import SQLiteClient    
from typing import List, Optional

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
    email: Optional[str] = None
    cell: str
    telegram_id: str

class User(UserBase):
    user_id: str
    created_at: datetime

