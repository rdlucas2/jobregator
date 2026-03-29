import psycopg2


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
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source, external_id)
);
"""


def get_connection(dsn: str):
    return psycopg2.connect(dsn)


def ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute(SCHEMA_SQL)
    conn.commit()


def insert_listing(conn, listing: dict) -> bool:
    """Insert a listing. Returns True if inserted, False if duplicate."""
    sql = """
        INSERT INTO job_listings (source, external_id, title, company, location,
                                  description, url, salary, posted_at, raw_json)
        VALUES (%(source)s, %(external_id)s, %(title)s, %(company)s, %(location)s,
                %(description)s, %(url)s, %(salary)s, %(posted_at)s, %(raw_json)s)
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
