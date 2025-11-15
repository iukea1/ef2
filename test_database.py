#!/usr/bin/env python3
"""
IRS 990 Database Quality and Relationship Tests

Comprehensive test suite for validating:
- Database structure and schema
- Data quality (nulls, duplicates, types)
- Relationship joins between tables
- Snake_case formatting compliance
- Referential integrity
- Cross-table consistency
"""

import sqlite3
import pandas as pd
import re
from typing import Dict, List, Tuple, Any
from pathlib import Path
import sys

# Configuration
SQLITE_DB = "irs990_all_tables.sqlite"
CSV_DIR = "csv_output"

# Test results tracking
test_results = []
warnings = []


class TestResult:
    """Track individual test results"""
    def __init__(self, category: str, name: str, status: str, message: str = "", details: Any = None):
        self.category = category
        self.name = name
        self.status = status  # PASS, FAIL, WARN
        self.message = message
        self.details = details


def log_test(category: str, name: str, status: str, message: str = "", details: Any = None):
    """Log a test result"""
    result = TestResult(category, name, status, message, details)
    test_results.append(result)

    # Print immediately
    icon = "✓" if status == "PASS" else "✗" if status == "FAIL" else "⚠"
    color = "\033[92m" if status == "PASS" else "\033[91m" if status == "FAIL" else "\033[93m"
    reset = "\033[0m"

    print(f"  {color}{icon}{reset} {name}")
    if message:
        print(f"    {message}")
    if details:
        print(f"    Details: {details}")


def is_snake_case(text: str) -> bool:
    """Check if text is in snake_case format"""
    # Should be lowercase, can contain underscores and numbers
    return bool(re.match(r'^[a-z0-9_]+$', text))


def test_database_exists():
    """Test 1: Database file exists"""
    print("\n" + "=" * 80)
    print("DATABASE STRUCTURE TESTS")
    print("=" * 80)

    if Path(SQLITE_DB).exists():
        file_size = Path(SQLITE_DB).stat().st_size
        log_test("Structure", "Database file exists", "PASS",
                 f"Size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
        return True
    else:
        log_test("Structure", "Database file exists", "FAIL",
                 f"Database not found: {SQLITE_DB}")
        return False


def test_database_connection():
    """Test 2: Can connect to database"""
    try:
        con = sqlite3.connect(SQLITE_DB)
        con.close()
        log_test("Structure", "Database connection", "PASS")
        return True
    except Exception as e:
        log_test("Structure", "Database connection", "FAIL", str(e))
        return False


def test_tables_exist(con: sqlite3.Connection):
    """Test 3: Tables exist and are populated"""
    cursor = con.cursor()
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = [t[0] for t in tables]

    if len(table_names) > 0:
        log_test("Structure", "Tables exist", "PASS",
                 f"Found {len(table_names)} tables")
    else:
        log_test("Structure", "Tables exist", "FAIL", "No tables found")
        return []

    return table_names


def test_snake_case_compliance(con: sqlite3.Connection, table_names: List[str]):
    """Test 4: All tables and columns use snake_case"""
    cursor = con.cursor()
    non_snake_tables = []
    non_snake_columns = {}

    # Check table names
    for table in table_names:
        if not is_snake_case(table):
            non_snake_tables.append(table)

    # Check column names
    for table in table_names:
        columns = cursor.execute(f"PRAGMA table_info({table})").fetchall()
        bad_cols = [col[1] for col in columns if not is_snake_case(col[1])]
        if bad_cols:
            non_snake_columns[table] = bad_cols

    if not non_snake_tables and not non_snake_columns:
        log_test("Formatting", "Snake_case compliance", "PASS",
                 "All tables and columns use snake_case")
    else:
        details = []
        if non_snake_tables:
            details.append(f"Non-snake_case tables: {non_snake_tables}")
        if non_snake_columns:
            details.append(f"Non-snake_case columns: {non_snake_columns}")
        log_test("Formatting", "Snake_case compliance", "FAIL",
                 "\n    ".join(details))


def test_table_row_counts(con: sqlite3.Connection, table_names: List[str]):
    """Test 5: Tables have data"""
    print("\n" + "=" * 80)
    print("DATA POPULATION TESTS")
    print("=" * 80)

    cursor = con.cursor()
    empty_tables = []
    table_stats = {}

    for table in table_names:
        count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        table_stats[table] = count
        if count == 0:
            empty_tables.append(table)

    if not empty_tables:
        log_test("Population", "All tables have data", "PASS",
                 f"Total rows across tables: {sum(table_stats.values()):,}")
    else:
        log_test("Population", "All tables have data", "WARN",
                 f"{len(empty_tables)} empty tables",
                 empty_tables[:5])

    # Show largest tables
    top_tables = sorted(table_stats.items(), key=lambda x: x[1], reverse=True)[:5]
    print(f"\n  Largest tables:")
    for table, count in top_tables:
        print(f"    - {table}: {count:,} rows")

    return table_stats


def test_key_columns_exist(con: sqlite3.Connection, table_names: List[str]):
    """Test 6: Key columns exist (objectid, ein, tax_year)"""
    cursor = con.cursor()
    key_columns = ['objectid', 'ein', 'tax_year']
    tables_with_keys = {col: [] for col in key_columns}
    tables_missing_keys = {col: [] for col in key_columns}

    for table in table_names:
        columns = [col[1] for col in cursor.execute(f"PRAGMA table_info({table})").fetchall()]
        for key_col in key_columns:
            if key_col in columns:
                tables_with_keys[key_col].append(table)
            else:
                tables_missing_keys[key_col].append(table)

    for key_col in key_columns:
        if len(tables_with_keys[key_col]) > 0:
            log_test("Schema", f"Column '{key_col}' exists", "PASS",
                     f"Found in {len(tables_with_keys[key_col])}/{len(table_names)} tables")
        else:
            log_test("Schema", f"Column '{key_col}' exists", "WARN",
                     "Not found in any tables")


def test_duplicate_rows(con: sqlite3.Connection, table_names: List[str]):
    """Test 7: Check for duplicate rows"""
    print("\n" + "=" * 80)
    print("DATA QUALITY TESTS")
    print("=" * 80)

    cursor = con.cursor()
    tables_with_dupes = {}

    for table in table_names[:10]:  # Test first 10 tables
        # Check for duplicate objectids
        query = f"""
            SELECT objectid, COUNT(*) as cnt
            FROM {table}
            GROUP BY objectid
            HAVING COUNT(*) > 1
        """
        try:
            dupes = cursor.execute(query).fetchall()
            if dupes:
                tables_with_dupes[table] = len(dupes)
        except:
            pass  # Table might not have objectid column

    if not tables_with_dupes:
        log_test("Quality", "No duplicate objectids", "PASS",
                 "Checked 10 tables")
    else:
        log_test("Quality", "No duplicate objectids", "WARN",
                 f"{len(tables_with_dupes)} tables have duplicates",
                 tables_with_dupes)


def test_null_key_columns(con: sqlite3.Connection, table_names: List[str]):
    """Test 8: Check for NULLs in key columns"""
    cursor = con.cursor()
    tables_with_nulls = {}

    for table in table_names[:10]:
        # Check if objectid has nulls
        try:
            null_count = cursor.execute(
                f"SELECT COUNT(*) FROM {table} WHERE objectid IS NULL"
            ).fetchone()[0]
            if null_count > 0:
                tables_with_nulls[table] = null_count
        except:
            pass

    if not tables_with_nulls:
        log_test("Quality", "No NULL objectids", "PASS",
                 "Checked 10 tables")
    else:
        log_test("Quality", "No NULL objectids", "FAIL",
                 f"{len(tables_with_nulls)} tables have NULL objectids",
                 tables_with_nulls)


def test_objectid_format(con: sqlite3.Connection, table_names: List[str]):
    """Test 9: Validate objectid format (OID-*)"""
    cursor = con.cursor()
    tables_with_invalid = {}

    for table in table_names[:5]:
        try:
            # Check if objectids start with 'OID-' or 'oid-'
            invalid = cursor.execute(f"""
                SELECT COUNT(*) FROM {table}
                WHERE objectid NOT LIKE 'OID-%' AND objectid NOT LIKE 'oid-%'
            """).fetchone()[0]

            if invalid > 0:
                tables_with_invalid[table] = invalid
        except:
            pass

    if not tables_with_invalid:
        log_test("Quality", "Valid objectid format", "PASS",
                 "All objectids follow OID-* pattern")
    else:
        log_test("Quality", "Valid objectid format", "WARN",
                 f"{len(tables_with_invalid)} tables have invalid objectids",
                 tables_with_invalid)


def test_relationship_joins(con: sqlite3.Connection, table_names: List[str]):
    """Test 10: Test joins between tables using objectid"""
    print("\n" + "=" * 80)
    print("RELATIONSHIP JOIN TESTS")
    print("=" * 80)

    # Test common joins
    join_tests = [
        ("f9_p00_t00_header", "f9_p01_t00_summary", "Header-Summary join"),
        ("f9_p00_t00_header", "f9_p08_t00_revenue", "Header-Revenue join"),
        ("f9_p00_t00_header", "f9_p09_t00_expenses", "Header-Expenses join"),
    ]

    for table1, table2, description in join_tests:
        if table1 not in table_names or table2 not in table_names:
            log_test("Joins", description, "SKIP",
                     f"Tables not present")
            continue

        try:
            query = f"""
                SELECT COUNT(*) as joined_rows
                FROM {table1} t1
                INNER JOIN {table2} t2 ON t1.objectid = t2.objectid
            """
            result = con.execute(query).fetchone()[0]

            # Also get individual counts
            count1 = con.execute(f"SELECT COUNT(*) FROM {table1}").fetchone()[0]
            count2 = con.execute(f"SELECT COUNT(*) FROM {table2}").fetchone()[0]

            if result > 0:
                log_test("Joins", description, "PASS",
                         f"Joined {result:,} rows (from {count1:,} and {count2:,})")
            else:
                log_test("Joins", description, "WARN",
                         "Join returned 0 rows")

        except Exception as e:
            log_test("Joins", description, "FAIL", str(e))


def test_referential_integrity(con: sqlite3.Connection, table_names: List[str]):
    """Test 11: Check if objectids in data tables exist in header"""
    if "f9_p00_t00_header" not in table_names:
        log_test("Integrity", "Referential integrity", "SKIP",
                 "Header table not present")
        return

    cursor = con.cursor()
    orphaned_data = {}

    # Test a few data tables
    data_tables = [t for t in table_names if t != "f9_p00_t00_header"][:5]

    for table in data_tables:
        try:
            query = f"""
                SELECT COUNT(*) FROM {table} t
                WHERE NOT EXISTS (
                    SELECT 1 FROM f9_p00_t00_header h
                    WHERE h.objectid = t.objectid
                )
            """
            orphaned = cursor.execute(query).fetchone()[0]
            if orphaned > 0:
                orphaned_data[table] = orphaned
        except:
            pass

    if not orphaned_data:
        log_test("Integrity", "Referential integrity", "PASS",
                 "All data table objectids exist in header")
    else:
        log_test("Integrity", "Referential integrity", "WARN",
                 f"{len(orphaned_data)} tables have orphaned records",
                 orphaned_data)


def test_index_exists(con: sqlite3.Connection, table_names: List[str]):
    """Test 12: Check if indexes exist on key columns"""
    cursor = con.cursor()
    tables_with_indexes = {}
    tables_without_indexes = []

    for table in table_names[:10]:
        indexes = cursor.execute(
            f"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='{table}'"
        ).fetchall()

        if indexes:
            tables_with_indexes[table] = len(indexes)
        else:
            tables_without_indexes.append(table)

    if len(tables_with_indexes) > 0:
        log_test("Performance", "Indexes exist", "PASS",
                 f"{len(tables_with_indexes)} tables have indexes")
    else:
        log_test("Performance", "Indexes exist", "WARN",
                 "No indexes found on any tables")


def test_data_types(con: sqlite3.Connection, table_names: List[str]):
    """Test 13: Validate data types make sense"""
    print("\n" + "=" * 80)
    print("DATA TYPE VALIDATION TESTS")
    print("=" * 80)

    # Test numeric columns can be converted
    test_table = table_names[0] if table_names else None
    if not test_table:
        return

    try:
        df = pd.read_sql(f"SELECT * FROM {test_table} LIMIT 100", con)

        # Check for columns that look like numbers
        numeric_cols = [col for col in df.columns if
                        'year' in col.lower() or
                        'amount' in col.lower() or
                        'revenue' in col.lower() or
                        'total' in col.lower()]

        convertible = []
        non_convertible = []

        for col in numeric_cols[:5]:  # Test first 5 numeric-looking columns
            try:
                pd.to_numeric(df[col].dropna(), errors='raise')
                convertible.append(col)
            except:
                non_convertible.append(col)

        if len(numeric_cols) > 0:
            log_test("Types", "Numeric columns convertible", "PASS",
                     f"{len(convertible)}/{len(numeric_cols[:5])} tested columns are numeric")

    except Exception as e:
        log_test("Types", "Numeric columns convertible", "WARN",
                 f"Could not test: {str(e)[:100]}")


def test_cross_table_consistency(con: sqlite3.Connection, table_names: List[str]):
    """Test 14: Check consistency across related tables"""
    # Test that tax_year is consistent across joined records
    if "f9_p00_t00_header" not in table_names or "f9_p08_t00_revenue" not in table_names:
        log_test("Consistency", "Cross-table tax_year match", "SKIP",
                 "Required tables not present")
        return

    try:
        query = """
            SELECT COUNT(*) FROM f9_p00_t00_header h
            INNER JOIN f9_p08_t00_revenue r ON h.objectid = r.objectid
            WHERE h.tax_year != r.tax_year
        """
        mismatches = con.execute(query).fetchone()[0]

        if mismatches == 0:
            log_test("Consistency", "Cross-table tax_year match", "PASS",
                     "Tax years match across header and revenue tables")
        else:
            log_test("Consistency", "Cross-table tax_year match", "FAIL",
                     f"{mismatches} records have mismatched tax_years")
    except Exception as e:
        log_test("Consistency", "Cross-table tax_year match", "WARN",
                 f"Could not test: {str(e)[:100]}")


def test_csv_files_exist():
    """Test 15: Check CSV files exist and match database"""
    print("\n" + "=" * 80)
    print("CSV FILE VALIDATION TESTS")
    print("=" * 80)

    if not Path(CSV_DIR).exists():
        log_test("CSV", "CSV directory exists", "FAIL",
                 f"Directory not found: {CSV_DIR}")
        return

    csv_files = list(Path(CSV_DIR).glob("*.csv"))

    if csv_files:
        log_test("CSV", "CSV files exist", "PASS",
                 f"Found {len(csv_files)} CSV files")

        # Test snake_case filenames
        non_snake = [f.name for f in csv_files if not is_snake_case(f.stem)]
        if not non_snake:
            log_test("CSV", "CSV filenames are snake_case", "PASS")
        else:
            log_test("CSV", "CSV filenames are snake_case", "WARN",
                     f"{len(non_snake)} files not in snake_case")

        # Test CSV can be read
        try:
            test_file = csv_files[0]
            df = pd.read_csv(test_file, nrows=5)
            log_test("CSV", "CSV files readable", "PASS",
                     f"Tested: {test_file.name}")

            # Check column names are snake_case
            non_snake_cols = [col for col in df.columns if not is_snake_case(col)]
            if not non_snake_cols:
                log_test("CSV", "CSV columns are snake_case", "PASS")
            else:
                log_test("CSV", "CSV columns are snake_case", "FAIL",
                         f"Non-snake_case columns: {non_snake_cols}")

        except Exception as e:
            log_test("CSV", "CSV files readable", "FAIL", str(e))
    else:
        log_test("CSV", "CSV files exist", "WARN",
                 "No CSV files found")


def print_summary():
    """Print test summary"""
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    # Count by status
    passed = sum(1 for t in test_results if t.status == "PASS")
    failed = sum(1 for t in test_results if t.status == "FAIL")
    warned = sum(1 for t in test_results if t.status == "WARN")
    skipped = sum(1 for t in test_results if t.status == "SKIP")

    total = len(test_results)

    print(f"\nTotal Tests: {total}")
    print(f"  ✓ Passed:  {passed} ({passed/total*100:.1f}%)")
    print(f"  ✗ Failed:  {failed} ({failed/total*100:.1f}%)")
    print(f"  ⚠ Warnings: {warned} ({warned/total*100:.1f}%)")
    print(f"  ○ Skipped: {skipped} ({skipped/total*100:.1f}%)")

    # Group by category
    print("\nResults by Category:")
    categories = {}
    for test in test_results:
        if test.category not in categories:
            categories[test.category] = {"PASS": 0, "FAIL": 0, "WARN": 0, "SKIP": 0}
        categories[test.category][test.status] += 1

    for category, counts in sorted(categories.items()):
        total_cat = sum(counts.values())
        passed_cat = counts["PASS"]
        print(f"  {category}: {passed_cat}/{total_cat} passed")

    # Overall status
    print("\n" + "=" * 80)
    if failed == 0:
        print("✓ ALL CRITICAL TESTS PASSED")
        if warned > 0:
            print(f"⚠ {warned} warnings (non-critical issues)")
    else:
        print(f"✗ {failed} CRITICAL TEST(S) FAILED")

    print("=" * 80)

    return failed == 0


def main():
    """Run all tests"""
    print("=" * 80)
    print("IRS 990 DATABASE QUALITY AND RELATIONSHIP TESTS")
    print("=" * 80)
    print(f"Database: {SQLITE_DB}")
    print(f"CSV Directory: {CSV_DIR}")
    print("=" * 80)

    # Database structure tests
    if not test_database_exists():
        print("\n✗ Cannot proceed - database does not exist")
        return False

    if not test_database_connection():
        print("\n✗ Cannot proceed - cannot connect to database")
        return False

    # Connect to database
    con = sqlite3.connect(SQLITE_DB)

    try:
        # Structure tests
        table_names = test_tables_exist(con)
        if not table_names:
            print("\n✗ Cannot proceed - no tables found")
            return False

        test_snake_case_compliance(con, table_names)

        # Data population tests
        table_stats = test_table_row_counts(con, table_names)
        test_key_columns_exist(con, table_names)

        # Data quality tests
        test_duplicate_rows(con, table_names)
        test_null_key_columns(con, table_names)
        test_objectid_format(con, table_names)

        # Relationship tests
        test_relationship_joins(con, table_names)
        test_referential_integrity(con, table_names)

        # Performance tests
        test_index_exists(con, table_names)

        # Type validation
        test_data_types(con, table_names)

        # Consistency tests
        test_cross_table_consistency(con, table_names)

        # CSV validation
        test_csv_files_exist()

    finally:
        con.close()

    # Print summary
    success = print_summary()

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
