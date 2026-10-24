"""Normalize DATABASE_URL for SQLAlchemy asyncpg (Neon, Render, etc.)."""

import ssl
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Query params libpq/psycopg understand but asyncpg.connect() rejects as kwargs.
_STRIP_QUERY_KEYS = frozenset(
    {
        "sslmode",
        "channel_binding",
        "options",
        "connect_timeout",
    }
)


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://") and "+asyncpg" not in url and "+psycopg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def prepare_database_engine_args(url: str) -> tuple[str, dict]:
    """
    Return (clean_url, connect_args) for create_async_engine.
    Neon URLs often include ?sslmode=require which must not reach asyncpg as sslmode=.
    """
    url = normalize_database_url(url)
    if not url.startswith("postgresql+asyncpg"):
        return url, {}

    parsed = urlparse(url)
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    query = dict(query_pairs)
    connect_args: dict = {}

    sslmode = query.get("sslmode")
    if sslmode and sslmode != "disable":
        connect_args["ssl"] = ssl.create_default_context()
    elif sslmode == "disable":
        connect_args["ssl"] = False

    for key in _STRIP_QUERY_KEYS:
        query.pop(key, None)

    clean_query = urlencode(query)
    clean_url = urlunparse(parsed._replace(query=clean_query))
    return clean_url, connect_args
