# migrate_sqlite_to_pg.py
"""
One-time migration: copies all rows from the old SQLite DB into PostgreSQL
(Supabase). Run AFTER create_all() has built the Postgres schema.

    python migrate_sqlite_to_pg.py                       # uses data/agrotwinx.db
    python migrate_sqlite_to_pg.py path/to/agrotwinx.db

Reads DATABASE_URL from the environment. Safe to re-run? No — it appends.
Run it once on a freshly-created (empty) Postgres schema.
"""

import os, sys, sqlite3
import psycopg2, psycopg2.extras

# FK-safe load order (parents before children)
ORDER = [
    "farmers", "farms", "digital_twins", "satellite_observations", "weather_data",
    "disease_detections", "buyers", "stubble_listings", "stubble_transactions",
    "carbon_certificates", "platform_revenue", "b2b_clients", "data_reports",
    "impact_metrics",
]
BOOL_COLS = set()   # active/delivered kept as INTEGER 0/1 (matches SQLite + app queries)
SERIAL_PK = {  # tables whose PK is an auto sequence (carbon_certificates is text -> excluded)
    "farmers": "farmer_id", "farms": "farm_id", "digital_twins": "twin_id",
    "satellite_observations": "observation_id", "weather_data": "weather_id",
    "disease_detections": "detection_id", "buyers": "buyer_id",
    "stubble_listings": "listing_id", "stubble_transactions": "transaction_id",
    "platform_revenue": "revenue_id", "b2b_clients": "client_id",
    "data_reports": "report_id", "impact_metrics": "metric_id",
}


def main():
    sqlite_path = sys.argv[1] if len(sys.argv) > 1 else "data/agrotwinx.db"
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit("❌ DATABASE_URL not set")
    dsn = url.replace("+asyncpg", "").replace("+psycopg2", "")
    if not os.path.exists(sqlite_path):
        sys.exit(f"❌ SQLite file not found: {sqlite_path}")

    sl = sqlite3.connect(sqlite_path); sl.row_factory = sqlite3.Row
    pg = psycopg2.connect(dsn); pg.autocommit = False
    pcur = pg.cursor()

    existing = {r[0] for r in sl.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

    total = 0
    for table in ORDER:
        if table not in existing:
            print(f"  – {table}: not in source, skip"); continue
        rows = sl.execute(f"SELECT * FROM {table}").fetchall()
        if not rows:
            print(f"  – {table}: 0 rows"); continue
        cols = rows[0].keys()
        def conv(c, v):
            if c in BOOL_COLS and v is not None:
                return bool(v)
            return v
        values = [[conv(c, r[c]) for c in cols] for r in rows]
        collist = ", ".join(cols)
        ph = "(" + ", ".join(["%s"] * len(cols)) + ")"
        psycopg2.extras.execute_values(
            pcur, f"INSERT INTO {table} ({collist}) VALUES %s", values, template=ph)
        pg.commit()
        print(f"  ✅ {table}: {len(rows)} rows")
        total += len(rows)

    # Reset sequences so future natural inserts don't collide with copied ids
    for table, pk in SERIAL_PK.items():
        if table in existing:
            pcur.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}','{pk}'), "
                f"COALESCE((SELECT MAX({pk}) FROM {table}), 1), true)")
    pg.commit()
    print(f"\n✅ Migration complete: {total} rows copied, sequences reset.")
    sl.close(); pg.close()


if __name__ == "__main__":
    main()