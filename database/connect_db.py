"""
Production-ready async database connection pool using asyncpg.

Features:
- Async connection pooling with configurable min/max connections
- Automatic reconnection and health checks
- Graceful shutdown and cleanup
- Transaction management with automatic rollback
- Comprehensive error handling and logging
- Connection timeout and retry logic
"""

import os
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, Any
from dotenv import load_dotenv
import asyncpg
from asyncpg.pool import Pool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Database configuration
DB_NAME = os.getenv("POSTGRES_DATABASE")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")
DB_HOST = os.getenv("POSTGRES_HOST")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))

# Connection pool configuration
MIN_CONNECTIONS = int(os.getenv("DB_MIN_CONNECTIONS", "5"))
MAX_CONNECTIONS = int(os.getenv("DB_MAX_CONNECTIONS", "20"))
CONNECTION_TIMEOUT = int(os.getenv("DB_CONNECTION_TIMEOUT", "30"))
COMMAND_TIMEOUT = int(os.getenv("DB_COMMAND_TIMEOUT", "60"))
MAX_QUERIES = int(os.getenv("DB_MAX_QUERIES", "50000"))
MAX_INACTIVE_CONNECTION_LIFETIME = int(os.getenv("DB_MAX_INACTIVE_LIFETIME", "300"))

# Global connection pool
_connection_pool: Optional[Pool] = None
_pool_lock = asyncio.Lock()


class DatabaseError(Exception):
    """Base exception for database errors"""
    pass


class ConnectionPoolError(DatabaseError):
    """Exception for connection pool errors"""
    pass


async def _init_connection(conn: asyncpg.Connection) -> None:
    """
    Initialize a new connection with custom settings.
    
    Args:
        conn: The asyncpg connection to initialize
    """
    # Set statement timeout to prevent long-running queries
    await conn.execute(f"SET statement_timeout = {COMMAND_TIMEOUT * 1000}")
    # Set timezone
    await conn.execute("SET timezone = 'UTC'")
    logger.debug("Connection initialized with custom settings")


async def _create_connection_pool() -> Pool:
    """
    Create and configure the async connection pool with best practices.
    
    Returns:
        Pool: Configured asyncpg connection pool
        
    Raises:
        ConnectionPoolError: If pool creation fails
    """
    try:
        pool = await asyncpg.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            min_size=MIN_CONNECTIONS,
            max_size=MAX_CONNECTIONS,
            max_queries=MAX_QUERIES,
            max_inactive_connection_lifetime=MAX_INACTIVE_CONNECTION_LIFETIME,
            timeout=CONNECTION_TIMEOUT,
            command_timeout=COMMAND_TIMEOUT,
            init=_init_connection,
            # Connection pool will automatically reconnect on connection loss
            server_settings={
                'application_name': 'vertexai_mcp',
                'tcp_keepalives_idle': '30',
                'tcp_keepalives_interval': '10',
                'tcp_keepalives_count': '5',
            }
        )
        
        # Test the connection
        async with pool.acquire() as conn:
            await conn.fetchval('SELECT 1')
            
        logger.info(
            f"Connection pool created successfully: "
            f"min={MIN_CONNECTIONS}, max={MAX_CONNECTIONS}"
        )
        return pool
        
    except Exception as e:
        logger.error(f"Failed to create connection pool: {e}", exc_info=True)
        raise ConnectionPoolError(f"Failed to create connection pool: {e}") from e


async def get_connection_pool() -> Pool:
    """
    Get the global connection pool instance (singleton pattern).
    Thread-safe and creates pool only once.
    
    Returns:
        Pool: The asyncpg connection pool instance
        
    Raises:
        ConnectionPoolError: If pool cannot be created
    """
    global _connection_pool
    
    if _connection_pool is None:
        async with _pool_lock:
            # Double-check locking pattern
            if _connection_pool is None:
                _connection_pool = await _create_connection_pool()
                
    return _connection_pool


async def close_connection_pool() -> None:
    """
    Gracefully close the connection pool and cleanup resources.
    Should be called on application shutdown.
    """
    global _connection_pool
    
    if _connection_pool is not None:
        try:
            await _connection_pool.close()
            logger.info("Connection pool closed successfully")
        except Exception as e:
            logger.error(f"Error closing connection pool: {e}", exc_info=True)
        finally:
            _connection_pool = None


@asynccontextmanager
async def get_db_connection():
    """
    Async context manager for acquiring a database connection from the pool.
    Automatically handles connection release and cleanup.
    
    Usage:
        async with get_db_connection() as conn:
            result = await conn.fetch('SELECT * FROM table')
            
    Yields:
        asyncpg.Connection: Database connection from the pool
        
    Raises:
        ConnectionPoolError: If connection cannot be acquired
    """
    pool = await get_connection_pool()
    conn = None
    
    try:
        conn = await pool.acquire()
        yield conn
    except asyncpg.PostgresError as e:
        logger.error(f"Database error: {e}", exc_info=True)
        raise DatabaseError(f"Database operation failed: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise
    finally:
        if conn is not None:
            try:
                await pool.release(conn)
            except Exception as e:
                logger.error(f"Error releasing connection: {e}", exc_info=True)


@asynccontextmanager
async def get_db_transaction():
    """
    Async context manager for database transactions with automatic commit/rollback.
    
    Usage:
        async with get_db_transaction() as conn:
            await conn.execute('INSERT INTO table VALUES ($1)', value)
            # Automatically commits on success, rolls back on error
            
    Yields:
        asyncpg.Connection: Database connection with active transaction
        
    Raises:
        DatabaseError: If transaction fails
    """
    pool = await get_connection_pool()
    conn = None
    
    try:
        conn = await pool.acquire()
        async with conn.transaction():
            yield conn
    except asyncpg.PostgresError as e:
        logger.error(f"Transaction failed: {e}", exc_info=True)
        raise DatabaseError(f"Transaction failed: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error in transaction: {e}", exc_info=True)
        raise
    finally:
        if conn is not None:
            try:
                await pool.release(conn)
            except Exception as e:
                logger.error(f"Error releasing connection: {e}", exc_info=True)


async def health_check() -> bool:
    """
    Perform a health check on the database connection pool.
    
    Returns:
        bool: True if healthy, False otherwise
    """
    try:
        async with get_db_connection() as conn:
            result = await conn.fetchval('SELECT 1')
            return result == 1
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return False


async def execute_with_retry(
    query: str,
    *args: Any,
    max_retries: int = 3,
    retry_delay: float = 1.0
) -> Any:
    """
    Execute a query with automatic retry logic for transient failures.
    
    Args:
        query: SQL query to execute
        *args: Query parameters
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        
    Returns:
        Query result
        
    Raises:
        DatabaseError: If all retry attempts fail
    """
    last_error = None
    
    for attempt in range(max_retries):
        try:
            async with get_db_connection() as conn:
                return await conn.fetch(query, *args)
        except (asyncpg.PostgresConnectionError, asyncpg.InterfaceError) as e:
            last_error = e
            logger.warning(
                f"Query failed (attempt {attempt + 1}/{max_retries}): {e}"
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))
        except Exception as e:
            logger.error(f"Non-retryable error: {e}", exc_info=True)
            raise DatabaseError(f"Query execution failed: {e}") from e
    
    raise DatabaseError(
        f"Query failed after {max_retries} attempts: {last_error}"
    ) from last_error


