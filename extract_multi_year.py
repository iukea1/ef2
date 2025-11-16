#!/usr/bin/env python3
"""
Multi-Year IRS 990 Data Extraction

Extract data across multiple tax years and combine for longitudinal analysis.
Supports parallel extraction and automatic data combination.
"""

import duckdb
import sqlite3
import pandas as pd
import os
import re
import gc
from pathlib import Path
from typing import List, Dict
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from datetime import datetime
import logging
from logging_config import setup_logging, log_performance, LogBlock

# Optional memory monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Setup logger
logger = setup_logging("extract_multi_year", level="INFO")

# Configuration
S3_BUCKET = "nccs-efile"
S3_VERSION = "efile_v2_1"  # Database version
S3_BASE_PATH = f"s3://{S3_BUCKET}/duckdb/{S3_VERSION}"
CSV_DIR = "csv_multi_year"
SQLITE_DIR = "sqlite_multi_year"
COMBINED_DB = "irs990_combined_years.sqlite"
CACHE_DIR = "duckdb_cache"  # Local cache for downloaded databases

# Create output directories
Path(CSV_DIR).mkdir(exist_ok=True)
Path(SQLITE_DIR).mkdir(exist_ok=True)
Path(CACHE_DIR).mkdir(exist_ok=True)

def to_snake_case(text: str) -> str:
    """Convert text to snake_case"""
    text = text.replace('-', '_').replace(' ', '_')
    text = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', text)
    text = re.sub('([a-z0-9])([A-Z])', r'\1_\2', text)
    return text.lower()

def log_memory_usage():
    """Log current memory usage if psutil is available"""
    if PSUTIL_AVAILABLE:
        process = psutil.Process()
        mem_info = process.memory_info()
        mem_mb = mem_info.rss / 1024 / 1024
        mem_percent = process.memory_percent()
        logger.debug(f"Memory usage: {mem_mb:.1f} MB ({mem_percent:.1f}%)")

        # Warning if memory usage is high
        if mem_percent > 80:
            logger.warning(f"High memory usage: {mem_percent:.1f}% - Consider reducing batch size")

        return mem_mb
    return None

def get_cached_db_path(year: int) -> Path:
    """Get path to cached local database for a given year"""
    return Path(CACHE_DIR) / f"EFILE{year}.duckdb"

def download_database_to_cache(year: int, s3_con: duckdb.DuckDBPyConnection, flatxml_table: str) -> Path:
    """
    Download/cache DuckDB database locally for faster repeated queries
    This dramatically speeds up extraction by eliminating S3 network latency

    Args:
        year: Tax year
        s3_con: DuckDB connection with S3 database already attached
        flatxml_table: Name of the FLATXML table in the attached database
    """
    cache_path = get_cached_db_path(year)

    if cache_path.exists():
        logger.info(f"Cache already exists: {cache_path}")
        cache_size_mb = cache_path.stat().st_size / 1024 / 1024
        logger.info(f"  Cache size: {cache_size_mb:.1f} MB")
        return cache_path

    logger.info(f"Downloading database to cache: {cache_path}")
    logger.info("  This is a one-time operation per year - subsequent runs will be much faster!")
    logger.info("  Note: This will download the entire FLATXML table (~500MB-2GB depending on year)")

    try:
        # Export the FLATXML table from S3 to a local DuckDB file
        logger.info(f"  Copying FLATXML table from S3 (this may take 5-15 minutes)...")

        # Use DuckDB's CREATE TABLE AS to copy data from S3 to local file
        # This is done in a single operation for efficiency
        export_query = f"""
        COPY (SELECT * FROM {flatxml_table})
        TO '{cache_path.parent / f"EFILE{year}_flatxml.parquet"}'
        (FORMAT PARQUET);
        """
        s3_con.execute(export_query)

        # Now create the local database and import the parquet file
        logger.info("  Creating local cache database...")
        local_con = duckdb.connect(str(cache_path))

        import_query = f"""
        CREATE TABLE FLATXML AS
        SELECT * FROM '{cache_path.parent / f"EFILE{year}_flatxml.parquet"}';
        """
        local_con.execute(import_query)
        local_con.close()

        # Clean up temporary parquet file
        parquet_file = cache_path.parent / f"EFILE{year}_flatxml.parquet"
        if parquet_file.exists():
            parquet_file.unlink()

        cache_size_mb = cache_path.stat().st_size / 1024 / 1024
        logger.info(f"  ✓ Cache created: {cache_size_mb:.1f} MB")
        logger.info(f"  ✓ Future extractions for {year} will be much faster!")

        return cache_path

    except Exception as e:
        logger.error(f"Failed to create cache: {str(e)[:200]}")
        # Clean up partial files
        if cache_path.exists():
            cache_path.unlink()
        parquet_file = cache_path.parent / f"EFILE{year}_flatxml.parquet"
        if parquet_file.exists():
            parquet_file.unlink()
        raise

def should_skip_table(year: int, table_name: str, skip_existing: bool) -> bool:
    """Check if table CSV already exists and should be skipped"""
    if not skip_existing:
        return False

    snake_name = to_snake_case(table_name)
    year_dir = Path(CSV_DIR) / str(year)
    csv_file = year_dir / f"{snake_name}.csv"

    if csv_file.exists() and csv_file.stat().st_size > 0:
        logger.debug(f"Skipping existing: {snake_name}")
        return True

    return False

@log_performance
def get_table_list() -> List[str]:
    """Get list of all IRS 990 tables"""
    url = "https://raw.githubusercontent.com/Nonprofit-Open-Data-Collective/irs-efile-master-concordance-file/refs/heads/master/concordance.csv"
    logger.debug(f"Loading concordance from: {url}")
    try:
        concordance = pd.read_csv(url, encoding='latin1', low_memory=False)
        tables = concordance['rdb_table'].dropna().unique()
        tables = sorted([str(t) for t in tables if t and str(t) != 'nan' and str(t) != ''])
        logger.info(f"Loaded {len(tables)} tables from concordance")
        return tables
    except Exception as e:
        logger.warning(f"Could not load concordance: {e}. Using fallback tables.")
        # Return core tables as fallback
        return [
            "F9-P00-T00-HEADER",
            "F9-P08-T00-REVENUE",
            "F9-P09-T00-EXPENSES",
            "F9-P10-T00-BALANCE-SHEET",
            "F9-P07-T01-COMPENSATION"
        ]

def setup_duckdb_s3():
    """Setup DuckDB with S3 support"""
    logger.debug("Setting up DuckDB with S3 support")
    con = duckdb.connect(':memory:')
    try:
        logger.debug("Installing httpfs extension")
        con.execute("INSTALL httpfs;")
        con.execute("LOAD httpfs;")
        logger.info("httpfs extension loaded successfully")
    except Exception as e:
        logger.debug(f"httpfs install failed: {e}. Trying to load existing...")
        try:
            con.execute("LOAD httpfs;")
            logger.info("httpfs extension loaded from existing installation")
        except Exception as e2:
            logger.error(f"Failed to load httpfs: {e2}")
            return None

    logger.debug("Configuring S3 settings")
    con.execute("SET s3_region='us-east-1';")
    con.execute("SET s3_endpoint='s3.amazonaws.com';")
    con.execute("SET s3_access_key_id='';")
    con.execute("SET s3_secret_access_key='';")
    logger.info("DuckDB S3 setup complete")

    return con

@log_performance
def extract_year_data(year: int, tables: List[str], sample_size: int = None,
                      skip_existing: bool = False, batch_size: int = 10) -> Dict:
    """
    Extract data for a single year using direct S3 queries

    Args:
        year: Tax year to extract
        tables: List of table names to extract
        sample_size: Optional row limit per table
        skip_existing: If True, skip tables that already have CSV files
        batch_size: Force garbage collection after this many tables
    """
    logger.info(f"{'='*80}")
    logger.info(f"Processing Year: {year}")
    logger.info(f"{'='*80}")

    results = {
        'year': year,
        'tables_extracted': 0,
        'tables_failed': 0,
        'total_rows': 0,
        'timestamp': datetime.now().isoformat()
    }

    # Setup DuckDB
    con = setup_duckdb_s3()
    if not con:
        print(f"  ✗ Cannot setup DuckDB for year {year}")
        return results

    # Attach S3 database directly
    db_path = f"{S3_BASE_PATH}/EFILE{year}.duckdb"
    dbname = f"EFILE{year}"
    logger.debug(f"Connecting to S3 database: {db_path}")

    try:
        con.execute(f"ATTACH '{db_path}' AS {dbname};")
        print(f"  ✓ Attached S3 database: {dbname}")
    except Exception as e:
        print(f"  ✗ Could not attach database: {str(e)[:100]}")
        con.close()
        return results

    # Find FLATXML table
    flatxml_table = None
    for name in [f"{dbname}.FLATXML", f"{dbname}.EFILE{year}_FLATXML"]:
        try:
            con.execute(f"SELECT * FROM {name} LIMIT 1;")
            flatxml_table = name
            logger.debug(f"Found FLATXML table: {name}")
            break
        except:
            continue

    if not flatxml_table:
        print(f"  ✗ FLATXML table not found")
        con.close()
        return results

    # Extract each table
    year_dir = Path(CSV_DIR) / str(year)
    year_dir.mkdir(exist_ok=True)

    tables_skipped = 0

    for idx, table_name in enumerate(tables, 1):
        snake_name = to_snake_case(table_name)
        csv_file = year_dir / f"{snake_name}.csv"

        # Skip if CSV already exists and skip_existing is True
        if should_skip_table(year, table_name, skip_existing):
            tables_skipped += 1
            continue

        # Progress indicator
        print(f"\n  [{idx}/{len(tables)}] Processing: {table_name}")

        try:
            # Build query with optional sampling (LIMIT applied after PIVOT for efficiency)
            limit_clause = f"LIMIT {sample_size}" if sample_size else ""

            query = f"""
            COPY (
                SELECT * FROM (
                    PIVOT (
                        SELECT OBJECTID, VARIABLE_NAME, VALUE
                        FROM {flatxml_table}
                        WHERE RDB_TABLE = '{table_name}'
                        AND TYPE = 'terminal'
                    )
                    ON VARIABLE_NAME
                    USING FIRST(VALUE)
                )
                {limit_clause}
            )
            TO '{csv_file}'
            WITH (HEADER, DELIMITER ',');
            """

            con.execute(query)

            if csv_file.exists() and csv_file.stat().st_size > 0:
                # Count rows
                row_count = sum(1 for _ in open(csv_file)) - 1  # -1 for header
                results['tables_extracted'] += 1
                results['total_rows'] += row_count
                print(f"    ✓ {snake_name}: {row_count:,} rows")
            else:
                results['tables_failed'] += 1

        except Exception as e:
            results['tables_failed'] += 1
            print(f"    ✗ Error: {str(e)[:80]}")

        # Aggressive memory cleanup every batch_size tables
        if idx % batch_size == 0:
            logger.info(f"  Batch checkpoint ({idx}/{len(tables)}) - forcing garbage collection")
            gc.collect()
            log_memory_usage()
            print(f"  Progress: {idx}/{len(tables)} tables processed ({results['tables_extracted']} successful)")

    con.close()
    gc.collect()  # Final cleanup for this year

    print(f"\n  Summary for {year}:")
    print(f"    Extracted: {results['tables_extracted']} tables")
    print(f"    Failed: {results['tables_failed']} tables")
    if tables_skipped > 0:
        print(f"    Skipped (already exist): {tables_skipped} tables")
    print(f"    Total rows: {results['total_rows']:,}")

    return results

def combine_year_data(years: List[int], tables: List[str]):
    """Combine data across years into single database with memory-efficient chunked processing"""
    print(f"\n{'='*80}")
    print(f"COMBINING DATA ACROSS YEARS: {min(years)}-{max(years)}")
    print(f"{'='*80}")

    con = sqlite3.connect(COMBINED_DB)
    CHUNK_SIZE = 50000  # Process 50k rows at a time

    for table_name in tables:
        snake_name = to_snake_case(table_name)
        print(f"\n  Combining: {snake_name}")

        years_found = []
        total_rows = 0
        first_write = True

        for year in years:
            csv_file = Path(CSV_DIR) / str(year) / f"{snake_name}.csv"

            if csv_file.exists():
                try:
                    # Process CSV in chunks to avoid loading entire file into memory
                    for chunk in pd.read_csv(csv_file, chunksize=CHUNK_SIZE):
                        # Convert column names to snake_case
                        chunk.columns = [to_snake_case(col) for col in chunk.columns]

                        # Add year column if not present
                        if 'tax_year' not in chunk.columns:
                            chunk['tax_year'] = year

                        # Write chunk to database
                        if first_write:
                            chunk.to_sql(snake_name, con, if_exists='replace', index=False)
                            first_write = False
                        else:
                            chunk.to_sql(snake_name, con, if_exists='append', index=False)

                        total_rows += len(chunk)

                        # Free memory
                        del chunk
                        gc.collect()

                    years_found.append(year)

                except Exception as e:
                    print(f"    ✗ Error reading {year}: {str(e)[:50]}")

        if years_found:
            # Create indexes after all data is loaded
            try:
                con.execute(f"CREATE INDEX IF NOT EXISTS idx_{snake_name}_objectid ON {snake_name}(objectid);")
                con.execute(f"CREATE INDEX IF NOT EXISTS idx_{snake_name}_tax_year ON {snake_name}(tax_year);")

                # Check if 'ein' column exists before creating index
                cursor = con.execute(f"PRAGMA table_info({snake_name})")
                columns = [row[1] for row in cursor.fetchall()]
                if 'ein' in columns:
                    con.execute(f"CREATE INDEX IF NOT EXISTS idx_{snake_name}_ein ON {snake_name}(ein);")
            except Exception as e:
                print(f"    ! Index creation warning: {str(e)[:50]}")

            print(f"    ✓ Combined {len(years_found)} years: {years_found}")
            print(f"    ✓ Total rows: {total_rows:,}")
        else:
            print(f"    ⊘ No data found for any year")

    con.commit()
    con.close()

    print(f"\n{'='*80}")
    print(f"✓ Combined database created: {COMBINED_DB}")
    print(f"{'='*80}")

def analyze_multi_year_coverage(years: List[int], tables: List[str]):
    """Analyze data coverage across years"""
    print(f"\n{'='*80}")
    print(f"MULTI-YEAR DATA COVERAGE ANALYSIS")
    print(f"{'='*80}")

    coverage = {}

    for table_name in tables:
        snake_name = to_snake_case(table_name)
        coverage[snake_name] = {}

        for year in years:
            csv_file = Path(CSV_DIR) / str(year) / f"{snake_name}.csv"
            if csv_file.exists():
                row_count = sum(1 for _ in open(csv_file)) - 1
                coverage[snake_name][year] = row_count
            else:
                coverage[snake_name][year] = 0

    # Create summary
    print("\nTable Coverage by Year:")
    print(f"{'Table':<40} {' '.join(str(y) for y in years)}")
    print("-" * 80)

    for table, year_data in sorted(coverage.items())[:10]:  # Show first 10
        counts = [f"{year_data.get(y, 0):>6,}" for y in years]
        print(f"{table:<40} {' '.join(counts)}")

    # Overall statistics
    print("\nOverall Statistics:")
    total_by_year = {year: sum(coverage[t].get(year, 0) for t in coverage) for year in years}
    for year, total in total_by_year.items():
        print(f"  {year}: {total:,} total rows")

def create_longitudinal_views(years: List[int]):
    """Create SQL views for longitudinal analysis"""
    print(f"\n{'='*80}")
    print(f"CREATING LONGITUDINAL ANALYSIS VIEWS")
    print(f"{'='*80}")

    con = sqlite3.connect(COMBINED_DB)

    # View 1: Revenue trends over time
    try:
        con.execute("""
            CREATE VIEW IF NOT EXISTS revenue_trends AS
            SELECT
                ein,
                tax_year,
                CAST(f9_p8_total_revenue AS INTEGER) as total_revenue,
                CAST(f9_p8_contributions_gifts_grants AS INTEGER) as contributions,
                CAST(f9_p8_program_service_revenue AS INTEGER) as program_revenue
            FROM f9_p08_t00_revenue
            WHERE f9_p8_total_revenue IS NOT NULL
            ORDER BY ein, tax_year;
        """)
        print("  ✓ Created view: revenue_trends")
    except Exception as e:
        print(f"  ⊘ Could not create revenue_trends: {str(e)[:50]}")

    # View 2: Year-over-year growth
    try:
        con.execute("""
            CREATE VIEW IF NOT EXISTS yoy_growth AS
            SELECT
                curr.ein,
                curr.tax_year,
                CAST(curr.f9_p8_total_revenue AS INTEGER) as current_revenue,
                CAST(prev.f9_p8_total_revenue AS INTEGER) as prior_revenue,
                ROUND(
                    (CAST(curr.f9_p8_total_revenue AS REAL) - CAST(prev.f9_p8_total_revenue AS REAL)) /
                    CAST(prev.f9_p8_total_revenue AS REAL) * 100,
                    2
                ) as growth_rate
            FROM f9_p08_t00_revenue curr
            LEFT JOIN f9_p08_t00_revenue prev
                ON curr.ein = prev.ein
                AND curr.tax_year = prev.tax_year + 1
            WHERE curr.f9_p8_total_revenue IS NOT NULL
                AND prev.f9_p8_total_revenue IS NOT NULL;
        """)
        print("  ✓ Created view: yoy_growth")
    except Exception as e:
        print(f"  ⊘ Could not create yoy_growth: {str(e)[:50]}")

    # View 3: Multi-year organizational summary
    try:
        con.execute("""
            CREATE VIEW IF NOT EXISTS org_multi_year_summary AS
            SELECT
                ein,
                COUNT(DISTINCT tax_year) as years_present,
                MIN(tax_year) as first_year,
                MAX(tax_year) as last_year,
                AVG(CAST(f9_p8_total_revenue AS INTEGER)) as avg_revenue,
                SUM(CAST(f9_p8_total_revenue AS INTEGER)) as total_revenue_all_years
            FROM f9_p08_t00_revenue
            WHERE f9_p8_total_revenue IS NOT NULL
            GROUP BY ein;
        """)
        print("  ✓ Created view: org_multi_year_summary")
    except Exception as e:
        print(f"  ⊘ Could not create org_multi_year_summary: {str(e)[:50]}")

    con.commit()
    con.close()

    print("\n✓ Longitudinal analysis views created")

def demo_multi_year_extraction():
    """Demo mode - create sample multi-year data"""
    print(f"\n{'='*80}")
    print(f"DEMO MODE - Creating Sample Multi-Year Data")
    print(f"{'='*80}")

    years = [2019, 2020, 2021]

    # Sample organizations that appear across years
    orgs = [
        ('123456789', 'Community Health Services'),
        ('987654321', 'Education Foundation'),
        ('555555555', 'Arts Council')
    ]

    for year in years:
        year_dir = Path(CSV_DIR) / str(year)
        year_dir.mkdir(exist_ok=True)

        # Create header data
        header = pd.DataFrame({
            'objectid': [f'OID-{year}{ein}' for ein, _ in orgs],
            'ein': [ein for ein, _ in orgs],
            'taxpayer_name': [name for _, name in orgs],
            'tax_year': [year] * len(orgs),
            'form_type': ['990'] * len(orgs)
        })

        # Create revenue data with growth
        base_revenues = [500000, 250000, 100000]
        growth_factor = 1 + (year - 2019) * 0.1  # 10% annual growth

        revenue = pd.DataFrame({
            'objectid': [f'OID-{year}{ein}' for ein, _ in orgs],
            'ein': [ein for ein, _ in orgs],
            'tax_year': [year] * len(orgs),
            'f9_p8_total_revenue': [str(int(r * growth_factor)) for r in base_revenues],
            'f9_p8_contributions_gifts_grants': [str(int(r * 0.6 * growth_factor)) for r in base_revenues],
            'f9_p8_program_service_revenue': [str(int(r * 0.4 * growth_factor)) for r in base_revenues]
        })

        # Save files
        header.to_csv(year_dir / 'f9_p00_t00_header.csv', index=False)
        revenue.to_csv(year_dir / 'f9_p08_t00_revenue.csv', index=False)

        print(f"  ✓ Created demo data for {year}")

    # Combine years
    tables = ['F9-P00-T00-HEADER', 'F9-P08-T00-REVENUE']
    combine_year_data(years, tables)
    create_longitudinal_views(years)

    # Show sample analysis
    print(f"\n{'='*80}")
    print("SAMPLE LONGITUDINAL ANALYSIS")
    print(f"{'='*80}")

    con = sqlite3.connect(COMBINED_DB)

    print("\n1. Revenue Growth by Organization:")
    df = pd.read_sql("""
        SELECT
            ein,
            tax_year,
            f9_p8_total_revenue as revenue
        FROM f9_p08_t00_revenue
        ORDER BY ein, tax_year
    """, con)
    print(df.to_string(index=False))

    print("\n2. Year-over-Year Growth Rates:")
    try:
        df = pd.read_sql("SELECT * FROM yoy_growth ORDER BY ein, tax_year", con)
        print(df.to_string(index=False))
    except:
        print("  (View not available)")

    con.close()

def main():
    parser = argparse.ArgumentParser(description='Multi-Year IRS 990 Data Extraction')
    parser.add_argument('--years', nargs='+', type=int, help='Years to extract (e.g., 2019 2020 2021)')
    parser.add_argument('--tables', nargs='+', help='Specific tables to extract (default: all)')
    parser.add_argument('--sample', type=int, help='Sample size per table for testing (applies after PIVOT)')
    parser.add_argument('--demo', action='store_true', help='Run demo mode with sample data')
    parser.add_argument('--combine-only', action='store_true', help='Only combine existing data')
    parser.add_argument('--max-tables', type=int, help='Maximum number of tables to process (for testing/memory constraints)')
    parser.add_argument('--skip-existing', action='store_true', help='Skip tables that already have CSV files (recommended for resuming work!)')
    parser.add_argument('--batch-size', type=int, default=10, help='Number of tables to process before forcing garbage collection (default: 10)')

    args = parser.parse_args()

    if args.demo:
        demo_multi_year_extraction()
        return

    # Get tables to process
    if args.tables:
        tables = args.tables
    else:
        tables = get_table_list()
        # Limit to core tables for demo (if no specific max-tables is set)
        if not args.max_tables:
            tables = [t for t in tables if '-T00-' in t][:10]

    # Apply max-tables limit if specified
    if args.max_tables:
        tables = tables[:args.max_tables]
        logger.info(f"Limited to {len(tables)} tables due to --max-tables")

    print(f"\n{'='*80}")
    print(f"MULTI-YEAR IRS 990 DATA EXTRACTION")
    print(f"{'='*80}")
    print(f"Tables: {len(tables)}")
    print(f"Years: {args.years if args.years else 'Demo mode'}")
    if args.sample:
        print(f"Sample size: {args.sample} rows per table (applied after PIVOT)")
    if args.max_tables:
        print(f"Max tables: {args.max_tables} (memory-constrained mode)")
    if args.skip_existing:
        print(f"Skip existing: ENABLED (will skip tables with existing CSV files)")
    print(f"Batch size: {args.batch_size} tables (memory cleanup frequency)")
    print(f"{'='*80}")

    if not args.combine_only:
        # Extract data for each year
        if args.years:
            for year in args.years:
                extract_year_data(year, tables, args.sample,
                                skip_existing=args.skip_existing,
                                batch_size=args.batch_size)
        else:
            print("\nNo years specified. Use --years 2019 2020 2021 or --demo")
            return

    # Combine years
    if args.years and len(args.years) > 1:
        combine_year_data(args.years, tables)
        analyze_multi_year_coverage(args.years, tables)
        create_longitudinal_views(args.years)

if __name__ == "__main__":
    main()
