import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List
from datetime import date

logger = logging.getLogger(__name__)


class SQLiteClient:
    def __init__(self, data_dir_path: Path | None = None):
        self.data_dir_path = data_dir_path or Path("/data")
        self.database_dir_path = self.data_dir_path / "db"
        self.database_path = self.database_dir_path / "higher-pleasures.db"
        self._ensure_directory()
        self._initialize_database()

    def _ensure_directory(self):
        """Ensure all required directories exist"""
        os.makedirs(self.database_dir_path, exist_ok=True)
        
    @contextmanager
    def _get_connection(self, autocommit=True):
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
                telegram_id TEXT NOT NULL,
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
                date DATE NOT NULL,
                duration_minutes INTEGER NOT NULL,
                raw_input TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (user_activity_id) REFERENCES activities(activity_id)
            );
            """)

    def insert_user(
        self,
        user_id: str,
        first_name: str,
        last_name: str,
        cell: str,
        telegram_id: str,
        email: str | None = None,
    ) -> None:
        with self._get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO users (user_id, first_name, last_name, cell, telegram_id, email) 
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, first_name, last_name, cell, telegram_id, email),
            )
            connection.commit()

    def get_user_activities(self, user_id: str) -> List[str]:
        with self._get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT activity 
                FROM activities 
                WHERE user_id = ?
                """,
                (user_id,),
            )
            return [row[0] for row in cursor.fetchall()]

    def get_user_activity_id_from_activity(self, user_id: str, activity: str) -> int:
        with self._get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT user_activity_id 
                FROM activities 
                WHERE user_id = ? AND activity = ?
                """,
                (user_id, activity),
            )
            result = cursor.fetchall()
            return result[0][0] if result else None

    def insert_activity(self, user_id: str, activity: str) -> None:
        with self._get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO activities (user_id, activity) 
                VALUES (?, ?)
                """,
                (user_id, activity),
            )
            connection.commit()
            activity_id = cursor.lastrowid
            return activity_id

    def insert_entry(
        self,
        db_user_id: int,
        user_activity_id: int,
        date: date,
        duration_minutes: int,
        raw_input: str,
    ) -> None:
        
        with self._get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO entries (user_id, user_activity_id, date, duration_minutes, raw_input) 
                VALUES (?, ?, ?, ?, ?)
                """,
                (db_user_id, user_activity_id, date, duration_minutes, raw_input),
            )
            connection.commit()

    def get_user_id_from_telegram(self, telegram_id: str) -> str:
        with self._get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT user_id 
                FROM users 
                WHERE telegram_id = ?
                """,
                (telegram_id,),
            )
            result = cursor.fetchall()
            return result[0][0] if result else None

    def is_user_allowed(self, telegram_id: str) -> bool:
        return self.get_user_id_from_telegram(telegram_id) is not None
