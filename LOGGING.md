# Logging Guide

Comprehensive logging implementation for EF2 data extraction and validation.

## Quick Start

All scripts now include detailed logging with both console and file output.

### Basic Usage

```bash
# Run with default INFO level logging
python3 extract_multi_year.py --demo

# View logs
tail -f logs/extract_multi_year_20241115.log
```

### Log Levels

Set log level via environment variable or code:

```bash
# Set log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
export EF2_LOG_LEVEL=DEBUG
python3 extract_multi_year.py --demo

# Or in code
logger = setup_logging("my_script", level="DEBUG")
```

## Features

### 1. Dual Output
- **Console**: Clean, formatted output for user
- **File**: Detailed logs with timestamps, line numbers, function names

### 2. Log Rotation
- Automatic rotation when logs reach 10 MB
- Keeps 5 backup files
- Daily log files with date stamp

### 3. Performance Tracking
- Function execution times logged automatically
- Use `@log_performance` decorator

### 4. Structured Logging
- Consistent format across all scripts
- Easy to parse and analyze
- Includes context (function, line number)

## Log Locations

```
logs/
├── extract_multi_year_20241115.log
├── extract_all_tables_20241115.log
├── validate_data_20241115.log
└── test_database_20241115.log
```

## Log Format

### Console Output
```
12:34:56 - INFO - Processing Year: 2021
12:34:57 - INFO - Attached S3 database: EFILE2021
12:35:02 - INFO - Completed extract_year_data in 5.23s
```

### File Output
```
2024-11-15 12:34:56 - extract_multi_year - INFO - extract_year_data:95 - Processing Year: 2021
2024-11-15 12:34:57 - extract_multi_year - INFO - extract_year_data:118 - Attached S3 database: EFILE2021
2024-11-15 12:35:02 - extract_multi_year - INFO - log_performance:45 - Completed extract_year_data in 5.23s
```

## Usage in Code

### Setup Logging

```python
from logging_config import setup_logging, log_performance, LogBlock

# Initialize logger
logger = setup_logging("my_script", level="INFO")

# Log messages
logger.debug("Detailed debug information")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error occurred")
logger.critical("Critical error!")
```

### Performance Decorator

```python
@log_performance
def slow_function(data):
    """This function's execution time will be logged"""
    # Do work...
    return result

# Logs:
# INFO - Completed slow_function in 2.34s
```

### Log Block Context Manager

```python
with LogBlock(logger, "Processing large dataset"):
    # Code here is timed and logged
    process_data()

# Logs:
# INFO - Starting: Processing large dataset
# INFO - Completed: Processing large dataset (45.67s)
```

## Examples

### Multi-Year Extraction

```python
logger.info(f"Starting extraction for {len(years)} years")

for year in years:
    with LogBlock(logger, f"Year {year} extraction"):
        extract_year_data(year, tables)
        logger.info(f"Extracted {count} tables for {year}")

logger.info("Multi-year extraction complete")
```

**Log Output:**
```
INFO - Starting extraction for 3 years
INFO - Starting: Year 2019 extraction
INFO - Attached S3 database: EFILE2019
INFO - Extracted 10 tables for 2019
INFO - Completed: Year 2019 extraction (120.45s)
INFO - Starting: Year 2020 extraction
...
INFO - Multi-year extraction complete
```

### Data Validation

```python
logger.info("Starting data validation")

for rule in validation_rules:
    logger.debug(f"Checking rule: {rule.name}")
    result = rule.validate()

    if result.failed > 0:
        logger.warning(f"Rule {rule.name} failed: {result.failed} errors")
    else:
        logger.debug(f"Rule {rule.name} passed")

logger.info(f"Validation complete: {passed}/{total} checks passed")
```

**Log Output:**
```
INFO - Starting data validation
DEBUG - Checking rule: EIN format validation
DEBUG - Rule EIN format validation passed
DEBUG - Checking rule: Tax year range
DEBUG - Rule Tax year range passed
WARNING - Rule Revenue components sum failed: 5 errors
INFO - Validation complete: 20/22 checks passed
```

## Log Analysis

### View Recent Errors

```bash
# Show only errors from today's log
grep ERROR logs/extract_multi_year_$(date +%Y%m%d).log

# Show warnings and errors
grep -E "WARNING|ERROR" logs/extract_multi_year_$(date +%Y%m%d).log
```

### Monitor Live Logs

```bash
# Follow log in real-time
tail -f logs/extract_multi_year_$(date +%Y%m%d).log

# Follow and filter for errors
tail -f logs/extract_multi_year_$(date +%Y%m%d).log | grep --line-buffered ERROR
```

### Performance Analysis

```bash
# Find slow operations
grep "Completed.*in" logs/extract_multi_year_$(date +%Y%m%d).log | sort -t'in' -k2 -rn

# Example output:
# Completed extract_year_data in 125.45s
# Completed combine_year_data in 45.23s
# Completed setup_duckdb_s3 in 2.34s
```

### Extract Specific Information

```bash
# Show all year extractions
grep "Processing Year:" logs/extract_multi_year_$(date +%Y%m%d).log

# Show all validation failures
grep "failed:" logs/validate_data_$(date +%Y%m%d).log

# Count errors by type
grep ERROR logs/*.log | cut -d: -f3 | sort | uniq -c
```

## Integration with Scripts

### extract_multi_year.py

Logs:
- ✓ DuckDB setup and S3 connection
- ✓ Database attachment
- ✓ Table extraction (per table)
- ✓ Data combination
- ✓ View creation
- ✓ Performance metrics

Example log flow:
```
INFO - Loading concordance tables
INFO - Loaded 128 tables from concordance
INFO - Setting up DuckDB with S3 support
INFO - DuckDB S3 setup complete
INFO - Processing Year: 2021
INFO - Attached S3 database: EFILE2021
INFO - Extracting table: f9_p00_t00_header
INFO - Extracted 150 rows to CSV
INFO - Completed extract_year_data in 45.23s
INFO - Combining data across years
INFO - Combined 3 years for table: f9_p00_t00_header
INFO - Creating longitudinal analysis views
INFO - Created view: revenue_trends
```

### validate_data.py

Logs:
- ✓ Validation rule execution
- ✓ Pass/fail counts
- ✓ Detailed failure examples
- ✓ Category summaries
- ✓ Report generation

Example log flow:
```
INFO - Starting IRS 990 data validation
INFO - Database: irs990_all_tables.sqlite
INFO - Tables found: 9
INFO - Validating format rules
DEBUG - Checking EIN format for f9_p00_t00_header
INFO - EIN format: 150 passed, 0 failed
INFO - Validating completeness rules
INFO - objectid completeness: 150 passed, 0 failed
WARNING - Revenue components sum: 5 failed
DEBUG - Example: EIN 123456789 sum mismatch
INFO - Validation report saved to validation_report.json
INFO - Validation passed with 2 warnings
```

### test_database.py

Logs:
- ✓ Test execution
- ✓ Join testing
- ✓ Referential integrity checks
- ✓ Performance metrics

## Troubleshooting

### Issue: Logs not appearing

**Check:**
1. `logs/` directory exists
2. Permissions are correct
3. Log level is appropriate

```bash
# Create logs directory
mkdir -p logs
chmod 755 logs

# Set debug level temporarily
export EF2_LOG_LEVEL=DEBUG
python3 your_script.py
```

### Issue: Logs too verbose

**Solution:** Adjust log level

```bash
# Use INFO for normal operation
export EF2_LOG_LEVEL=INFO

# Use WARNING for quiet operation
export EF2_LOG_LEVEL=WARNING
```

### Issue: Log files too large

**Solution:** Logs auto-rotate at 10 MB. To adjust:

```python
logger = setup_logging(
    "my_script",
    max_bytes=5*1024*1024,  # 5 MB
    backup_count=3           # Keep 3 backups
)
```

## Best Practices

### 1. Use Appropriate Log Levels

- **DEBUG**: Detailed diagnostic info
  ```python
  logger.debug(f"Query: {sql_query}")
  logger.debug(f"Processing row {i} of {total}")
  ```

- **INFO**: General informational messages
  ```python
  logger.info("Starting data extraction")
  logger.info(f"Processed {count} records")
  ```

- **WARNING**: Warning messages (non-critical)
  ```python
  logger.warning("Table not found, skipping")
  logger.warning(f"Low data quality: {score}%")
  ```

- **ERROR**: Error messages
  ```python
  logger.error(f"Failed to connect: {error}")
  logger.error("Database query failed")
  ```

- **CRITICAL**: Critical errors
  ```python
  logger.critical("Data corruption detected!")
  logger.critical("System out of memory")
  ```

### 2. Include Context

```python
# Good - includes context
logger.info(f"Extracted {row_count} rows from {table_name}")

# Bad - lacking context
logger.info("Extraction complete")
```

### 3. Log Exceptions Properly

```python
try:
    process_data()
except Exception as e:
    logger.error(f"Processing failed: {e}", exc_info=True)
    # exc_info=True includes full traceback
```

### 4. Use Performance Decorators

```python
# Automatically logs execution time
@log_performance
def expensive_operation():
    # Implementation
    pass
```

### 5. Structure Multi-Step Operations

```python
with LogBlock(logger, "Multi-step operation"):
    step_1()
    step_2()
    step_3()
# Automatically logs start and completion with timing
```

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Run Extraction with Logging
  run: |
    python3 extract_multi_year.py --years 2021

- name: Upload Logs
  if: always()
  uses: actions/upload-artifact@v2
  with:
    name: extraction-logs
    path: logs/

- name: Check for Errors
  run: |
    if grep -q ERROR logs/*.log; then
      echo "Errors found in logs"
      grep ERROR logs/*.log
      exit 1
    fi
```

### Log Monitoring

```bash
# Send errors to monitoring system
grep ERROR logs/*.log | while read line; do
    curl -X POST https://monitoring.example.com/logs \
      -H "Content-Type: application/json" \
      -d "{\"message\": \"$line\"}"
done
```

## Configuration File

Create `logging.conf` for advanced configuration:

```ini
[loggers]
keys=root,extract,validate

[handlers]
keys=console,file

[formatters]
keys=simple,detailed

[logger_root]
level=INFO
handlers=console,file

[logger_extract]
level=DEBUG
handlers=file
qualname=extract_multi_year

[logger_validate]
level=INFO
handlers=console,file
qualname=validate_data

[handler_console]
class=StreamHandler
level=INFO
formatter=simple
args=(sys.stdout,)

[handler_file]
class=handlers.RotatingFileHandler
level=DEBUG
formatter=detailed
args=('logs/app.log', 'a', 10*1024*1024, 5)

[formatter_simple]
format=%(asctime)s - %(levelname)s - %(message)s

[formatter_detailed]
format=%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s
```

## Summary

All scripts now include:
- ✅ Comprehensive logging
- ✅ Performance tracking
- ✅ File and console output
- ✅ Log rotation
- ✅ Structured formatting
- ✅ Easy debugging
- ✅ Production-ready

For more information, see `logging_config.py` source code.
