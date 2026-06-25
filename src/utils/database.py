# src/utils/database.py
"""
AgroTwinX database layer — now backed by PostgreSQL (Supabase + pgvector).

DROP-IN REPLACEMENT: the public API is identical to the old SQLite class
(insert / get / update / query / get_connection / close), so the 23 files
that use it need NO changes. SQLite-isms are absorbed here:
  - '?' placeholders are auto-translated to '%s'
  - INSERT returns the new id via RETURNING (replaces sqlite lastrowid)
  - rows come back as dicts (like sqlite3.Row -> dict)

Reads DATABASE_URL from the environment (.env). Example:
  DATABASE_URL=postgresql://postgres.<ref>:<pwd>@<host>.pooler.supabase.com:5432/postgres
"""

import os
import threading
import psycopg2
import psycopg2.extras

# Primary-key column for each table (for INSERT ... RETURNING)
_PK = {
    "farmers": "farmer_id", "farms": "farm_id", "digital_twins": "twin_id",
    "satellite_observations": "observation_id", "weather_data": "weather_id",
    "disease_detections": "detection_id", "buyers": "buyer_id",
    "stubble_listings": "listing_id", "stubble_transactions": "transaction_id",
    "carbon_certificates": "certificate_id", "platform_revenue": "revenue_id",
    "b2b_clients": "client_id", "data_reports": "report_id",
    "impact_metrics": "metric_id", "agronomy_chunks": "id",
}


def _q(sql: str) -> str:
    """Translate SQLite '?' placeholders to psycopg2 '%s'."""
    return sql.replace("?", "%s")


class _CursorShim:
    """Wraps a RealDictCursor so legacy code using raw cursors keeps working
    (auto-translates '?' and exposes dict rows)."""
    def __init__(self, cur):
        self._cur = cur

    def execute(self, sql, params=None):
        return self._cur.execute(_q(sql), params or ())

    def executemany(self, sql, seq):
        return self._cur.executemany(_q(sql), seq)

    def fetchone(self):
        row = self._cur.fetchone()
        return dict(row) if row is not None else None

    def fetchall(self):
        return [dict(r) for r in self._cur.fetchall()]

    @property
    def rowcount(self):
        return self._cur.rowcount

    def __getattr__(self, name):
        return getattr(self._cur, name)


class _ConnShim:
    """Wraps a psycopg2 connection so .cursor() returns the shim."""
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return _CursorShim(self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor))

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def __getattr__(self, name):
        return getattr(self._conn, name)


class Database:
    """PostgreSQL-backed database with the original SQLite-era API."""

    def __init__(self, db_path=None):
        # db_path kept only for signature compatibility; ignored on Postgres.
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            raise RuntimeError("DATABASE_URL not set (put your Supabase string in .env)")
        # asyncpg URL -> plain libpq for psycopg2
        self._dsn = self.database_url.replace("+asyncpg", "").replace("+psycopg2", "")
        self._local = threading.local()
        print("✅ Database connected (PostgreSQL)")

    # ---- connection management (thread-local, like the old version) ----
    def get_connection(self):
        if not getattr(self._local, "conn", None) or self._local.conn.closed:
            raw = psycopg2.connect(self._dsn)
            raw.autocommit = False
            self._local.conn = raw
        return _ConnShim(self._local.conn)

    # ---- CRUD (identical signatures to the old SQLite class) ----
    def insert(self, table, data):
        conn = self.get_connection()
        cur = conn.cursor()
        cols = ", ".join(data.keys())
        ph = ", ".join(["%s"] * len(data))
        pk = _PK.get(table, "id")
        cur.execute(f"INSERT INTO {table} ({cols}) VALUES ({ph}) RETURNING {pk}",
                    list(data.values()))
        new_id = cur.fetchone()[pk]
        conn.commit()
        return new_id

    def get(self, table, id_column, id_value):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {table} WHERE {id_column} = %s", (id_value,))
        return cur.fetchone()

    def update(self, table, id_column, id_value, data):
        conn = self.get_connection()
        cur = conn.cursor()
        sets = ", ".join([f"{k} = %s" for k in data.keys()])
        cur.execute(f"UPDATE {table} SET {sets} WHERE {id_column} = %s",
                    list(data.values()) + [id_value])
        conn.commit()
        return cur.rowcount

    def query(self, sql, params=None):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute(sql, params or ())          # _CursorShim translates '?' -> '%s'
        if cur.description:                      # SELECT -> rows
            rows = cur.fetchall()
            conn.commit()
            return rows
        conn.commit()                            # DDL/INSERT/UPDATE
        return []

    def close(self):
        conn = getattr(self._local, "conn", None)
        if conn and not conn.closed:
            conn.close()
            self._local.conn = None