import psycopg2
from psycopg2 import pool, extras
from contextlib import contextmanager
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import POSTGRESQL_CONFIG
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global connection pool
_connection_pool = None


def initialize_connection_pool():
    """
    Initialize the PostgreSQL connection pool.
    Should be called once at application startup.
    """
    global _connection_pool
    
    if _connection_pool is not None:
        logger.info("Connection pool already initialized")
        return
    
    try:
        _connection_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=POSTGRESQL_CONFIG['minconn'],
            maxconn=POSTGRESQL_CONFIG['maxconn'],
            host=POSTGRESQL_CONFIG['host'],
            port=POSTGRESQL_CONFIG['port'],
            dbname=POSTGRESQL_CONFIG['database'],
            user=POSTGRESQL_CONFIG['user'],
            password=POSTGRESQL_CONFIG['password'],
            connect_timeout=POSTGRESQL_CONFIG['connect_timeout'],
            application_name=POSTGRESQL_CONFIG['application_name']
        )
        logger.info(f"Connection pool initialized successfully for database: {POSTGRESQL_CONFIG['database']}")
    except psycopg2.Error as e:
        logger.error(f"Failed to initialize connection pool: {e}")
        raise


def close_connection_pool():
    """
    Close all connections in the pool.
    Should be called at application shutdown.
    """
    global _connection_pool
    
    if _connection_pool:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("Connection pool closed")


def get_postgres_connection():
    """
    Get a connection from the pool.
    Returns:
        conn: psycopg2 connection object from the pool
    Raises:
        psycopg2.DatabaseError: If connection fails
    """
    global _connection_pool
    
    # Initialize pool if not already done
    if _connection_pool is None:
        initialize_connection_pool()
    
    try:
        conn = _connection_pool.getconn()
        return conn
    except psycopg2.Error as e:
        logger.error(f"Failed to get connection from pool: {e}")
        raise


def return_connection(conn):
    """
    Return a connection back to the pool.
    Args:
        conn: psycopg2 connection object to return
    """
    global _connection_pool
    
    if _connection_pool and conn:
        _connection_pool.putconn(conn)


@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    Automatically handles connection pooling and cleanup.
    
    Usage:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM table")
                results = cur.fetchall()
    """
    conn = None
    try:
        conn = get_postgres_connection()
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            return_connection(conn)


@contextmanager
def get_db_cursor(cursor_factory=None):
    """
    Context manager for database cursor.
    Automatically handles connection and cursor lifecycle.
    
    Args:
        cursor_factory: Optional cursor factory (e.g., RealDictCursor for dict results)
    
    Usage:
        with get_db_cursor() as cur:
            cur.execute("SELECT * FROM table")
            results = cur.fetchall()
    """
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cursor
        finally:
            cursor.close()


def execute_query(query, params=None, fetch=True, cursor_factory=None):
    """
    Execute a SQL query with automatic connection management.
    
    Args:
        query (str): SQL query to execute
        params (tuple/dict): Query parameters for safe parameterized queries
        fetch (bool): Whether to fetch and return results
        cursor_factory: Optional cursor factory (e.g., RealDictCursor)
    
    Returns:
        list: Query results if fetch=True, None otherwise
    """
    try:
        with get_db_cursor(cursor_factory=cursor_factory) as cur:
            cur.execute(query, params)
            if fetch:
                return cur.fetchall()
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        logger.error(f"Query: {query}")
        raise


def test_connection():
    """
    Test the database connection.
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        with get_db_cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()
            logger.info(f"Database connection successful. PostgreSQL version: {version[0]}")
            return True, f"Connected successfully: {version[0]}"
    except Exception as e:
        error_msg = f"Database connection failed: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
