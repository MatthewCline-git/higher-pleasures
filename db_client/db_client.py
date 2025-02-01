from contextlib import contextmanager
import os
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class SQLiteClient:
    def __init__(self, database_dir_path: Path | None = None):
        self.database_dir_path = database_dir_path or Path("../../database/")
        self.database_path = self.database_dir_path / Path("higher-pleasures.db")
        self._ensure_directory(self)

    def _ensure_directory(self):
        os.makedirs(self.database_dir_path, exist_ok=True)
    
    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        try: 
            yield conn
        finally:
            conn.close()

    def _initialize_database(self):
        with self._get_connection() as connection:
            cursor = connection.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT,
                cell TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS activities (
                user_activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                activity TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entries (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                user_activity_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                raw_input TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (user_activity_id) REFERENCES activities(activity_id)
            );
            """)

