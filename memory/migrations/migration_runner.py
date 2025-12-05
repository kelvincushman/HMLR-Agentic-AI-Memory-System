"""
Database migration runner for CognitiveLattice memory system.

Applies SQL migrations in order and tracks completion in metadata table.
"""
import os
import sqlite3
from pathlib import Path
from typing import List
import logging

logger = logging.getLogger(__name__)


class MigrationRunner:
    """Applies database migrations to the memory store."""
    
    def __init__(self, db_path: str):
        """
        Initialize migration runner.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.migration_dir = Path(__file__).parent
    
    def run_migrations(self, migration_files: List[str] = None) -> None:
        """
        Run all pending migrations.
        
        Args:
            migration_files: Optional list of specific migrations to run.
                           If None, runs all migrations in order.
        """
        if migration_files is None:
            # Get all .sql files in migrations directory
            migration_files = sorted([
                f.name for f in self.migration_dir.glob('*.sql')
            ])
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
        
        try:
            for migration_file in migration_files:
                if self._is_applied(conn, migration_file):
                    logger.info(f"Migration {migration_file} already applied, skipping")
                    continue
                
                logger.info(f"Applying migration: {migration_file}")
                self._apply_migration(conn, migration_file)
                self._mark_applied(conn, migration_file)
                logger.info(f"Migration {migration_file} completed successfully")
            
            conn.commit()
            logger.info("All migrations completed successfully")
        
        except Exception as e:
            conn.rollback()
            logger.error(f"Migration failed: {e}")
            raise
        
        finally:
            conn.close()
    
    def _is_applied(self, conn: sqlite3.Connection, migration_file: str) -> bool:
        """Check if migration has already been applied."""
        cursor = conn.cursor()
        
        # Check if metadata table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='metadata'
        """)
        if not cursor.fetchone():
            return False
        
        # Check if this specific migration is recorded
        cursor.execute("""
            SELECT value FROM metadata 
            WHERE key = ? AND value = 'complete'
        """, (f"migration_{migration_file.replace('.sql', '')}",))
        
        return cursor.fetchone() is not None
    
    def _apply_migration(self, conn: sqlite3.Connection, migration_file: str) -> None:
        """Apply a single migration file."""
        migration_path = self.migration_dir / migration_file
        
        with open(migration_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # Execute the migration (split on semicolons for multiple statements)
        conn.executescript(sql_script)
    
    def _mark_applied(self, conn: sqlite3.Connection, migration_file: str) -> None:
        """Mark migration as applied in metadata table."""
        migration_name = migration_file.replace('.sql', '')
        
        conn.execute("""
            INSERT OR REPLACE INTO metadata (key, value, updated_at)
            VALUES (?, 'complete', datetime('now'))
        """, (f"migration_{migration_name}",))


def run_pending_migrations(db_path: str) -> None:
    """
    Convenience function to run all pending migrations.
    
    Args:
        db_path: Path to SQLite database
    """
    runner = MigrationRunner(db_path)
    runner.run_migrations()


if __name__ == "__main__":
    # For testing: run migrations on default database
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/memory.db"
    
    logging.basicConfig(level=logging.INFO)
    run_pending_migrations(db_path)
