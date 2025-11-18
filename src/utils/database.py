"""Database connection utilities."""
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from src.config import settings

@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = psycopg2.connect(settings.database_url)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

@contextmanager
def get_db_cursor(dict_cursor=False):
    """Context manager for database cursors."""
    with get_db_connection() as conn:
        cursor_factory = RealDictCursor if dict_cursor else None
        cur = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cur
        finally:
            cur.close()
