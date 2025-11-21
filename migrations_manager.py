import psycopg2
import os
import logging
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

class MigrationsManager:
    """
    Simple SQL-based migration system that tracks applied migrations
    and automatically runs new ones on startup.
    """
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.migrations_dir = Path(__file__).parent / 'migrations'
        
    def _get_connection(self):
        """Get database connection"""
        return psycopg2.connect(self.database_url)
    
    def _ensure_migrations_table(self, conn):
        """Create schema_migrations table if it doesn't exist"""
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id SERIAL PRIMARY KEY,
                    version VARCHAR(255) UNIQUE NOT NULL,
                    applied_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            conn.commit()
    
    def _get_applied_migrations(self, conn) -> List[str]:
        """Get list of already applied migration versions"""
        with conn.cursor() as cur:
            cur.execute("SELECT version FROM schema_migrations ORDER BY version")
            return [row[0] for row in cur.fetchall()]
    
    def _get_pending_migrations(self, applied: List[str]) -> List[Tuple[str, str]]:
        """
        Get list of pending migrations to apply.
        Returns list of tuples: (version, file_path)
        """
        if not self.migrations_dir.exists():
            logger.warning(f"Migrations directory not found: {self.migrations_dir}")
            return []
        
        pending = []
        for sql_file in sorted(self.migrations_dir.glob('*.sql')):
            version = sql_file.stem  # e.g., "001_fix_schema_order"
            if version not in applied:
                pending.append((version, str(sql_file)))
        
        return pending
    
    def _apply_migration(self, conn, version: str, file_path: str):
        """Apply a single migration file"""
        logger.info(f"Applying migration: {version}")
        
        with open(file_path, 'r') as f:
            sql = f.read()
        
        with conn.cursor() as cur:
            # Execute the migration SQL
            cur.execute(sql)
            
            # Record that this migration was applied
            cur.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (version,)
            )
            
        conn.commit()
        logger.info(f"✅ Migration {version} applied successfully")
    
    def run_migrations(self):
        """
        Main entry point: Run all pending migrations.
        Safe to call multiple times - only applies new migrations.
        """
        if not self.database_url:
            logger.warning("DATABASE_URL not set, skipping migrations")
            return
        
        try:
            conn = self._get_connection()
            
            # Ensure migrations tracking table exists
            self._ensure_migrations_table(conn)
            
            # Get list of applied migrations
            applied = self._get_applied_migrations(conn)
            logger.info(f"Applied migrations: {len(applied)}")
            
            # Get pending migrations
            pending = self._get_pending_migrations(applied)
            
            if not pending:
                logger.info("✅ Database schema is up to date (no pending migrations)")
                conn.close()
                return
            
            logger.info(f"Found {len(pending)} pending migration(s)")
            
            # Apply each pending migration
            for version, file_path in pending:
                try:
                    self._apply_migration(conn, version, file_path)
                except Exception as e:
                    logger.error(f"❌ Failed to apply migration {version}: {e}")
                    conn.rollback()
                    conn.close()
                    raise
            
            logger.info(f"✅ All {len(pending)} migration(s) applied successfully")
            conn.close()
            
        except Exception as e:
            logger.error(f"Migration error: {e}")
            raise
