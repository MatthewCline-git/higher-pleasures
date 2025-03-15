import logging
import os
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date
from typing import Any, TypedDict

import psycopg2
from psycopg2.extras import RealDictCursor


logger = logging.getLogger(__name__)


class Entry(TypedDict):
    user_id: str
    user_activity_id: int
    date: date
    duration_minutes: Any
    raw_input: str


class PostgresClient:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("POSTGRES_URL")
        if not self.database_url:
            raise ValueError("POSTGRES_URL must be provided or set as an environment variable")
        self._initialize_database()

    @contextmanager
    def _get_connection(self) -> Generator[psycopg2.extensions.connection, None, None]:
        conn = psycopg2.connect(self.database_url)
        try:
            yield conn
        finally:
            conn.close()

    def _initialize_database(self) -> None:
        with self._get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    email TEXT,
                    cell TEXT NOT NULL,
                    telegram_id TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS activities (
                    user_activity_id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    activity TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                );
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS entries (
                    entry_id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    user_activity_id INTEGER NOT NULL,
                    date DATE NOT NULL,
                    duration_minutes INTEGER NOT NULL,
                    raw_input TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (user_activity_id) REFERENCES activities(user_activity_id)
                );
                """)

            connection.commit()

    # ruff: noqa: PLR0913
    def insert_user(
        self,
        user_id: str,
        first_name: str,
        last_name: str,
        cell: str,
        telegram_id: str,
        email: str | None = None,
    ) -> None:
        with self._get_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (user_id, first_name, last_name, cell, telegram_id, email)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (user_id, first_name, last_name, cell, telegram_id, email),
            )
        connection.commit()

    def get_user_activities(self, user_id: str) -> list[str]:
        with self._get_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT activity
                FROM activities
                WHERE user_id = %s
                """,
                (user_id,),
            )
            return [row[0] for row in cursor.fetchall()]

    def get_user_activity_id_from_activity(self, user_id: str, activity: str) -> int:
        with self._get_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_activity_id
                FROM activities
                WHERE user_id = %s AND activity = %s
                """,
                (user_id, activity),
            )
            result = cursor.fetchone()
            return result[0] if result else None

    def insert_activity(self, user_id: str, activity: str) -> int:
        with self._get_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO activities (user_id, activity)
                VALUES (%s, %s)
                RETURNING user_activity_id
                """,
                (user_id, activity),
            )
            activity_id = cursor.fetchone()[0]
            connection.commit()
            return activity_id

    def insert_entry(
        self,
        db_user_id: str,
        user_activity_id: int,
        date: date,
        duration_minutes: int,
        raw_input: str,
    ) -> None:
        with self._get_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO entries (user_id, user_activity_id, date, duration_minutes, raw_input)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (db_user_id, user_activity_id, date, duration_minutes, raw_input),
            )
        connection.commit()

    def get_user_id_from_telegram(self, telegram_id: str) -> str:
        with self._get_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id
                FROM users
                WHERE telegram_id = %s
                """,
                (telegram_id,),
            )
            result = cursor.fetchone()
            return result[0] if result else None

    # ruff: noqa: D102
    def is_user_allowed(self, telegram_id: str) -> bool:
        return self.get_user_id_from_telegram(telegram_id) is not None

    def get_entries(self) -> list[Entry]:
        with self._get_connection() as connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM entries
                """
            )
            entries = cursor.fetchall()
            return [dict(entry) for entry in entries]

    def get_user_entries(self, user_id: str) -> list[Entry]:
        with self._get_connection() as connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM entries
                WHERE user_id = %s
                """,
                (user_id,),
            )
            entries = cursor.fetchall()
            return [dict(entry) for entry in entries]
