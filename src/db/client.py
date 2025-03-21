import logging
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import TypedDict


logger = logging.getLogger(__name__)


class Entry(TypedDict):
    user_id: str
    user_activity_id: int
    date: date
    duration_minutes: int
    raw_input: str


class SQLiteClient:
    def __init__(self, data_dir_path: Path | None = None) -> None:
        self.data_dir_path = data_dir_path or Path("/data")
        self.database_dir_path = self.data_dir_path / "db"
        self.database_path = self.database_dir_path / "higher-pleasures.db"
        self._ensure_directory()
        self._initialize_database()

    def _ensure_directory(self) -> None:
        """Ensure all required directories exist"""
        Path.mkdir(self.database_dir_path, exist_ok=True, parents=True)

    @contextmanager
    def _get_connection(self, *, _autocommit: bool = True) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _initialize_database(self) -> None:
        with self._get_connection() as connection:
            cursor = connection.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT,
                cell TEXT NOT NULL,
                telegram_id INTEGER NOT NULL,
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

    # ruff: noqa: PLR0913
    def insert_user(
        self,
        user_id: str,
        first_name: str,
        last_name: str,
        cell: str,
        telegram_id: int,
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

    def get_user_activities(self, user_id: str) -> list[str]:
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
            result: list[tuple[int]] = cursor.fetchall()
            return result[0][0]

    def insert_activity(self, user_id: str, activity: str) -> int:
        with self._get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO activities (user_id, activity)
                VALUES (?, ?)
                """,
                (user_id, activity),
            )
            row_id = cursor.lastrowid
            cursor.execute(
                """
                SELECT user_activity_id
                FROM activities
                WHERE rowid = ?
                """,
                (row_id,),
            )
            result = cursor.fetchone()
            connection.commit()
            return result[0]

    def insert_entry(
        self,
        db_user_id: str,
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

    def get_user_id_from_telegram(self, telegram_id: int) -> str | None:
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

    # ruff: noqa: D102
    def is_user_allowed(self, telegram_id: int) -> bool:
        return self.get_user_id_from_telegram(telegram_id) is not None

    def get_entries(self) -> list[Entry]:
        with self._get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT *
                FROM entries
                """
            )
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            entries = []
            for row in rows:
                entry = dict(zip(columns, row, strict=False))
                entries.append(entry)
            return entries

    def get_user_entries(self, user_id: str) -> list[Entry]:
        with self._get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT *
                FROM entries
                WHERE user_id = ?
                """,
                (user_id,),
            )
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            entries = []
            for row in rows:
                entry = dict(zip(columns, row, strict=False))
                entries.append(entry)
            return entries

    ### MIGRATION ZONE ###
    def export_all_users(self) -> list[dict]:
        """Export all users from SQLite database."""
        with self._get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT user_id, first_name, last_name, email, cell, telegram_id, created_at FROM users")
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row, strict=False)) for row in rows]

    def export_all_activities(self) -> list[dict]:
        """Export all activities from SQLite database."""
        with self._get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT user_activity_id, user_id, activity, created_at FROM activities")
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row, strict=False)) for row in rows]

    def export_all_entries(self) -> list[dict]:
        """Export all entries from SQLite database."""
        with self._get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT entry_id, user_id, user_activity_id, date, duration_minutes, raw_input, created_at
                FROM entries
            """)
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row, strict=False)) for row in rows]
