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
from pathlib import Path
from typing import List, Dict
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from datetime import datetime
import logging
from logging_config import setup_logging, log_performance, LogBlock

# Setup logger
logger = setup_logging("extract_multi_year", level="INFO")

# Configuration
S3_BUCKET = "nccs-efile"
CSV_DIR = "csv_multi_year"
SQLITE_DIR = "sqlite_multi_year"
COMBINED_DB = "irs990_combined_years.sqlite"

# Create output directories
Path(CSV_DIR).mkdir(exist_ok=True)
Path(SQLITE_DIR).mkdir(exist_ok=True)

def to_snake_case(text: str) -> str:
    """Convert text to snake_case"""
    text = text.replace('-', '_').replace(' ', '_')
    text = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', text)
    text = re.sub('([a-z0-9])([A-Z])', r'\1_\2', text)
    return text.lower()

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
def extract_year_data(year: int, tables: List[str], sample_size: int = None) -> Dict:
    """Extract data for a single year"""
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

    # Attach S3 database
    s3_path = f"s3://{S3_BUCKET}/duckdb/EFILE{year}.duckdb"
    dbname = f"EFILE{year}"

    try:
        con.execute(f"ATTACH '{s3_path}' AS {dbname};")
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

    for table_name in tables:
        snake_name = to_snake_case(table_name)
        csv_file = year_dir / f"{snake_name}.csv"

        try:
            # Build query with optional sampling
            limit_clause = f"LIMIT {sample_size}" if sample_size else ""

            query = f"""
            COPY (
                SELECT * FROM (
                    PIVOT (
                        SELECT OBJECTID, VARIABLE_NAME, VALUE
                        FROM {flatxml_table}
                        WHERE RDB_TABLE = '{table_name}'
                        AND TYPE = 'terminal'
                        {limit_clause}
                    )
                    ON VARIABLE_NAME
                    USING FIRST(VALUE)
                )
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
            # print(f"    ✗ {snake_name}: {str(e)[:80]}")

    con.close()

    print(f"\n  Summary for {year}:")
    print(f"    Extracted: {results['tables_extracted']} tables")
    print(f"    Failed: {results['tables_failed']} tables")
    print(f"    Total rows: {results['total_rows']:,}")

    return results

def combine_year_data(years: List[int], tables: List[str]):
    """Combine data across years into single database"""
    print(f"\n{'='*80}")
    print(f"COMBINING DATA ACROSS YEARS: {min(years)}-{max(years)}")
    print(f"{'='*80}")

    con = sqlite3.connect(COMBINED_DB)

    for table_name in tables:
        snake_name = to_snake_case(table_name)
        print(f"\n  Combining: {snake_name}")

        combined_data = []
        years_found = []

        for year in years:
            csv_file = Path(CSV_DIR) / str(year) / f"{snake_name}.csv"

            if csv_file.exists():
                try:
                    df = pd.read_csv(csv_file)
                    # Convert column names to snake_case
                    df.columns = [to_snake_case(col) for col in df.columns]
                    # Add year column if not present
                    if 'tax_year' not in df.columns:
                        df['tax_year'] = year
                    combined_data.append(df)
                    years_found.append(year)
                except Exception as e:
                    print(f"    ✗ Error reading {year}: {str(e)[:50]}")

        if combined_data:
            # Combine all years
            combined_df = pd.concat(combined_data, ignore_index=True)

            # Write to database
            combined_df.to_sql(snake_name, con, if_exists='replace', index=False)

            # Create indexes
            try:
                con.execute(f"CREATE INDEX IF NOT EXISTS idx_{snake_name}_objectid ON {snake_name}(objectid);")
                con.execute(f"CREATE INDEX IF NOT EXISTS idx_{snake_name}_tax_year ON {snake_name}(tax_year);")
                if 'ein' in combined_df.columns:
                    con.execute(f"CREATE INDEX IF NOT EXISTS idx_{snake_name}_ein ON {snake_name}(ein);")
            except:
                pass

            print(f"    ✓ Combined {len(combined_data)} years: {years_found}")
            print(f"    ✓ Total rows: {len(combined_df):,}")
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
    parser.add_argument('--sample', type=int, help='Sample size per table for testing')
    parser.add_argument('--demo', action='store_true', help='Run demo mode with sample data')
    parser.add_argument('--combine-only', action='store_true', help='Only combine existing data')

    args = parser.parse_args()

    if args.demo:
        demo_multi_year_extraction()
        return

    # Get tables to process
    if args.tables:
        tables = args.tables
    else:
        tables = get_table_list()
        # Limit to core tables for demo
        tables = [t for t in tables if '-T00-' in t][:10]

    print(f"\n{'='*80}")
    print(f"MULTI-YEAR IRS 990 DATA EXTRACTION")
    print(f"{'='*80}")
    print(f"Tables: {len(tables)}")
    print(f"Years: {args.years if args.years else 'Demo mode'}")
    if args.sample:
        print(f"Sample size: {args.sample} rows per table")
    print(f"{'='*80}")

    if not args.combine_only:
        # Extract data for each year
        if args.years:
            for year in args.years:
                extract_year_data(year, tables, args.sample)
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
