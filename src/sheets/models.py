# src/sheets/models.py
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List


@dataclass
class SheetEntry:
    """Represents a single row entry in the activity sheet"""

    date: datetime
    values: List[float]


class EntryType(Enum):
    """Types of entries that can appear in the date column"""

    WEEK_HEADER = "WEEK"
    DATE = "DATE"
