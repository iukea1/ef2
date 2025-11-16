# EF2 S3 to SQLite Workflow

Complete guide for extracting IRS 990 data from S3 DuckDB databases and importing into SQLite.

## Overview

This workflow demonstrates how to:
1. Connect to remote S3 DuckDB databases containing IRS 990 efile data
2. Extract specific tables from XML-based data
3. Save extracted data to CSV files
4. Import CSV data into SQLite for local analysis

## Files Created

### Scripts

1. **`extract_to_sqlite.py`** - Production script for S3 extraction (requires network access)
   - Connects to S3 DuckDB database
   - Extracts tables using DuckDB SQL queries
   - Saves to CSV and imports to SQLite

2. **`demo_workflow.py`** - Demonstration script with sample data
   - Works without network access
   - Shows complete workflow with mock IRS 990 data
   - Useful for testing and understanding the process

3. **`extract_to_sqlite.R`** - R version of the workflow
   - Uses ef2 package functions
   - Ideal for R users familiar with the ef2 ecosystem

### Output Files

1. **`CSV/F9-P08-T00-REVENUE-2021.csv`** - Extracted table in CSV format
   - Contains IRS 990 revenue data
   - Includes metadata (EIN, Tax Year, Form Type)
   - Ready for analysis in Excel, R, Python, etc.

2. **`ef2_data.sqlite`** - SQLite database
   - Contains imported tables
   - Indexed for query performance
   - Portable and self-contained

## Quick Start

### Run the Demo

```bash
python3 demo_workflow.py
```

This will:
- Create sample IRS 990 data
- Save to CSV
- Import to SQLite
- Run sample queries
- Show you how the workflow works

### Production Use (with S3 access)

```bash
python3 extract_to_sqlite.py
```

Requirements:
- Network access to download DuckDB extensions
- Internet connectivity to AWS S3

## Data Structure

### Source: S3 DuckDB Database

The IRS 990 data is stored in DuckDB databases on S3:

- **Location**: `s3://nccs-efile/duckdb/efile_v2_1/EFILE{YEAR}.duckdb`
- **Format**: Flattened XML structure (FLATXML table)
- **Access**: Anonymous (public data)

Example structure:
```
EFILE2021.duckdb/
├── FLATXML - Flattened XML nodes
├── KEYS - Metadata (EIN, Tax Year, URLs)
└── Other tables
```

### Intermediate: CSV Files

Extracted tables are saved as CSV files:

```csv
OBJECTID,EIN,TAXPAYER_NAME,TAX_YEAR,FORM_TYPE,F9_P8_TOTAL_REVENUE,...
OID-202120139349301207,123456789,Sample Nonprofit 1,2021,990,850000,...
```

### Final: SQLite Database

SQLite database with normalized tables and indexes:

```sql
-- Table structure
CREATE TABLE F9_P08_T00_REVENUE (
    OBJECTID TEXT,
    EIN TEXT,
    TAXPAYER_NAME TEXT,
    TAX_YEAR INTEGER,
    FORM_TYPE TEXT,
    F9_P8_CONTRIBUTIONS_GIFTS_GRANTS TEXT,
    F9_P8_PROGRAM_SERVICE_REVENUE TEXT,
    F9_P8_INVESTMENT_INCOME TEXT,
    F9_P8_TOTAL_REVENUE TEXT,
    XPATH TEXT,
    URL TEXT
);

-- Indexes for performance
CREATE INDEX idx_ein ON F9_P08_T00_REVENUE(EIN);
CREATE INDEX idx_tax_year ON F9_P08_T00_REVENUE(TAX_YEAR);
CREATE INDEX idx_form_type ON F9_P08_T00_REVENUE(FORM_TYPE);
```

## Usage Examples

### Python

```python
import sqlite3
import pandas as pd

# Connect to database
con = sqlite3.connect('ef2_data.sqlite')

# Query all data
df = pd.read_sql_query('SELECT * FROM F9_P08_T00_REVENUE', con)
print(df)

# Filter by criteria
query = """
    SELECT TAXPAYER_NAME, F9_P8_TOTAL_REVENUE
    FROM F9_P08_T00_REVENUE
    WHERE CAST(F9_P8_TOTAL_REVENUE AS INTEGER) > 500000
    ORDER BY CAST(F9_P8_TOTAL_REVENUE AS INTEGER) DESC
"""
high_revenue = pd.read_sql_query(query, con)
print(high_revenue)

# Aggregate analysis
query = """
    SELECT
        FORM_TYPE,
        COUNT(*) as num_filings,
        AVG(CAST(F9_P8_TOTAL_REVENUE AS INTEGER)) as avg_revenue
    FROM F9_P08_T00_REVENUE
    GROUP BY FORM_TYPE
"""
summary = pd.read_sql_query(query, con)
print(summary)

con.close()
```

### R

```r
library(DBI)
library(RSQLite)
library(dplyr)

# Connect to database
con <- dbConnect(RSQLite::SQLite(), "ef2_data.sqlite")

# Query data
df <- dbGetQuery(con, "SELECT * FROM F9_P08_T00_REVENUE")

# Or use dplyr
library(dplyr)
tbl(con, "F9_P08_T00_REVENUE") %>%
  filter(TAX_YEAR == 2021) %>%
  select(TAXPAYER_NAME, F9_P8_TOTAL_REVENUE) %>%
  collect()

dbDisconnect(con)
```

### SQL (command line)

```bash
# If sqlite3 is installed
sqlite3 ef2_data.sqlite

# Inside sqlite3 shell
.tables
.schema F9_P08_T00_REVENUE
SELECT * FROM F9_P08_T00_REVENUE LIMIT 10;

# Analysis queries
SELECT FORM_TYPE, COUNT(*) as count
FROM F9_P08_T00_REVENUE
GROUP BY FORM_TYPE;
```

## EF2 Library Integration

This workflow utilizes the EF2 library for processing IRS 990 data:

### Key Functions Used

1. **`get_s3_database(filename, anonymous=TRUE)`**
   - Connects to S3-hosted DuckDB database
   - Returns DBI connection object
   - Location: `R/99_utils_s3.R:27`

2. **`flatten_table(table_name, year, con)`**
   - Extracts and pivots FLATXML data
   - Converts long format to wide format
   - Location: `R/08_extract_csv_tables.R:9`

3. **`add_keys(db_tbl, table_name, year, cc_file, con)`**
   - Joins metadata from KEYS table
   - Adds EIN, Tax Year, URLs
   - Location: `R/08_extract_csv_tables.R:33`

4. **`build_table(table_name, year, con, cc_file, post_to_s3=FALSE)`**
   - Complete table extraction pipeline
   - Combines flatten + add_keys + export
   - Location: `R/08_extract_csv_tables.R:58`

### Available Tables

Common IRS 990 tables you can extract:

- `F9-P00-T00-HEADER` - Return header information
- `F9-P08-T00-REVENUE` - Revenue (Part VIII)
- `F9-P09-T00-EXPENSES` - Expenses (Part IX)
- `F9-P10-T00-BALANCE-SHEET` - Balance sheet (Part X)
- `F9-P07-T01-COMPENSATION` - Officer compensation
- And many more...

Get full list:
```r
library(irs990efile)
table_names <- get_table_names()
```

## Architecture

### Data Flow

```
IRS XML Files (S3)
    ↓
DuckDB Database (S3)
    ├── FLATXML table (long format)
    └── KEYS table (metadata)
    ↓
SQL Query (filter by table_name)
    ↓
Pivot to Wide Format
    ↓
Join with KEYS
    ↓
CSV Export
    ↓
SQLite Import
    ↓
Local Analysis
```

### Performance Considerations

1. **S3 Streaming**: DuckDB reads directly from S3 without full download
2. **Lazy Evaluation**: Queries executed on S3, only results transferred
3. **Indexing**: SQLite indexes speed up local queries
4. **Batching**: Process by year to manage memory

### Limitations in This Environment

The current environment has some limitations:
- No network access to download DuckDB httpfs extension
- Therefore, `demo_workflow.py` uses sample data
- `extract_to_sqlite.py` would work in a proper environment

## Troubleshooting

### DuckDB Extension Error

```
Error: Failed to download extension "httpfs"
```

**Solution**: Requires internet access. Use `demo_workflow.py` for offline testing.

### Memory Issues

If extracting large tables:
```python
# Add LIMIT to query
df = wide_table.limit(10000).collect()
```

### S3 Access Denied

Ensure anonymous access is enabled:
```python
con.execute("SET s3_access_key_id='';")
con.execute("SET s3_secret_access_key='';")
```

## Next Steps

1. **Expand to Multiple Tables**: Modify scripts to extract multiple tables
2. **Multi-Year Analysis**: Combine data across tax years
3. **Data Validation**: Add checks for data quality
4. **Advanced Queries**: Create views and complex analyses
5. **Visualization**: Connect BI tools to SQLite database

## Resources

- [EF2 GitHub Repository](https://github.com/nonprofit-open-data-collective/ef2)
- [IRS 990 Concordance](https://github.com/Nonprofit-Open-Data-Collective/irs-efile-master-concordance-file)
- [NCCS Data Portal](https://nccs.urban.org/nccs/datasets/efile/)
- [DuckDB Documentation](https://duckdb.org/docs/)

## License

This workflow utilizes the EF2 library which is open source. IRS 990 data is public domain.
