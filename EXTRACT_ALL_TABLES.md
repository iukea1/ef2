# Extract All IRS 990 Tables - Complete Guide

Comprehensive workflow for extracting all 128+ IRS 990 tables from S3 DuckDB databases to CSV and SQLite with snake_case formatting.

## Overview

This workflow extracts **all available IRS 990 tables** from the S3-hosted DuckDB databases, converting them to:
- **CSV files** with snake_case column names and filenames
- **SQLite database** with snake_case table and column names
- **Optimized for memory efficiency** - processes one table at a time to prevent RAM exhaustion

## Quick Start

### Python Version

```bash
python3 extract_all_tables.py
```

### R Version

```bash
Rscript extract_all_tables.R
```

## Features

### ✓ All Tables Extraction
- Automatically extracts all 128+ IRS 990 tables from concordance
- Includes header tables (T00) and data tables (T01-T99)
- Processes Form 990, 990-EZ, 990-PF, and all schedules

### ✓ Snake Case Formatting
- **Filenames**: `f9_p08_t00_revenue_2021.csv` (not `F9-P08-T00-REVENUE-2021.csv`)
- **Table names**: `f9_p08_t00_revenue` (not `F9-P08-T00-REVENUE`)
- **Column names**: `taxpayer_name`, `ein`, `tax_year` (not `TAXPAYER_NAME`, `EIN`, `TAX_YEAR`)

### ✓ Memory Optimization
- Processes one table at a time
- Uses DuckDB's `COPY` command to write directly to CSV
- No full data loading into memory
- Automatic garbage collection after each table
- Chunked reading for SQLite import
- **Prevents RAM exhaustion** even with large datasets

### ✓ Progress Tracking
- Real-time progress display ([15/128] Processing...)
- Success/skip/error counters
- File size reporting
- Row count tracking

### ✓ Error Handling
- Graceful handling of empty tables
- Network failure recovery
- Partial file cleanup
- Detailed error messages

## Output Structure

### CSV Files

```
csv_output/
├── f9_p00_t00_header_2021.csv
├── f9_p01_t00_summary_2021.csv
├── f9_p08_t00_revenue_2021.csv
├── f9_p09_t00_expenses_2021.csv
├── f9_p10_t00_balance_sheet_2021.csv
├── f9_p07_t01_compensation_2021.csv
├── sd_p01_t01_contributors_2021.csv
└── ... (123+ more files)
```

Each CSV file:
- Snake_case filename
- Snake_case column headers
- Proper UTF-8 encoding
- Standard CSV format (comma-delimited, quoted strings)

### SQLite Database

```
irs990_all_tables.sqlite
├── f9_p00_t00_header (123,456 rows)
├── f9_p01_t00_summary (123,456 rows)
├── f9_p08_t00_revenue (123,456 rows)
├── f9_p09_t00_expenses (123,456 rows)
└── ... (128+ tables)
```

Each table includes:
- Snake_case table name
- Snake_case column names
- Indexes on key columns (objectid, ein, tax_year, form_type)
- Optimized for query performance

## Available Tables

### Form 990 Core (990, 990-EZ, 990-PF)

**Header Tables (T00)**
- `f9_p00_t00_header` - Return header info (EIN, name, tax year)
- `f9_p01_t00_summary` - Summary financials
- `f9_p08_t00_revenue` - Revenue (Part VIII)
- `f9_p09_t00_expenses` - Expenses (Part IX)
- `f9_p10_t00_balance_sheet` - Balance sheet (Part X)
- `f9_p03_t00_mission` - Mission and programs (Part III)
- `f9_p06_t00_governance` - Governance (Part VI)

**Data Tables (T01-T99)**
- `f9_p07_t01_compensation` - Officer compensation
- `f9_p07_t02_contractors` - Independent contractors
- `f9_p03_t01_programs_other` - Additional program services

### Schedules

**Schedule A - Public Charity Status**
- `sa_p01_t00_public_support` - Public support test
- `sa_p02_t01_support_schedule` - Support schedule details

**Schedule B - Contributors**
- `sd_p01_t01_contributors` - Large contributors list

**Schedule C - Political Activities**
- `sc_p01_t00_political` - Political campaign activities

**Schedule D - Supplemental Financial**
- `sd_p01_t00_supplemental` - Supplemental financial info
- `sd_p11_t01_investments` - Investment details

**Schedule F - Foreign Activities**
- `sf_p01_t01_foreign_activities` - International activities

**Schedule H - Hospitals**
- `sh_p01_t00_hospital` - Hospital facilities

**Schedule I - Grants**
- `si_p01_t01_grants_us` - Domestic grants
- `si_p02_t01_grants_foreign` - International grants

**Schedule J - Compensation**
- `sj_p01_t01_compensation_detail` - Detailed compensation

**Schedule K - Tax-Exempt Bonds**
- `sk_p01_t01_bonds` - Bond details

**Schedule L - Transactions**
- `sl_p01_t01_transactions` - Interested person transactions

**Schedule M - Non-Cash Contributions**
- `sm_p01_t01_noncash` - Non-cash contribution details

**Schedule N - Liquidation**
- `sn_p01_t00_liquidation` - Termination/liquidation

**Schedule O - Supplemental Information**
- `so_p01_t01_supplement` - Additional narrative

**Schedule R - Related Organizations**
- `sr_p01_t01_related_orgs` - Related organization details

And many more (128+ total tables)!

## Snake Case Conversion Examples

### Filenames

| Original | Snake Case |
|----------|-----------|
| `F9-P08-T00-REVENUE` | `f9_p08_t00_revenue_2021.csv` |
| `F9-P07-T01-COMPENSATION` | `f9_p07_t01_compensation_2021.csv` |
| `SD-P01-T01-CONTRIBUTORS` | `sd_p01_t01_contributors_2021.csv` |

### Column Names

| Original | Snake Case |
|----------|-----------|
| `TAXPAYER_NAME` | `taxpayer_name` |
| `EIN` | `ein` |
| `TAX_YEAR` | `tax_year` |
| `F9_P8_TOTAL_REVENUE` | `f9_p8_total_revenue` |
| `FORM_TYPE` | `form_type` |

## Usage Examples

### Query All Revenue Data (Python)

```python
import sqlite3
import pandas as pd

con = sqlite3.connect('irs990_all_tables.sqlite')

# Get all revenue data
revenue = pd.read_sql('''
    SELECT
        ein,
        taxpayer_name,
        tax_year,
        f9_p8_total_revenue
    FROM f9_p08_t00_revenue
    WHERE CAST(f9_p8_total_revenue AS INTEGER) > 1000000
    ORDER BY CAST(f9_p8_total_revenue AS INTEGER) DESC
    LIMIT 100
''', con)

print(revenue)
con.close()
```

### Join Multiple Tables (SQL)

```sql
-- Combine header and revenue data
SELECT
    h.ein,
    h.taxpayer_name,
    h.tax_year,
    r.f9_p8_contributions_gifts_grants,
    r.f9_p8_program_service_revenue,
    r.f9_p8_total_revenue
FROM f9_p00_t00_header h
JOIN f9_p08_t00_revenue r
    ON h.objectid = r.objectid
WHERE h.form_type = '990'
    AND h.tax_year = 2021
```

### Analyze Compensation (R)

```r
library(DBI)
library(RSQLite)
library(dplyr)

con <- dbConnect(RSQLite::SQLite(), "irs990_all_tables.sqlite")

# Get compensation data
compensation <- tbl(con, "f9_p07_t01_compensation") %>%
  filter(!is.na(total_compensation)) %>%
  arrange(desc(total_compensation)) %>%
  collect()

summary(as.numeric(compensation$total_compensation))

dbDisconnect(con)
```

### Export Specific Table to Pandas

```python
import pandas as pd

# Read CSV directly
df = pd.read_csv('csv_output/f9_p08_t00_revenue_2021.csv')

# All columns are already snake_case!
print(df.columns)
# ['objectid', 'ein', 'taxpayer_name', 'tax_year', 'f9_p8_total_revenue', ...]

# Analysis
df['f9_p8_total_revenue'] = pd.to_numeric(df['f9_p8_total_revenue'], errors='coerce')
print(df['f9_p8_total_revenue'].describe())
```

## Memory Management

### How It Works

1. **One Table at a Time**: Processes tables sequentially, not all at once
2. **Direct CSV Writing**: DuckDB's `COPY` command writes directly to disk
3. **No Full Load**: Never loads entire table into Python/R memory
4. **Chunked Import**: SQLite import uses chunks (50,000 rows at a time)
5. **Garbage Collection**: Force GC after each table to free memory
6. **Stream Processing**: DuckDB streams data from S3, doesn't download entire database

### Memory Usage

Typical memory usage:
- **Small tables** (<10k rows): ~50 MB RAM
- **Medium tables** (100k rows): ~200 MB RAM
- **Large tables** (1M+ rows): ~500 MB RAM
- **Peak usage**: Generally <2 GB even for largest tables

### Configuration

Adjust batch size in code if needed:

```python
BATCH_SIZE = 50000  # Increase for more RAM, decrease for less RAM
```

```r
chunk_size = 50000  # Same for R version
```

## Performance

### Benchmarks

Processing time (approximate, depends on network speed):

| Dataset Size | Tables | Time | Output Size |
|--------------|--------|------|-------------|
| Small (2009) | 128 | ~5 min | ~500 MB |
| Medium (2015) | 128 | ~15 min | ~2 GB |
| Large (2021) | 128 | ~30 min | ~5 GB |

### Optimization Tips

1. **Process by year**: Run one year at a time
2. **Select tables**: Edit script to extract only needed tables
3. **Skip SQLite**: Comment out SQLite import if you only need CSVs
4. **Use SSD**: Write to SSD storage for faster disk I/O
5. **Parallel years**: Run multiple years in parallel (different processes)

## Troubleshooting

### "Out of Memory" Error

**Solution**: Reduce `BATCH_SIZE`

```python
BATCH_SIZE = 10000  # Instead of 50000
```

### "DuckDB httpfs extension error"

**Solution**: Network required for first-time extension download

- Ensure internet connectivity
- Run in environment with HTTP/HTTPS access
- Extension downloads once, then cached

### "Table XYZ has no data"

**Normal**: Some tables are empty for certain years

- 990-EZ filers don't have all 990 tables
- Some schedules only apply to specific org types
- Script skips empty tables automatically

### CSV Encoding Issues

**Solution**: Files are UTF-8, ensure your reader supports it

```python
pd.read_csv('file.csv', encoding='utf-8')
```

### SQLite Import Slow

**Solution**: Disable indexes during import, add later

Or skip SQLite entirely and use CSV files directly.

## Customization

### Extract Specific Tables Only

Edit the script to filter tables:

```python
# Only extract revenue and expenses
table_filter = ['F9-P08-T00-REVENUE', 'F9-P09-T00-EXPENSES']
all_tables = [t for t in all_tables if t in table_filter]
```

### Change Output Format

Modify the `COPY` command for different formats:

```python
# TSV instead of CSV
copy_sql = f"COPY (...) TO '{filename}' WITH (HEADER, DELIMITER '\t');"

# Parquet format (more compact)
copy_sql = f"COPY (...) TO '{filename}' (FORMAT PARQUET);"
```

### Process Multiple Years

```python
for year in range(2009, 2025):
    print(f"\nProcessing year {year}...")
    # Run extraction workflow
```

## File Organization

### Recommended Structure

```
project/
├── extract_all_tables.py          # Extraction script
├── extract_all_tables.R            # R version
├── table_list.txt                  # List of all tables
├── csv_output/                     # CSV files
│   ├── 2009/
│   │   ├── f9_p00_t00_header_2009.csv
│   │   └── ...
│   ├── 2021/
│   │   ├── f9_p00_t00_header_2021.csv
│   │   └── ...
├── sqlite/                         # SQLite databases
│   ├── irs990_2009.sqlite
│   ├── irs990_2021.sqlite
└── analysis/                       # Your analysis scripts
    ├── revenue_trends.py
    └── compensation_analysis.R
```

## Integration with EF2 Library

This workflow builds on EF2's functions:

### Python via DuckDB

```python
# Direct DuckDB queries (this script's approach)
con.execute("SELECT * FROM FLATXML WHERE ...")
```

### R via EF2 Functions

```r
# Using EF2 library functions
library(ef2)
con <- get_s3_database("EFILE2021.duckdb")
wide_table <- flatten_table("F9-P08-T00-REVENUE", 2021, con)
```

Both approaches work - this script optimizes for:
- Processing ALL tables automatically
- Memory efficiency
- Snake_case consistency
- Progress tracking

## Next Steps

1. **Run extraction** for your year(s) of interest
2. **Verify output** - check CSV files and SQLite database
3. **Start analysis** - query SQLite or read CSVs
4. **Join tables** - combine data across tables using `objectid`
5. **Time series** - process multiple years and track changes

## Resources

- [EF2 GitHub](https://github.com/nonprofit-open-data-collective/ef2)
- [IRS 990 Concordance](https://github.com/Nonprofit-Open-Data-Collective/irs-efile-master-concordance-file)
- [Table Schemas](https://nonprofit-open-data-collective.github.io/irs990efile/)
- [NCCS Data Portal](https://nccs.urban.org/nccs/datasets/efile/)
- [DuckDB Documentation](https://duckdb.org/docs/)
- [SQLite Documentation](https://www.sqlite.org/docs.html)

## FAQ

**Q: Why snake_case?**
A: Python and R conventions, easier to type, more readable in code

**Q: Can I use different case?**
A: Yes! Modify the `to_snake_case()` function for your preference

**Q: How much disk space needed?**
A: ~5-10 GB per year for all tables (CSV + SQLite)

**Q: Can I process multiple years?**
A: Yes! Run script multiple times with different YEAR values

**Q: What if S3 is down?**
A: Script includes demo mode with sample data for testing

**Q: Do I need AWS credentials?**
A: No! S3 bucket is public, uses anonymous access

**Q: Can I use PostgreSQL instead of SQLite?**
A: Yes! Modify `import_csv_to_sqlite()` function for PostgreSQL

**Q: How do I update data annually?**
A: Re-run script with new year when IRS releases data

---

**Made with ❤️ using the EF2 library**
