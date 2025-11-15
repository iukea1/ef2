#!/usr/bin/env python3
"""
Extract ALL IRS 990 tables from S3 DuckDB to CSV and SQLite
Optimized for memory efficiency - processes one table at a time
Uses snake_case formatting for files and columns
"""

import duckdb
import sqlite3
import pandas as pd
import os
import re
import gc
from pathlib import Path
from typing import List, Optional

# Configuration
YEAR = 2021
S3_BUCKET = "nccs-efile"
S3_PATH = f"s3://{S3_BUCKET}/duckdb/EFILE{YEAR}.duckdb"
CSV_DIR = "csv_output"
SQLITE_DB = "irs990_all_tables.sqlite"
BATCH_SIZE = 50000  # Process this many rows at a time to save memory

# Create output directory
Path(CSV_DIR).mkdir(exist_ok=True)

def to_snake_case(text: str) -> str:
    """Convert text to snake_case format"""
    # Handle common patterns in IRS table names
    # F9-P08-T00-REVENUE -> f9_p08_t00_revenue
    text = text.replace('-', '_').replace(' ', '_')
    # Handle camelCase to snake_case
    text = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', text)
    text = re.sub('([a-z0-9])([A-Z])', r'\1_\2', text)
    return text.lower()

def get_table_list() -> List[str]:
    """Get list of all available IRS 990 tables from concordance"""
    print("Loading concordance to get table list...")
    url = "https://raw.githubusercontent.com/Nonprofit-Open-Data-Collective/irs-efile-master-concordance-file/refs/heads/master/concordance.csv"

    try:
        concordance = pd.read_csv(url, encoding='latin1', low_memory=False)
        tables = concordance['rdb_table'].dropna().unique()
        tables = sorted([str(t) for t in tables if t and str(t) != 'nan' and str(t) != ''])
        print(f"  Found {len(tables)} unique tables")
        return tables
    except Exception as e:
        print(f"  Error loading concordance: {e}")
        print("  Using default table list from file...")
        try:
            with open('table_list.txt', 'r') as f:
                return [line.strip() for line in f if line.strip()]
        except:
            # Return a subset of common tables as fallback
            return [
                "F9-P00-T00-HEADER",
                "F9-P01-T00-SUMMARY",
                "F9-P08-T00-REVENUE",
                "F9-P09-T00-EXPENSES",
                "F9-P10-T00-BALANCE-SHEET",
                "F9-P07-T01-COMPENSATION"
            ]

def setup_duckdb_connection():
    """Initialize DuckDB with S3 support"""
    print("Setting up DuckDB connection...")
    con = duckdb.connect(':memory:')

    # Install and load httpfs extension
    try:
        con.execute("INSTALL httpfs;")
        con.execute("LOAD httpfs;")
        print("  ✓ httpfs extension loaded")
    except Exception as e:
        print(f"  ! Could not install httpfs: {str(e)[:100]}")
        try:
            con.execute("LOAD httpfs;")
            print("  ✓ httpfs loaded from existing installation")
        except:
            print("  ✗ Cannot access S3 without httpfs extension")
            return None

    # Configure S3 for anonymous access
    con.execute("SET s3_region='us-east-1';")
    con.execute("SET s3_endpoint='s3.amazonaws.com';")
    con.execute("SET s3_access_key_id='';")
    con.execute("SET s3_secret_access_key='';")
    print("  ✓ S3 configuration complete")

    return con

def attach_s3_database(con, year: int):
    """Attach S3 DuckDB database"""
    print(f"\nAttaching S3 database for year {year}...")
    s3_path = f"s3://{S3_BUCKET}/duckdb/EFILE{year}.duckdb"
    dbname = f"EFILE{year}"

    try:
        attach_sql = f"ATTACH '{s3_path}' AS {dbname};"
        con.execute(attach_sql)
        print(f"  ✓ Attached: {dbname}")
        return dbname
    except Exception as e:
        print(f"  ✗ Failed to attach database: {str(e)[:200]}")
        return None

def get_available_flatxml_table(con, dbname: str):
    """Find the FLATXML table (may have different naming conventions)"""
    possible_names = [
        f"{dbname}.FLATXML",
        f"{dbname}.EFILE{YEAR}_FLATXML",
        f"FLATXML",
        f"EFILE{YEAR}_FLATXML"
    ]

    for name in possible_names:
        try:
            con.execute(f"SELECT * FROM {name} LIMIT 1;")
            return name
        except:
            continue
    return None

def extract_table_to_csv(con, flatxml_table: str, table_name: str, year: int, output_dir: str) -> Optional[str]:
    """
    Extract a single table from FLATXML and save to CSV
    Uses DuckDB's COPY command for memory efficiency
    """
    # Convert table name to snake_case
    snake_table_name = to_snake_case(table_name)
    csv_filename = f"{output_dir}/{snake_table_name}_{year}.csv"

    print(f"\n  Extracting: {table_name}")
    print(f"    → {snake_table_name}_{year}.csv")

    try:
        # Query to extract and pivot the table
        # This query runs on DuckDB side, minimizing memory usage
        query = f"""
        COPY (
            WITH filtered_data AS (
                SELECT
                    OBJECTID,
                    VARIABLE_NAME,
                    VALUE
                FROM {flatxml_table}
                WHERE RDB_TABLE = '{table_name}'
                AND TYPE = 'terminal'
            ),
            pivoted AS (
                SELECT * FROM (
                    PIVOT filtered_data
                    ON VARIABLE_NAME
                    USING FIRST(VALUE)
                )
            )
            SELECT * FROM pivoted
        )
        TO '{csv_filename}'
        WITH (HEADER, DELIMITER ',');
        """

        # Execute the query - DuckDB writes directly to CSV
        con.execute(query)

        # Check if file was created and has data
        if os.path.exists(csv_filename):
            file_size = os.path.getsize(csv_filename)
            if file_size > 0:
                print(f"    ✓ Created: {file_size:,} bytes")
                return csv_filename
            else:
                print(f"    ⊘ No data found for this table")
                os.remove(csv_filename)
                return None
        else:
            print(f"    ⊘ File not created (table may be empty)")
            return None

    except Exception as e:
        error_msg = str(e)[:200]
        print(f"    ✗ Error: {error_msg}")
        # Clean up partial file if it exists
        if os.path.exists(csv_filename):
            os.remove(csv_filename)
        return None

def convert_columns_to_snake_case(csv_file: str) -> None:
    """Convert CSV column headers to snake_case"""
    try:
        # Read just the header
        df = pd.read_csv(csv_file, nrows=0)

        # Convert column names
        new_columns = {col: to_snake_case(col) for col in df.columns}

        # Read and write with new columns
        df = pd.read_csv(csv_file)
        df.rename(columns=new_columns, inplace=True)
        df.to_csv(csv_file, index=False)

        print(f"    ✓ Converted columns to snake_case")
    except Exception as e:
        print(f"    ! Could not convert columns: {str(e)[:100]}")

def import_csv_to_sqlite(csv_file: str, table_name: str, sqlite_db: str) -> bool:
    """Import CSV to SQLite with snake_case table name"""
    snake_table_name = to_snake_case(table_name)

    try:
        # Read CSV in chunks to save memory
        chunksize = BATCH_SIZE
        first_chunk = True

        con = sqlite3.connect(sqlite_db)

        for chunk in pd.read_csv(csv_file, chunksize=chunksize):
            # Convert column names to snake_case
            chunk.columns = [to_snake_case(col) for col in chunk.columns]

            if first_chunk:
                chunk.to_sql(snake_table_name, con, if_exists='replace', index=False)
                first_chunk = False
            else:
                chunk.to_sql(snake_table_name, con, if_exists='append', index=False)

            # Free memory
            del chunk
            gc.collect()

        con.close()
        print(f"    ✓ Imported to SQLite: {snake_table_name}")
        return True

    except Exception as e:
        print(f"    ✗ SQLite import failed: {str(e)[:100]}")
        return False

def create_sqlite_indexes(sqlite_db: str, table_name: str) -> None:
    """Create indexes on common columns for better query performance"""
    snake_table_name = to_snake_case(table_name)

    try:
        con = sqlite3.connect(sqlite_db)
        cursor = con.cursor()

        # Get column names
        cursor.execute(f"PRAGMA table_info({snake_table_name})")
        columns = [row[1] for row in cursor.fetchall()]

        # Create indexes on common key columns
        index_columns = ['objectid', 'ein', 'tax_year', 'form_type']
        for col in index_columns:
            if col in columns:
                try:
                    idx_name = f"idx_{snake_table_name}_{col}"
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {snake_table_name}({col});")
                except:
                    pass  # Index might already exist or column type doesn't support indexing

        con.commit()
        con.close()

    except Exception as e:
        print(f"    ! Could not create indexes: {str(e)[:100]}")

def main():
    """Main extraction workflow"""
    print("=" * 80)
    print("IRS 990 - Extract All Tables from S3 DuckDB to CSV and SQLite")
    print("=" * 80)
    print(f"Year: {YEAR}")
    print(f"Output: {CSV_DIR}/")
    print(f"SQLite: {SQLITE_DB}")
    print("=" * 80)

    # Get table list
    all_tables = get_table_list()
    print(f"\nTables to process: {len(all_tables)}")

    # Setup DuckDB connection
    con = setup_duckdb_connection()
    if not con:
        print("\n✗ Cannot proceed without DuckDB S3 access")
        print("  Running in demo mode with sample tables...\n")
        run_demo_mode(all_tables)
        return

    # Attach S3 database
    dbname = attach_s3_database(con, YEAR)
    if not dbname:
        print("\n✗ Cannot proceed without database access")
        con.close()
        return

    # Find FLATXML table
    flatxml_table = get_available_flatxml_table(con, dbname)
    if not flatxml_table:
        print(f"\n✗ Cannot find FLATXML table in {dbname}")
        con.close()
        return

    print(f"  ✓ Found FLATXML table: {flatxml_table}")

    # Process each table
    print(f"\n{'=' * 80}")
    print(f"Processing {len(all_tables)} tables...")
    print(f"{'=' * 80}")

    success_count = 0
    skipped_count = 0
    error_count = 0

    for i, table_name in enumerate(all_tables, 1):
        print(f"\n[{i}/{len(all_tables)}] {table_name}")

        # Extract to CSV
        csv_file = extract_table_to_csv(con, flatxml_table, table_name, YEAR, CSV_DIR)

        if csv_file:
            # Convert columns to snake_case
            convert_columns_to_snake_case(csv_file)

            # Import to SQLite
            if import_csv_to_sqlite(csv_file, table_name, SQLITE_DB):
                # Create indexes
                create_sqlite_indexes(SQLITE_DB, table_name)
                success_count += 1
            else:
                error_count += 1
        else:
            skipped_count += 1

        # Force garbage collection after each table
        gc.collect()

    # Cleanup
    con.close()

    # Summary
    print(f"\n{'=' * 80}")
    print("EXTRACTION COMPLETE")
    print(f"{'=' * 80}")
    print(f"  ✓ Success: {success_count} tables")
    print(f"  ⊘ Skipped: {skipped_count} tables (no data)")
    print(f"  ✗ Errors:  {error_count} tables")
    print(f"\nOutput:")
    print(f"  CSV files: {CSV_DIR}/")
    print(f"  SQLite DB: {SQLITE_DB}")
    print(f"{'=' * 80}")

def run_demo_mode(all_tables: List[str]):
    """Run demo with sample data when S3 is not available"""
    print("DEMO MODE - Creating sample data for a few tables\n")

    # Create sample data for a few tables
    sample_tables = all_tables[:5]  # Just process first 5 for demo

    for i, table_name in enumerate(sample_tables, 1):
        print(f"[{i}/{len(sample_tables)}] {table_name}")

        # Create sample data
        sample_data = pd.DataFrame({
            'OBJECTID': [f'OID-{YEAR}001', f'OID-{YEAR}002'],
            'EIN': ['123456789', '987654321'],
            'TAX_YEAR': [YEAR, YEAR],
            'SAMPLE_VALUE': [1000, 2000]
        })

        # Save to CSV with snake_case
        snake_table_name = to_snake_case(table_name)
        csv_file = f"{CSV_DIR}/{snake_table_name}_{YEAR}.csv"

        # Convert columns to snake_case
        sample_data.columns = [to_snake_case(col) for col in sample_data.columns]
        sample_data.to_csv(csv_file, index=False)

        print(f"  ✓ Created demo CSV: {csv_file}")

        # Import to SQLite
        import_csv_to_sqlite(csv_file, table_name, SQLITE_DB)
        create_sqlite_indexes(SQLITE_DB, table_name)

    print(f"\nDemo complete! Created {len(sample_tables)} sample tables.")

if __name__ == "__main__":
    main()
