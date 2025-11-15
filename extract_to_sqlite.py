#!/usr/bin/env python3
"""
Script to connect to S3 DuckDB, extract table to CSV, and import to SQLite
This script demonstrates the EF2 workflow using Python
"""

import duckdb
import sqlite3
import pandas as pd
import os
from pathlib import Path

print("=== EF2 S3 to SQLite Workflow ===\n")

# Configuration
YEAR = 2021
S3_BUCKET = "nccs-efile"
S3_PATH = f"s3://{S3_BUCKET}/duckdb/EFILE{YEAR}.duckdb"
TABLE_NAME = "F9-P08-T00-REVENUE"
CSV_DIR = "CSV"
CSV_FILENAME = f"{CSV_DIR}/{TABLE_NAME}-{YEAR}.csv"
SQLITE_DB = "ef2_data.sqlite"

# Create CSV directory
Path(CSV_DIR).mkdir(exist_ok=True)

print("Step 1: Connecting to DuckDB with S3 support...\n")

# Create DuckDB connection with S3 support
con = duckdb.connect(':memory:')

# Install and load httpfs extension for S3 access
print("  - Setting up httpfs extension for S3 access...")
try:
    # Try to install and load httpfs
    con.execute("INSTALL httpfs;")
    con.execute("LOAD httpfs;")
    print("  - httpfs extension loaded successfully")
except Exception as e:
    print(f"  - Note: Could not install httpfs extension ({str(e)})")
    print("  - Attempting to load if already installed...")
    try:
        con.execute("LOAD httpfs;")
        print("  - httpfs extension loaded from existing installation")
    except:
        print("  - WARNING: Cannot access S3 without httpfs extension")
        print("  - This script requires network access to download DuckDB extensions")
        raise

# Configure S3 settings for anonymous access
print("  - Configuring S3 settings...")
con.execute("SET s3_region='us-east-1';")
con.execute("SET s3_endpoint='s3.amazonaws.com';")
con.execute("SET s3_access_key_id='';")
con.execute("SET s3_secret_access_key='';")

print(f"\nStep 2: Attaching S3 database: {S3_PATH}...\n")

try:
    # Attach the S3 database
    dbname = f"EFILE{YEAR}"
    attach_sql = f"ATTACH '{S3_PATH}' AS {dbname};"
    print(f"  - Executing: {attach_sql}")
    con.execute(attach_sql)

    print(f"  - Successfully attached database: {dbname}")

    # List available tables
    print("\nStep 3: Listing available tables in the database...\n")
    tables = con.execute(f"SELECT name FROM {dbname}.sqlite_master WHERE type='table';").fetchall()
    print(f"  - Available tables: {len(tables)}")
    for table in tables[:10]:  # Show first 10 tables
        print(f"    - {table[0]}")
    if len(tables) > 10:
        print(f"    ... and {len(tables) - 10} more tables")

    # Check if FLATXML table exists
    flatxml_table = f"{dbname}.EFILE{YEAR}_FLATXML"
    print(f"\nStep 4: Checking for FLATXML table: {flatxml_table}...")

    # Try different table naming conventions
    possible_tables = [
        f"{dbname}.EFILE{YEAR}_FLATXML",
        f"{dbname}.FLATXML",
        f"{dbname}.EFILE{YEAR}.FLATXML"
    ]

    flatxml_exists = None
    for tbl in possible_tables:
        try:
            count = con.execute(f"SELECT COUNT(*) FROM {tbl} LIMIT 1;").fetchone()
            flatxml_exists = tbl
            print(f"  - Found table: {tbl}")
            break
        except:
            continue

    if flatxml_exists:
        # Get sample data to understand structure
        print(f"\nStep 5: Examining FLATXML table structure...")
        sample = con.execute(f"SELECT * FROM {flatxml_exists} LIMIT 5;").fetchdf()
        print(f"  - Columns: {list(sample.columns)}")
        print(f"  - Sample rows: {len(sample)}")
        print("\n  - Sample data:")
        print(sample.head())

        # Extract data for specific table
        print(f"\nStep 6: Extracting data for table: {TABLE_NAME}...")

        # Query to filter for specific RDB_TABLE
        query = f"""
        SELECT *
        FROM {flatxml_exists}
        WHERE RDB_TABLE = '{TABLE_NAME}'
        AND TYPE = 'terminal'
        LIMIT 10000
        """

        print(f"  - Executing query to extract {TABLE_NAME} data...")
        df = con.execute(query).fetchdf()
        print(f"  - Extracted {len(df)} rows")

        if len(df) > 0:
            # Save to CSV
            print(f"\nStep 7: Writing to CSV: {CSV_FILENAME}")
            df.to_csv(CSV_FILENAME, index=False)
            file_size = os.path.getsize(CSV_FILENAME)
            print(f"  - CSV file created successfully")
            print(f"  - File size: {file_size:,} bytes")

            # Import to SQLite
            print(f"\nStep 8: Importing to SQLite database: {SQLITE_DB}")
            sqlite_con = sqlite3.connect(SQLITE_DB)

            # Clean table name for SQLite (replace dashes with underscores)
            sqlite_table_name = TABLE_NAME.replace("-", "_")

            print(f"  - Writing to SQLite table: {sqlite_table_name}")
            df.to_sql(sqlite_table_name, sqlite_con, if_exists='replace', index=False)

            # Verify data in SQLite
            print("\nStep 9: Verifying data in SQLite...")
            cursor = sqlite_con.cursor()
            count = cursor.execute(f"SELECT COUNT(*) FROM {sqlite_table_name}").fetchone()[0]
            print(f"  - Rows in SQLite table: {count:,}")

            # Show sample data
            print("\n  - Sample data from SQLite:")
            sample_df = pd.read_sql_query(f"SELECT * FROM {sqlite_table_name} LIMIT 5", sqlite_con)
            print(sample_df)

            # List all tables
            print("\n  - All tables in SQLite database:")
            tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", sqlite_con)
            for tbl in tables['name']:
                print(f"    - {tbl}")

            sqlite_con.close()

            print("\n=== WORKFLOW COMPLETED SUCCESSFULLY ===")
            print(f"CSV file: {CSV_FILENAME}")
            print(f"SQLite database: {SQLITE_DB}")
            print(f"SQLite table: {sqlite_table_name}")
            print("\nYou can now query the SQLite database using:")
            print(f"  sqlite3 {SQLITE_DB}")
            print(f"  SELECT * FROM {sqlite_table_name} LIMIT 10;")
        else:
            print(f"\n  - No data found for table: {TABLE_NAME}")
            print("  - This might be expected if the table doesn't exist for this year")
    else:
        print("\n  - FLATXML table not found. Listing all available tables:")
        all_tables = con.execute(f"SHOW TABLES FROM {dbname};").fetchall()
        for tbl in all_tables:
            print(f"    - {tbl[0]}")

except Exception as e:
    print(f"\nError occurred: {type(e).__name__}: {str(e)}")
    print("\nThis might be due to:")
    print("  1. Network connectivity issues")
    print("  2. S3 bucket access restrictions")
    print("  3. Database file not existing at the specified path")
    print("  4. DuckDB version compatibility")

    import traceback
    print("\nFull traceback:")
    traceback.print_exc()

finally:
    con.close()
    print("\n  - DuckDB connection closed")
