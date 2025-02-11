"""Higher Pleasures - A natural language activity tracker.

This package provides functionality for tracking activities using natural language
processing and storing the data in Google Sheets.
"""

__version__ = "0.1.0"

from .activities.parser import OpenAIActivityParser
from .activities.tracker import ActivityTracker
from .sheets.client import GoogleSheetsClient


__all__ = [
    "ActivityTracker",
    "GoogleSheetsClient",
    "OpenAIActivityParser",
]
