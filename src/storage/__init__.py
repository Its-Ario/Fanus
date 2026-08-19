from src.storage.db import (
    DatabaseCredentials,
    DatabaseManager,
    configure_database_manager,
    get_database_manager,
)


def init_database(credentials: DatabaseCredentials) -> DatabaseManager:
    manager = configure_database_manager(credentials)
    manager.initialize()
    return manager


__all__ = [
    "DatabaseCredentials",
    "DatabaseManager",
    "configure_database_manager",
    "get_database_manager",
    "init_database",
]
