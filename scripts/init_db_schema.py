#!/usr/bin/env python3
"""
Initialize database schema on Railway.
Reads schema.sql and applies it to the DATABASE_URL.
"""
import os
import sys
from pathlib import Path
import psycopg2

def main():
    # Get database URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    # Convert asyncpg URL to psycopg2 format if needed
    if database_url.startswith('postgresql+asyncpg://'):
        database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')

    # Read schema.sql
    schema_path = Path(__file__).parent.parent / 'db' / 'schema.sql'
    if not schema_path.exists():
        print(f"ERROR: schema.sql not found at {schema_path}")
        sys.exit(1)

    with open(schema_path, 'r') as f:
        schema_sql = f.read()

    # Connect and apply schema
    print("Connecting to database...")
    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        cur = conn.cursor()

        print("Applying schema.sql...")
        cur.execute(schema_sql)

        print("✅ Schema applied successfully!")

        # Verify tables exist
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = [row[0] for row in cur.fetchall()]
        print(f"\n✅ Created {len(tables)} tables:")
        for table in tables:
            print(f"  - {table}")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"ERROR applying schema: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
