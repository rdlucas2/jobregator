import json
import os

import psycopg2
import pytest

from src.db import ensure_schema, insert_listing, listing_exists


@pytest.fixture(scope="module")
def db_conn():
    """Connect to a test Postgres instance.

    Requires POSTGRES_DSN env var, or defaults to the Docker Compose service.
    """
    dsn = os.environ.get(
        "POSTGRES_DSN",
        "postgresql://jobregator:jobregator@localhost:5432/jobregator",
    )
    conn = psycopg2.connect(dsn)
    ensure_schema(conn)
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def clean_table(db_conn):
    """Truncate job_listings between tests."""
    with db_conn.cursor() as cur:
        cur.execute("TRUNCATE job_listings RESTART IDENTITY")
    db_conn.commit()


def _make_listing(external_id="123", source="adzuna"):
    return {
        "source": source,
        "external_id": external_id,
        "title": "DevOps Engineer",
        "company": "Acme Corp",
        "location": "Remote",
        "description": "A great job...",
        "url": "https://example.com/jobs/123",
        "salary": "$150000-$200000",
        "posted_at": "2026-03-28T10:00:00Z",
        "raw_json": json.dumps({"original": "data"}),
    }


def test_insert_listing_returns_true_on_new(db_conn):
    listing = _make_listing()
    assert insert_listing(db_conn, listing) is True


def test_insert_duplicate_returns_false(db_conn):
    listing = _make_listing()
    insert_listing(db_conn, listing)
    assert insert_listing(db_conn, listing) is False


def test_listing_exists_returns_true_after_insert(db_conn):
    listing = _make_listing()
    insert_listing(db_conn, listing)
    assert listing_exists(db_conn, "adzuna", "123") is True


def test_listing_exists_returns_false_for_missing(db_conn):
    assert listing_exists(db_conn, "adzuna", "nonexistent") is False


def test_different_sources_same_external_id_both_inserted(db_conn):
    listing_a = _make_listing(external_id="123", source="adzuna")
    listing_b = _make_listing(external_id="123", source="indeed")
    assert insert_listing(db_conn, listing_a) is True
    assert insert_listing(db_conn, listing_b) is True
