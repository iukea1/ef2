# Database Quality and Relationship Testing

Comprehensive test suite for validating IRS 990 database quality, data integrity, and relationship joins.

## Quick Start

### Create Test Data

```bash
python3 create_test_data.py
```

Creates comprehensive test database with:
- 5 organizations
- 6 related tables
- 33 total records
- One-to-one and one-to-many relationships
- Consistent objectids across tables

### Run Tests

```bash
python3 test_database.py
```

Runs 22 comprehensive tests covering:
- Database structure
- Data quality
- Relationship joins
- Referential integrity
- Snake_case compliance
- CSV file validation

## Test Categories

### 1. Database Structure Tests

✓ **Database file exists** - Verifies SQLite file is present
✓ **Database connection** - Tests connection to database
✓ **Tables exist** - Confirms tables are created
✓ **Snake_case compliance** - All tables and columns use snake_case

### 2. Data Population Tests

✓ **Tables have data** - No empty tables
✓ **Key columns exist** - objectid, ein, tax_year present
✓ **Row counts** - Reports rows per table

### 3. Data Quality Tests

✓ **No duplicate objectids** - Validates uniqueness (except one-to-many)
✓ **No NULL objectids** - Key fields populated
✓ **Valid objectid format** - Follows OID-* pattern

### 4. Relationship Join Tests

✓ **Header-Summary join** - Tests inner join on objectid
✓ **Header-Revenue join** - Validates revenue relationship
✓ **Header-Expenses join** - Validates expense relationship
✓ **Referential integrity** - Data tables reference valid header records

### 5. Data Type Validation

✓ **Numeric columns convertible** - Financial fields are numeric
✓ **Cross-table consistency** - tax_year matches across joins

### 6. Performance Tests

✓ **Indexes exist** - Confirms indexes on key columns

### 7. CSV File Validation

✓ **CSV files exist** - Output files created
✓ **CSV filenames snake_case** - Proper naming
✓ **CSV files readable** - Valid format
✓ **CSV columns snake_case** - Proper column naming

## Test Output

### Success
```
================================================================================
✓ ALL CRITICAL TESTS PASSED
================================================================================
```

### With Warnings
```
================================================================================
✓ ALL CRITICAL TESTS PASSED
⚠ 2 warnings (non-critical issues)
================================================================================
```

### Failure
```
================================================================================
✗ 3 CRITICAL TEST(S) FAILED
================================================================================
```

## Sample Test Results

```
================================================================================
IRS 990 DATABASE QUALITY AND RELATIONSHIP TESTS
================================================================================

DATABASE STRUCTURE TESTS
  ✓ Database file exists (159,744 bytes)
  ✓ Database connection
  ✓ Tables exist (9 tables)
  ✓ Snake_case compliance

DATA POPULATION TESTS
  ✓ All tables have data (39 total rows)
  ✓ Column 'objectid' exists (9/9 tables)
  ✓ Column 'ein' exists (9/9 tables)
  ✓ Column 'tax_year' exists (9/9 tables)

RELATIONSHIP JOIN TESTS
  ✓ Header-Summary join (5 rows)
  ✓ Header-Revenue join (5 rows)
  ✓ Header-Expenses join (5 rows)

TEST SUMMARY
  Total Tests: 22
  ✓ Passed:  20 (90.9%)
  ✗ Failed:  0 (0.0%)
  ⚠ Warnings: 2 (9.1%)
```

## Understanding Warnings

Warnings are non-critical issues that may be expected:

### Duplicate objectids
```
⚠ No duplicate objectids
  1 tables have duplicates
  Details: {'f9_p07_t01_compensation': 3}
```

**Expected:** One-to-many tables (like compensation) have multiple rows per organization.
**Action:** Normal for hierarchical data.

### Orphaned records
```
⚠ Referential integrity
  3 tables have orphaned records
  Details: {'old_demo_table': 2}
```

**Cause:** Old demo data without matching header records.
**Action:** Run `create_test_data.py` to recreate clean test data.

## Test Data Structure

### Created Tables

1. **f9_p00_t00_header** (5 rows)
   - Organization header information
   - Primary key: objectid

2. **f9_p08_t00_revenue** (5 rows)
   - Revenue data (Form 990 Part VIII)
   - Foreign key: objectid → header

3. **f9_p09_t00_expenses** (5 rows)
   - Expense data (Form 990 Part IX)
   - Foreign key: objectid → header

4. **f9_p10_t00_balance_sheet** (5 rows)
   - Balance sheet (Form 990 Part X)
   - Foreign key: objectid → header

5. **f9_p07_t01_compensation** (8 rows)
   - Officer compensation (one-to-many)
   - Foreign key: objectid → header
   - Multiple officers per organization

6. **f9_p01_t00_summary** (5 rows)
   - Summary financials
   - Foreign key: objectid → header

### Sample Data

```python
# Organization 1
objectid: 'OID-202120139349301207'
ein: '123456789'
name: 'Community Health Services Inc'

# Has related records in:
- revenue: $875,000 total
- expenses: $750,000 total
- balance_sheet: $585,000 net assets
- compensation: 2 officers
- summary: matching financials
```

## Testing Joins

### One-to-One Joins

```sql
SELECT h.taxpayer_name, r.f9_p8_total_revenue
FROM f9_p00_t00_header h
INNER JOIN f9_p08_t00_revenue r ON h.objectid = r.objectid;
```

Result: 5 rows (each organization has one revenue record)

### One-to-Many Joins

```sql
SELECT h.taxpayer_name, c.person_name, c.reportable_compensation
FROM f9_p00_t00_header h
INNER JOIN f9_p07_t01_compensation c ON h.objectid = c.objectid;
```

Result: 8 rows (organizations have multiple officers)

### Multi-Table Joins

```sql
SELECT
    h.taxpayer_name,
    r.f9_p8_total_revenue,
    e.f9_p9_total_expenses,
    b.f9_p10_net_assets_eoy
FROM f9_p00_t00_header h
JOIN f9_p08_t00_revenue r ON h.objectid = r.objectid
JOIN f9_p09_t00_expenses e ON h.objectid = e.objectid
JOIN f9_p10_t00_balance_sheet b ON h.objectid = b.objectid;
```

Result: 5 rows (complete financial picture per organization)

## Data Consistency Tests

### Test 1: Revenue Match
```python
# Verify summary revenue matches detail revenue
SELECT COUNT(*) FROM f9_p01_t00_summary s
JOIN f9_p08_t00_revenue r ON s.objectid = r.objectid
WHERE s.f9_p1_total_revenue != r.f9_p8_total_revenue;
```

Expected: 0 mismatches

### Test 2: Tax Year Consistency
```python
# All related records have same tax_year
SELECT h.objectid FROM f9_p00_t00_header h
JOIN f9_p08_t00_revenue r ON h.objectid = r.objectid
WHERE h.tax_year != r.tax_year;
```

Expected: 0 mismatches

### Test 3: Referential Integrity
```python
# All revenue records reference valid header
SELECT COUNT(*) FROM f9_p08_t00_revenue r
WHERE NOT EXISTS (
    SELECT 1 FROM f9_p00_t00_header h
    WHERE h.objectid = r.objectid
);
```

Expected: 0 orphaned records

## Customizing Tests

### Add Custom Tests

Edit `test_database.py` and add:

```python
def test_custom_validation(con: sqlite3.Connection, table_names: List[str]):
    """Custom test description"""
    # Your test logic
    if condition:
        log_test("Custom", "Test name", "PASS", "Success message")
    else:
        log_test("Custom", "Test name", "FAIL", "Failure message")
```

### Skip Tables

Filter tables in test functions:

```python
# Only test specific tables
test_tables = [t for t in table_names if 'revenue' in t or 'expense' in t]
```

### Adjust Thresholds

Modify warning conditions:

```python
# Warn if more than 10% NULL values
null_percent = null_count / total_count * 100
if null_percent > 10:
    log_test("Quality", "NULL threshold", "WARN", f"{null_percent:.1f}% NULL")
```

## Integration with CI/CD

### Exit Codes

- **0**: All tests passed (warnings allowed)
- **1**: One or more tests failed

### Use in Scripts

```bash
#!/bin/bash
python3 test_database.py
if [ $? -eq 0 ]; then
    echo "Tests passed - safe to deploy"
else
    echo "Tests failed - blocking deployment"
    exit 1
fi
```

### GitHub Actions

```yaml
- name: Test Database Quality
  run: |
    python3 create_test_data.py
    python3 test_database.py
```

## Troubleshooting

### "Database not found"

**Solution:** Run `create_test_data.py` first

### "Tables not present"

**Solution:** Some tests skip if specific tables don't exist (normal for demo data)

### "Join returned 0 rows"

**Cause:** objectids don't match between tables
**Solution:** Use `create_test_data.py` which creates consistent objectids

### Many warnings

**Check:**
1. Old demo data present - delete and recreate
2. Using production data - warnings may be expected
3. Table relationships - verify foreign keys

## Best Practices

### Before Production

1. ✓ Run tests on sample data first
2. ✓ Verify all critical tests pass
3. ✓ Understand warnings
4. ✓ Test joins on actual data
5. ✓ Check index performance

### Regular Testing

1. ✓ Run after each extraction
2. ✓ Monitor test trends
3. ✓ Alert on new failures
4. ✓ Document expected warnings

### Data Quality

1. ✓ Check for duplicates
2. ✓ Validate formats
3. ✓ Test relationships
4. ✓ Verify consistency
5. ✓ Monitor NULL rates

## Files

- `test_database.py` - Main test suite (22 tests)
- `create_test_data.py` - Generate test data
- `TEST_README.md` - This file

## Resources

- [SQLite Testing Best Practices](https://www.sqlite.org/testing.html)
- [Database Quality Metrics](https://en.wikipedia.org/wiki/Data_quality)
- [Referential Integrity](https://en.wikipedia.org/wiki/Referential_integrity)

---

**Questions?** Check test output for detailed error messages and suggestions.
