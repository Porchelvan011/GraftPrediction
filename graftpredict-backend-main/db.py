import contextlib
import mysql.connector
_orig_connect = mysql.connector.connect
from mysql.connector import pooling
from contextlib import contextmanager
import threading
import config

_pool = None
_pool_lock = threading.Lock()


def init_db_pool():
    global _pool
    with _pool_lock:
        if _pool is None:
            try:
                _pool = pooling.MySQLConnectionPool(
                    pool_name=config.DB_POOL_NAME,
                    pool_size=config.DB_POOL_SIZE,
                    host=config.DB_HOST,
                    user=config.DB_USER,
                    password=config.DB_PASSWORD,
                    database=config.DB_NAME,
                    autocommit=False,
                )
            except Exception as e:
                _pool = None


@contextmanager
def get_conn():
    """Context manager that yields a pooled connection (or direct fallback) and ensures close/rollback on error."""
    global _pool
    conn = None
    try:
        if _pool is None:
            init_db_pool()
        if _pool is not None:
            try:
                conn = _pool.get_connection()
                if not conn.is_connected():
                    conn.reconnect(attempts=2, delay=1)
            except Exception:
                conn = None
        if conn is None:
            conn = _orig_connect(
                host=config.DB_HOST,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                database=config.DB_NAME,
                autocommit=False,
            )
        yield conn
    except Exception:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# Compatibility helper: mimic mysql.connector.connect(...) used across the codebase
def compat_connect(*args, **kwargs):
    global _pool
    if _pool is None:
        init_db_pool()
    if _pool is not None:
        try:
            conn = _pool.get_connection()
            if not conn.is_connected():
                conn.reconnect(attempts=2, delay=1)
            return conn
        except Exception:
            pass
    # If caller provided args/kwargs, pass them directly to original unpatched connect
    if args or kwargs:
        return _orig_connect(*args, **kwargs)
    return _orig_connect(
        host=config.DB_HOST,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        autocommit=False,
    )
