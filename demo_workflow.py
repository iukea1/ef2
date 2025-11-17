#!/usr/bin/env python3
"""
Demonstration of EF2 S3 to SQLite Workflow

This script demonstrates the workflow with sample data since direct S3 access
requires network connectivity for DuckDB extensions.

In a production environment with network access, this would:
1. Connect to S3 DuckDB database
2. Extract IRS 990 tables
3. Save to CSV
4. Import to SQLite
"""

import sqlite3
import pandas as pd
import os
from pathlib import Path

print("=== EF2 Workflow Demonstration ===\n")
print("This demo simulates the workflow using sample data.\n")

# Configuration
CSV_DIR = "CSV"
SQLITE_DB = "ef2_data.sqlite"

# Create CSV directory
Path(CSV_DIR).mkdir(exist_ok=True)

print("Step 1: Creating sample IRS 990 data (simulating S3 extraction)...\n")

# Create sample data that would come from the DuckDB S3 database
# This represents what would be extracted from FLATXML table
sample_data = pd.DataFrame({
    'OBJECTID': ['OID-202120139349301207', 'OID-202120139349301208', 'OID-202120139349301209'],
    'EIN': ['123456789', '987654321', '555555555'],
    'TAXPAYER_NAME': ['Sample Nonprofit 1', 'Sample Nonprofit 2', 'Sample Nonprofit 3'],
    'TAX_YEAR': [2021, 2021, 2021],
    'FORM_TYPE': ['990', '990', '990EZ'],
    'F9_P8_CONTRIBUTIONS_GIFTS_GRANTS': ['500000', '250000', '100000'],
    'F9_P8_PROGRAM_SERVICE_REVENUE': ['300000', '150000', '50000'],
    'F9_P8_INVESTMENT_INCOME': ['50000', '25000', '10000'],
    'F9_P8_TOTAL_REVENUE': ['850000', '425000', '160000'],
    'XPATH': [
        '/Return/ReturnData/IRS990/CYContributionsGrantsAmt',
        '/Return/ReturnData/IRS990/CYContributionsGrantsAmt',
        '/Return/ReturnData/IRS990EZ/ContributionsGiftsGrantsEtcAmt'
    ],
    'URL': [
        'https://nccs-efile.s3.us-east-1.amazonaws.com/xml/202120139349301207_public.xml',
        'https://nccs-efile.s3.us-east-1.amazonaws.com/xml/202120139349301208_public.xml',
        'https://nccs-efile.s3.us-east-1.amazonaws.com/xml/202120139349301209_public.xml'
    ]
})

print(f"  - Created sample dataset with {len(sample_data)} rows and {len(sample_data.columns)} columns")
print(f"  - Columns: {', '.join(sample_data.columns[:5])}...")

print("\nStep 2: Displaying sample data structure...")
print("\nSample Data Preview:")
print("=" * 80)
print(sample_data.head().to_string(index=False))
print("=" * 80)

# Save to CSV (this simulates the extraction step)
table_name = "F9-P08-T00-REVENUE"
csv_filename = f"{CSV_DIR}/{table_name}-2021.csv"

print(f"\nStep 3: Saving to CSV: {csv_filename}")
sample_data.to_csv(csv_filename, index=False)
file_size = os.path.getsize(csv_filename)
print(f"  - CSV file created successfully")
print(f"  - File size: {file_size:,} bytes")

# Import to SQLite
print(f"\nStep 4: Creating SQLite database: {SQLITE_DB}")
sqlite_con = sqlite3.connect(SQLITE_DB)

# Clean table name for SQLite
sqlite_table_name = table_name.replace("-", "_")

print(f"  - Importing data to table: {sqlite_table_name}")
sample_data.to_sql(sqlite_table_name, sqlite_con, if_exists='replace', index=False)
print(f"  - Successfully created table: {sqlite_table_name}")

# Verify the import
print("\nStep 5: Verifying SQLite database...")
cursor = sqlite_con.cursor()

# Count rows
count = cursor.execute(f"SELECT COUNT(*) FROM {sqlite_table_name}").fetchone()[0]
print(f"  - Total rows in table: {count}")

# Get column info
columns = cursor.execute(f"PRAGMA table_info({sqlite_table_name})").fetchall()
print(f"  - Total columns: {len(columns)}")
print("\n  - Column information:")
for col in columns:
    print(f"    - {col[1]} ({col[2]})")

# Sample query
print(f"\nStep 6: Running sample SQL queries...")
print("\n  Query 1: SELECT all records")
df = pd.read_sql_query(f"SELECT * FROM {sqlite_table_name}", sqlite_con)
print(df.to_string(index=False))

print("\n  Query 2: Aggregate by FORM_TYPE")
query = f"""
    SELECT
        FORM_TYPE,
        COUNT(*) as num_filings,
        SUM(CAST(F9_P8_TOTAL_REVENUE AS INTEGER)) as total_revenue
    FROM {sqlite_table_name}
    GROUP BY FORM_TYPE
"""
agg_df = pd.read_sql_query(query, sqlite_con)
print(agg_df.to_string(index=False))

print("\n  Query 3: Filter by revenue threshold")
query = f"""
    SELECT
        TAXPAYER_NAME,
        F9_P8_TOTAL_REVENUE,
        FORM_TYPE
    FROM {sqlite_table_name}
    WHERE CAST(F9_P8_TOTAL_REVENUE AS INTEGER) > 200000
    ORDER BY CAST(F9_P8_TOTAL_REVENUE AS INTEGER) DESC
"""
filtered_df = pd.read_sql_query(query, sqlite_con)
print(filtered_df.to_string(index=False))

# List all tables
print("\nStep 7: Listing all tables in SQLite database...")
tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", sqlite_con)
for i, tbl in enumerate(tables['name'], 1):
    row_count = cursor.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    print(f"  {i}. {tbl} ({row_count} rows)")

# Create index for better query performance
print("\nStep 8: Creating database indexes for optimization...")
cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_ein ON {sqlite_table_name}(EIN);")
cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_tax_year ON {sqlite_table_name}(TAX_YEAR);")
cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_form_type ON {sqlite_table_name}(FORM_TYPE);")
print("  - Created indexes on EIN, TAX_YEAR, and FORM_TYPE columns")

sqlite_con.commit()
sqlite_con.close()

print("\n" + "=" * 80)
print("=== WORKFLOW DEMONSTRATION COMPLETED SUCCESSFULLY ===")
print("=" * 80)
print(f"\nCreated files:")
print(f"  1. CSV file: {csv_filename}")
print(f"  2. SQLite database: {SQLITE_DB}")
print(f"  3. SQLite table: {sqlite_table_name}")

print("\n" + "=" * 80)
print("How to use the SQLite database:")
print("=" * 80)
print(f"\nCommand line:")
print(f"  sqlite3 {SQLITE_DB}")
print(f"  .tables")
print(f"  SELECT * FROM {sqlite_table_name} LIMIT 10;")
print(f"  .exit")

print(f"\nPython:")
print(f"  import sqlite3")
print(f"  import pandas as pd")
print(f"  con = sqlite3.connect('{SQLITE_DB}')")
print(f"  df = pd.read_sql_query('SELECT * FROM {sqlite_table_name}', con)")
print(f"  print(df)")

print("\n" + "=" * 80)
print("Production Workflow (with S3 access):")
print("=" * 80)
print("""
When running in an environment with network access to S3, the workflow would:

1. Connect to S3 DuckDB database:
   - URL: s3://nccs-efile/duckdb/efile_v2_1/EFILE2021.duckdb
   - Uses DuckDB httpfs extension for S3 access
   - Anonymous access to public IRS 990 data

2. Query the FLATXML table:
   - Flattened XML structure with one row per XML node
   - Filter by RDB_TABLE name (e.g., 'F9-P08-T00-REVENUE')
   - Extract terminal nodes (actual data values)

3. Transform data:
   - Pivot from long format to wide format
   - Join with KEYS table for metadata (EIN, Tax Year, Form Type)
   - Apply concordance mappings for column names

4. Export to CSV:
   - Save extracted table to local CSV file
   - Can handle large datasets (millions of rows)

5. Import to SQLite:
   - Create normalized tables
   - Add indexes for query performance
   - Ready for analysis and reporting

See extract_to_sqlite.py for the full implementation that would run with S3 access.
""")

print("\n✓ Demo complete!")
