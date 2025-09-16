import os
from decimal import Decimal
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row
from psycopg.pool import ConnectionPool
import atexit
from contextlib import contextmanager
import threading

# Load environment variables
load_dotenv()

# Database configuration
DB_NAME = os.getenv("POSTGRES_DATABASE")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")
DB_HOST = os.getenv("POSTGRES_HOST")
DB_PORT = os.getenv("POSTGRES_PORT", 5432)

# Connection pool configuration
MIN_CONNECTIONS = int(os.getenv("DB_MIN_CONNECTIONS", "2"))
MAX_CONNECTIONS = int(os.getenv("DB_MAX_CONNECTIONS", "20"))

# Global connection pool
_connection_pool = None
_pool_lock = threading.Lock()

def _create_connection_pool():
    """
    Create and configure the connection pool
    
    Returns:
        ConnectionPool: Configured connection pool
    """
    conninfo = (
        f"dbname={DB_NAME} "
        f"user={DB_USER} "
        f"password={DB_PASSWORD} "
        f"host={DB_HOST} "
        f"port={DB_PORT}"
    )
    
    return ConnectionPool(
        conninfo=conninfo,
        min_size=MIN_CONNECTIONS,
        max_size=MAX_CONNECTIONS,
        kwargs={"row_factory": dict_row},
        open=True
    )

def get_connection_pool():
    """
    Get the global connection pool instance (singleton pattern)
    
    Returns:
        ConnectionPool: The connection pool instance
    """
    global _connection_pool
    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:
                try:
                    _connection_pool = _create_connection_pool()
                    # Register cleanup function
                    atexit.register(close_connection_pool)
                except psycopg.Error as e:
                    print(f"Error creating connection pool: {e}")
                    raise
    return _connection_pool

def close_connection_pool():
    """
    Close the connection pool and cleanup resources
    """
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.close()
        _connection_pool = None

@contextmanager
def get_db_connection():
    """
    Get a database connection from the pool
    
    Yields:
        Connection: Database connection object
    """
    pool = get_connection_pool()
    try:
        with pool.connection() as conn:
            yield conn
    except psycopg.Error as e:
        print(f"Error getting database connection: {e}")
        raise

# Legacy function for backward compatibility
def get_db_connection_legacy():
    """
    Create a direct connection to the PostgreSQL database (legacy)
    This function is kept for backward compatibility but should be avoided.
    Use get_db_connection() context manager instead.
    
    Returns:
        Connection: Database connection object
    """
    try:
        return psycopg.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            row_factory=dict_row
        )
    except psycopg.Error as e:
        print(f"Error connecting to database: {e}")
        raise


