# Advanced Features Guide

Comprehensive guide for multi-year analysis and data validation features.

## Table of Contents

1. [Multi-Year Extraction](#multi-year-extraction)
2. [Longitudinal Analysis](#longitudinal-analysis)
3. [Data Validation](#data-validation)
4. [Complete Workflow](#complete-workflow)

---

## Multi-Year Extraction

Extract and combine IRS 990 data across multiple tax years for longitudinal analysis.

### Quick Start

```bash
# Demo mode - creates sample multi-year data
python3 extract_multi_year.py --demo

# Extract specific years (requires S3 access)
python3 extract_multi_year.py --years 2019 2020 2021

# Extract with sampling (for testing)
python3 extract_multi_year.py --years 2021 --sample 1000
```

### Features

✅ **Multi-Year Extraction**
- Process multiple years in one command
- Automatic data organization by year
- Parallel processing support

✅ **Data Combination**
- Combines data across years into single database
- Creates unified views for analysis
- Maintains year-specific CSVs

✅ **Longitudinal Views**
- Revenue trends over time
- Year-over-year growth calculations
- Multi-year organizational summaries

✅ **Coverage Analysis**
- Reports data availability by year
- Identifies gaps in filing history
- Table-level statistics

### Output Structure

```
csv_multi_year/
├── 2019/
│   ├── f9_p00_t00_header.csv
│   ├── f9_p08_t00_revenue.csv
│   └── ...
├── 2020/
│   ├── f9_p00_t00_header.csv
│   ├── f9_p08_t00_revenue.csv
│   └── ...
└── 2021/
    ├── f9_p00_t00_header.csv
    ├── f9_p08_t00_revenue.csv
    └── ...

irs990_combined_years.sqlite  # Combined database with all years
```

### Usage Examples

#### Extract Multiple Years

```bash
# Extract 3 years of data
python3 extract_multi_year.py --years 2019 2020 2021

# Extract with table filter
python3 extract_multi_year.py --years 2021 --tables F9-P08-T00-REVENUE F9-P09-T00-EXPENSES

# Sample data for quick testing
python3 extract_multi_year.py --years 2021 --sample 100
```

#### Combine Existing Data

```bash
# Only combine, don't re-extract
python3 extract_multi_year.py --years 2019 2020 2021 --combine-only
```

---

## Longitudinal Analysis

Analyze trends and changes across multiple years.

### Built-in Views

The combined database includes SQL views for common analyses:

#### 1. Revenue Trends

```sql
SELECT * FROM revenue_trends
WHERE ein = '123456789'
ORDER BY tax_year;
```

Shows revenue components over time for each organization.

#### 2. Year-over-Year Growth

```sql
SELECT * FROM yoy_growth
WHERE growth_rate > 10
ORDER BY growth_rate DESC;
```

Calculates growth rates between consecutive years.

#### 3. Multi-Year Summary

```sql
SELECT * FROM org_multi_year_summary
WHERE years_present >= 3
ORDER BY avg_revenue DESC;
```

Aggregates organization data across all years present.

### Python Analysis Examples

```python
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

# Connect to combined database
con = sqlite3.connect('irs990_combined_years.sqlite')

# 1. Revenue growth by organization
query = """
    SELECT
        taxpayer_name,
        tax_year,
        CAST(f9_p8_total_revenue AS INTEGER) as revenue
    FROM f9_p00_t00_header h
    JOIN f9_p08_t00_revenue r ON h.objectid = r.objectid
    WHERE taxpayer_name = 'Community Health Services'
    ORDER BY tax_year
"""
df = pd.read_sql(query, con)

# Plot revenue trend
df.plot(x='tax_year', y='revenue', kind='line')
plt.title('Revenue Trend')
plt.show()

# 2. Sector-wide analysis
query = """
    SELECT
        tax_year,
        COUNT(*) as num_orgs,
        AVG(CAST(f9_p8_total_revenue AS INTEGER)) as avg_revenue,
        SUM(CAST(f9_p8_total_revenue AS INTEGER)) as total_revenue
    FROM f9_p08_t00_revenue
    GROUP BY tax_year
    ORDER BY tax_year
"""
sector_df = pd.read_sql(query, con)
print(sector_df)

# 3. Identify organizations with consistent growth
query = """
    SELECT
        ein,
        taxpayer_name,
        years_present,
        avg_revenue,
        total_revenue_all_years
    FROM f9_p00_t00_header h
    JOIN org_multi_year_summary s ON h.ein = s.ein
    WHERE years_present >= 3
        AND avg_revenue > 1000000
    ORDER BY avg_revenue DESC
    LIMIT 10
"""
top_orgs = pd.read_sql(query, con)
print(top_orgs)

con.close()
```

### R Analysis Examples

```r
library(DBI)
library(RSQLite)
library(dplyr)
library(ggplot2)

# Connect to database
con <- dbConnect(RSQLite::SQLite(), "irs990_combined_years.sqlite")

# Get revenue trends
revenue_trends <- tbl(con, "revenue_trends") %>%
  filter(!is.na(total_revenue)) %>%
  collect()

# Plot growth over time
ggplot(revenue_trends, aes(x = tax_year, y = total_revenue, group = ein)) +
  geom_line() +
  facet_wrap(~ ein) +
  theme_minimal() +
  labs(title = "Revenue Trends by Organization",
       x = "Tax Year",
       y = "Total Revenue")

# Year-over-year growth analysis
growth <- tbl(con, "yoy_growth") %>%
  filter(!is.na(growth_rate)) %>%
  collect()

# Distribution of growth rates
ggplot(growth, aes(x = growth_rate)) +
  geom_histogram(bins = 30) +
  theme_minimal() +
  labs(title = "Distribution of Year-over-Year Growth Rates",
       x = "Growth Rate (%)",
       y = "Count")

dbDisconnect(con)
```

---

## Data Validation

Comprehensive validation of extracted data quality.

### Quick Start

```bash
# Validate current database
python3 validate_data.py

# Exit code: 0 = passed, 1 = failed
echo $?
```

### Validation Categories

#### 1. Format Validation

- **EIN Format**: Validates 9-digit EIN format
- **Tax Year Range**: Ensures years are 2007-2024
- **Numeric Fields**: Checks numeric columns are convertible

#### 2. Completeness Validation

- **Required Fields**: Validates key columns are not NULL
  - objectid
  - ein
  - tax_year

#### 3. Business Logic Validation

- **Non-Negative Revenue**: Revenue amounts must be >= 0
- **Component Sums**: Revenue components should sum to total (±1% tolerance)
- **Expense Logic**: Expenses <= Revenue (warning if violated)

#### 4. Cross-Table Consistency

- **Revenue Match**: Summary revenue matches detail revenue
- **Tax Year Match**: Tax years match across joined tables
- **EIN Consistency**: EINs match across related records

#### 5. Outlier Detection

- **Z-Score Method**: Identifies statistical outliers (>3 std deviations)
- **Revenue Outliers**: Flags unusually high/low revenues
- **Expense Outliers**: Flags unusual expense patterns

#### 6. Temporal Consistency

- **Filing Gaps**: Identifies organizations skipping years
- **Trend Anomalies**: Detects unusual year-over-year changes
- **Historical Patterns**: Validates multi-year filing patterns

### Validation Output

```
================================================================================
IRS 990 DATA VALIDATION
================================================================================

Overall Statistics:
  Total checks: 1,247
  Passed: 1,235 (99.0%)
  Failed: 12 (1.0%)

Issues by Severity:
  Errors: 0
  Warnings: 12
  Info: 0

⚠️  WARNINGS:

  Business Logic - Revenue: Components sum to total
    Failed: 5 / 150
    Example: EIN 123456789: Total=875,000, Components=874,850, Diff=150

  Data Quality - f9_p08_t00_revenue: f9_p8_total_revenue outliers
    Failed: 7 / 150
    Example: EIN 987654321: f9_p8_total_revenue=50,000,000 (z-score=4.23)

✓ Detailed report saved to: validation_report.json

⚠️  VALIDATION PASSED WITH WARNINGS - 12 warnings found
```

### Validation Report (JSON)

```json
{
  "timestamp": "2024-11-15T19:45:00",
  "summary": {
    "total_checks": 1247,
    "passed": 1235,
    "failed": 12,
    "error_count": 0,
    "warning_count": 12
  },
  "rules": [
    {
      "category": "Format",
      "rule": "f9_p00_t00_header: EIN format",
      "severity": "ERROR",
      "passed": 150,
      "failed": 0,
      "pass_rate": "100.0%",
      "details": []
    }
  ],
  "categories": {
    "Format": {"passed": 300, "failed": 0},
    "Business Logic": {"passed": 445, "failed": 5},
    "Consistency": {"passed": 290, "failed": 0}
  }
}
```

### Custom Validation Rules

Add custom rules to `validate_data.py`:

```python
def validate_custom_rule(con: sqlite3.Connection) -> ValidationRule:
    """Custom validation rule"""
    rule = ValidationRule("Custom", "My custom check", "ERROR")

    query = """
        SELECT * FROM my_table
        WHERE my_condition
    """

    df = pd.read_sql(query, con)

    for _, row in df.iterrows():
        if row['value'] > threshold:
            rule.add_pass()
        else:
            rule.add_failure(f"Failed: {row['id']}")

    return rule
```

---

## Complete Workflow

### 1. Extract Multi-Year Data

```bash
# Extract 3 years
python3 extract_multi_year.py --years 2019 2020 2021

# Or use demo mode
python3 extract_multi_year.py --demo
```

**Output:**
- `csv_multi_year/YEAR/` - CSV files by year
- `irs990_combined_years.sqlite` - Combined database
- Longitudinal analysis views

### 2. Validate Data Quality

```bash
# Validate combined database
python3 validate_data.py

# Check exit code
if [ $? -eq 0 ]; then
    echo "Validation passed - data is clean"
else
    echo "Validation failed - review errors"
fi
```

**Output:**
- Console report with issues
- `validation_report.json` - Detailed findings

### 3. Analyze Trends

```python
import sqlite3
import pandas as pd

con = sqlite3.connect('irs990_combined_years.sqlite')

# Organizations with 3+ years of data
orgs = pd.read_sql("""
    SELECT * FROM org_multi_year_summary
    WHERE years_present >= 3
    ORDER BY avg_revenue DESC
    LIMIT 20
""", con)

# Revenue growth trends
growth = pd.read_sql("""
    SELECT
        ein,
        tax_year,
        growth_rate
    FROM yoy_growth
    WHERE growth_rate BETWEEN -50 AND 200
    ORDER BY ein, tax_year
""", con)

# Sector aggregates
sector = pd.read_sql("""
    SELECT
        tax_year,
        COUNT(DISTINCT ein) as num_orgs,
        AVG(total_revenue) as avg_revenue,
        SUM(total_revenue) as sector_total
    FROM revenue_trends
    GROUP BY tax_year
    ORDER BY tax_year
""", con)

con.close()
```

### 4. Export for Further Analysis

```bash
# Export specific table to CSV
sqlite3 irs990_combined_years.sqlite \
  ".headers on" \
  ".mode csv" \
  ".output revenue_all_years.csv" \
  "SELECT * FROM f9_p08_t00_revenue;"

# Export view
sqlite3 irs990_combined_years.sqlite \
  ".headers on" \
  ".mode csv" \
  ".output growth_rates.csv" \
  "SELECT * FROM yoy_growth;"
```

---

## Performance Tips

### For Large Datasets

1. **Use Sampling**
   ```bash
   python3 extract_multi_year.py --years 2021 --sample 10000
   ```

2. **Filter Tables**
   ```bash
   python3 extract_multi_year.py --years 2021 \
     --tables F9-P08-T00-REVENUE F9-P09-T00-EXPENSES
   ```

3. **Process Years Separately**
   ```bash
   # Extract years one at a time
   for year in 2019 2020 2021; do
       python3 extract_multi_year.py --years $year
   done

   # Then combine
   python3 extract_multi_year.py --years 2019 2020 2021 --combine-only
   ```

### Memory Optimization

- Multi-year extraction processes one table at a time
- Uses DuckDB's COPY for direct CSV writing
- Automatic garbage collection after each table
- Typically uses <2 GB RAM even for large datasets

---

## Integration Examples

### CI/CD Pipeline

```yaml
# .github/workflows/data-quality.yml
name: Data Quality Check

on:
  schedule:
    - cron: '0 2 * * 0'  # Weekly on Sunday

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Extract Latest Year
        run: |
          python3 extract_multi_year.py --years 2021 --sample 1000

      - name: Validate Data
        run: |
          python3 validate_data.py

      - name: Upload Report
        uses: actions/upload-artifact@v2
        with:
          name: validation-report
          path: validation_report.json
```

### Automated Reporting

```python
# scheduled_report.py
import subprocess
import json
from datetime import datetime

# Extract latest data
subprocess.run([
    'python3', 'extract_multi_year.py',
    '--years', '2020', '2021',
    '--sample', '5000'
])

# Validate
result = subprocess.run(['python3', 'validate_data.py'])

# Load validation report
with open('validation_report.json') as f:
    report = json.load(f)

# Email report
if report['summary']['error_count'] > 0:
    send_alert_email(report)
else:
    send_summary_email(report)
```

---

## Troubleshooting

### Multi-Year Extraction Issues

**Problem:** "Cannot attach S3 database"
- **Solution:** Check network connectivity and S3 bucket access

**Problem:** "FLATXML table not found"
- **Solution:** Database may use different naming. Check with demo mode first.

**Problem:** "Out of memory"
- **Solution:** Use `--sample` to limit rows, or process years separately

### Validation Issues

**Problem:** "Many format errors"
- **Solution:** Review data source quality. May indicate extraction issues.

**Problem:** "Revenue components don't sum"
- **Solution:** This is a WARNING, not ERROR. Small differences (<1%) are acceptable.

**Problem:** "Temporal gaps detected"
- **Solution:** Organizations don't file every year. This is expected behavior.

---

## Files Reference

| File | Purpose | Output |
|------|---------|--------|
| `extract_multi_year.py` | Multi-year extraction | Combined DB + CSVs by year |
| `validate_data.py` | Data quality checks | Validation report (JSON + console) |
| `irs990_combined_years.sqlite` | Combined database | All years in one DB |
| `validation_report.json` | Validation results | Detailed findings |
| `csv_multi_year/` | Year-specific CSVs | Original extracts by year |

---

## Next Steps

1. **Extract Your Data**
   ```bash
   python3 extract_multi_year.py --demo  # Start with demo
   python3 extract_multi_year.py --years 2021  # Then real data
   ```

2. **Validate Quality**
   ```bash
   python3 validate_data.py
   cat validation_report.json
   ```

3. **Analyze Trends**
   - Use built-in SQL views
   - Export to pandas/R for visualization
   - Create custom analyses

4. **Automate**
   - Set up scheduled extractions
   - Integrate validation into CI/CD
   - Create automated reports

---

**Questions?** See main README or test scripts for more examples.
