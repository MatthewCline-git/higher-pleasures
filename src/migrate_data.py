import logging

from src.db.client import SQLiteClient
from src.db.postgres_client import PostgresClient


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("db_migration")


def migrate_sqlite_to_postgres(batch_size: int = 100) -> None:
    """
    Migrate data from SQLite to PostgreSQL.

    Args:
        sqlite_data_path: Path to SQLite database directory
        postgres_url: PostgreSQL connection URL
        batch_size: Number of records to process in each batch
    """
    logger.info("Starting migration from SQLite to PostgreSQL")

    # Initialize clients
    sqlite_client = SQLiteClient()
    postgres_client = PostgresClient()

    try:
        # Prepare PostgreSQL for direct ID imports
        logger.info("Preparing PostgreSQL for migration")
        postgres_client.disable_autoincrement_constraints()

        # Migrate users (typically smaller table, so no batching)
        logger.info("Migrating users")
        users = sqlite_client.export_all_users()
        logger.info(f"Found {len(users)} users to migrate")
        postgres_client.import_users(users)

        # Migrate activities (typically smaller table, so no batching)
        logger.info("Migrating activities")
        activities = sqlite_client.export_all_activities()
        logger.info(f"Found {len(activities)} activities to migrate")
        postgres_client.import_activities(activities)

        # Migrate entries (potentially larger, so use batching)
        logger.info("Migrating entries")
        entries = sqlite_client.export_all_entries()
        logger.info(f"Found {len(entries)} entries to migrate")

        # Process entries in batches
        for i in range(0, len(entries), batch_size):
            batch = entries[i : i + batch_size]
            logger.info(
                f"Migrating entries batch {i // batch_size + 1}/{(len(entries) + batch_size - 1) // batch_size}"
            )
            postgres_client.import_entries(batch)

        # Reset sequences to continue from highest imported IDs
        logger.info("Resetting PostgreSQL sequences")
        postgres_client.reset_sequences()

        logger.info("Migration completed successfully")

    except Exception:
        logger.exception("Migration failed")
        raise


if __name__ == "__main__":
    migrate_sqlite_to_postgres()
