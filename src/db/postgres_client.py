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
        self.database_url = database_url or os.environ.get("PROD_POSTGRES_URL") or os.environ.get("DEV_POSTGRES_URL")
        if not self.database_url:
            raise ValueError("POSTGRES_URL must be provided or set as an environment variable")
        self._initialize_database()

    @contextmanager
    def _get_connection(self) -> Generator[psycopg2.extensions.connection, None, None]:
        try:
            conn = psycopg2.connect(self.database_url)
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
                    telegram_id BIGINT NOT NULL,
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
        telegram_id: int,
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
            return result[0]

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

    def get_user_id_from_telegram(self, telegram_id: int) -> str:
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
    def is_user_allowed(self, telegram_id: int) -> bool:
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

    ### MIGRATION ZONE ###
    def import_users(self, users: list[dict]) -> None:
        """Import users into PostgreSQL database."""
        with self._get_connection() as connection:
            with connection.cursor() as cursor:
                for user in users:
                    try:
                        cursor.execute(
                            """
                            INSERT INTO users (user_id, first_name, last_name, email, cell, telegram_id, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                user["user_id"],
                                user["first_name"],
                                user["last_name"],
                                user["email"],
                                user["cell"],
                                user["telegram_id"],
                                user["created_at"],
                            ),
                        )
                    except Exception:
                        logger.exception(f"Error importing user {user['user_id']}")
            connection.commit()

    def import_activities(self, activities: list[dict]) -> None:
        """Import activities into PostgreSQL database."""
        with self._get_connection() as connection:
            with connection.cursor() as cursor:
                for activity in activities:
                    try:
                        cursor.execute(
                            """
                            INSERT INTO activities (user_activity_id, user_id, activity, created_at)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (
                                activity["user_activity_id"],
                                activity["user_id"],
                                activity["activity"],
                                activity["created_at"],
                            ),
                        )
                    except Exception:
                        logger.exception(f"Error importing activity {activity['user_activity_id']}")
            connection.commit()

    def import_entries(self, entries: list[dict]) -> None:
        """Import entries into PostgreSQL database."""
        with self._get_connection() as connection:
            with connection.cursor() as cursor:
                for entry in entries:
                    try:
                        cursor.execute(
                            """
                            INSERT INTO
                                entries (entry_id, user_id, user_activity_id, date, duration_minutes, raw_input, created_at)
                            VALUES
                                (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                entry["entry_id"],
                                entry["user_id"],
                                entry["user_activity_id"],
                                entry["date"],
                                entry["duration_minutes"],
                                entry["raw_input"],
                                entry["created_at"],
                            ),
                        )
                    except Exception:
                        logger.exception(f"Error importing entry {entry['entry_id']}")
            connection.commit()

    def disable_autoincrement_constraints(self) -> None:
        """Temporarily disable sequence constraints to allow importing IDs directly."""
        with self._get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("ALTER SEQUENCE activities_user_activity_id_seq RESTART WITH 1000")
                cursor.execute("ALTER SEQUENCE entries_entry_id_seq RESTART WITH 1000")
            connection.commit()

    def reset_sequences(self) -> None:
        """Reset sequences after import to continue from the highest imported ID."""
        with self._get_connection() as connection:
            with connection.cursor() as cursor:
                # Find max IDs
                cursor.execute("SELECT MAX(user_activity_id) FROM activities")
                max_activity_id = cursor.fetchone()[0] or 0

                cursor.execute("SELECT MAX(entry_id) FROM entries")
                max_entry_id = cursor.fetchone()[0] or 0

                # Reset sequences
                cursor.execute(f"ALTER SEQUENCE activities_user_activity_id_seq RESTART WITH {max_activity_id + 1}")
                cursor.execute(f"ALTER SEQUENCE entries_entry_id_seq RESTART WITH {max_entry_id + 1}")
            connection.commit()
