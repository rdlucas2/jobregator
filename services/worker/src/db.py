import psycopg2
import psycopg2.extras


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS job_listings (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    salary TEXT NOT NULL DEFAULT '',
    posted_at TIMESTAMPTZ,
    raw_json JSONB,
    enriched_json JSONB,
    fit_score FLOAT,
    filter_reason TEXT DEFAULT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source, external_id)
);
"""

MIGRATION_ADD_FILTER_REASON = """
ALTER TABLE job_listings ADD COLUMN IF NOT EXISTS filter_reason TEXT DEFAULT NULL;
"""


def get_connection(dsn: str):
    return psycopg2.connect(dsn)


def ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute(SCHEMA_SQL)
        cur.execute(MIGRATION_ADD_FILTER_REASON)
    conn.commit()


def insert_listing(conn, listing: dict) -> bool:
    """Insert a listing. Returns True if inserted, False if duplicate."""
    sql = """
        INSERT INTO job_listings (source, external_id, title, company, location,
                                  description, url, salary, posted_at, raw_json,
                                  filter_reason)
        VALUES (%(source)s, %(external_id)s, %(title)s, %(company)s, %(location)s,
                %(description)s, %(url)s, %(salary)s, %(posted_at)s, %(raw_json)s,
                %(filter_reason)s)
        ON CONFLICT (source, external_id) DO NOTHING
        RETURNING id
    """
    with conn.cursor() as cur:
        cur.execute(sql, listing)
        inserted = cur.fetchone() is not None
    conn.commit()
    return inserted


def listing_exists(conn, source: str, external_id: str) -> bool:
    """Check if a listing already exists."""
    sql = "SELECT 1 FROM job_listings WHERE source = %s AND external_id = %s"
    with conn.cursor() as cur:
        cur.execute(sql, (source, external_id))
        return cur.fetchone() is not None


def update_enrichment(conn, source: str, external_id: str, enriched_json: dict, fit_score: float):
    """Update a listing with enrichment data from the MCP server."""
    sql = """
        UPDATE job_listings
        SET enriched_json = %(enriched_json)s,
            fit_score = %(fit_score)s,
            updated_at = NOW()
        WHERE source = %(source)s AND external_id = %(external_id)s
    """
    with conn.cursor() as cur:
        cur.execute(sql, {
            "enriched_json": psycopg2.extras.Json(enriched_json),
            "fit_score": fit_score,
            "source": source,
            "external_id": external_id,
        })
    conn.commit()
