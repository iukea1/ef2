#!/usr/bin/env python3
"""
Comprehensive Data Validation for IRS 990 Extracted Data

Validates data quality across all extracted tables including:
- Completeness checks
- Format validation
- Business rule validation
- Outlier detection
- Cross-table consistency
- Temporal consistency (for multi-year data)
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Any
import re
import json
from datetime import datetime

# Configuration
SQLITE_DB = "irs990_all_tables.sqlite"
COMBINED_DB = "irs990_combined_years.sqlite"
VALIDATION_REPORT = "validation_report.json"

# Validation results
validation_results = []


class ValidationRule:
    """Single validation rule"""
    def __init__(self, category: str, rule_name: str, severity: str = "ERROR"):
        self.category = category
        self.rule_name = rule_name
        self.severity = severity  # ERROR, WARNING, INFO
        self.passed = 0
        self.failed = 0
        self.details = []

    def add_failure(self, detail: str):
        self.failed += 1
        self.details.append(detail)

    def add_pass(self):
        self.passed += 1

    def to_dict(self):
        return {
            'category': self.category,
            'rule': self.rule_name,
            'severity': self.severity,
            'passed': self.passed,
            'failed': self.failed,
            'pass_rate': f"{self.passed / max(1, self.passed + self.failed) * 100:.1f}%",
            'details': self.details[:10]  # Limit to 10 examples
        }


def print_header(title: str):
    """Print section header"""
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}")


def validate_ein_format(con: sqlite3.Connection, table_name: str) -> ValidationRule:
    """Validate EIN format (9 digits)"""
    rule = ValidationRule("Format", f"{table_name}: EIN format", "ERROR")

    query = f"""
        SELECT ein, COUNT(*) as cnt
        FROM {table_name}
        WHERE ein IS NOT NULL
        GROUP BY ein
    """

    try:
        df = pd.read_sql(query, con)

        for _, row in df.iterrows():
            ein = str(row['ein'])
            # Remove any formatting
            ein_clean = re.sub(r'[^0-9]', '', ein)

            if len(ein_clean) == 9:
                rule.add_pass()
            else:
                rule.add_failure(f"Invalid EIN: {ein} (length: {len(ein_clean)})")

    except Exception as e:
        rule.add_failure(f"Query error: {str(e)[:100]}")

    return rule


def validate_tax_year_range(con: sqlite3.Connection, table_name: str) -> ValidationRule:
    """Validate tax year is reasonable (2007-2024)"""
    rule = ValidationRule("Business Logic", f"{table_name}: Tax year range", "ERROR")

    query = f"""
        SELECT tax_year, COUNT(*) as cnt
        FROM {table_name}
        WHERE tax_year IS NOT NULL
        GROUP BY tax_year
    """

    try:
        df = pd.read_sql(query, con)

        for _, row in df.iterrows():
            year = int(row['tax_year'])

            if 2007 <= year <= 2024:
                rule.add_pass()
            else:
                rule.add_failure(f"Invalid tax year: {year}")

    except Exception as e:
        rule.add_failure(f"Query error: {str(e)[:100]}")

    return rule


def validate_revenue_non_negative(con: sqlite3.Connection) -> ValidationRule:
    """Validate revenue amounts are non-negative"""
    rule = ValidationRule("Business Logic", "Revenue: Non-negative values", "ERROR")

    # Check if revenue table exists
    try:
        query = """
            SELECT
                objectid,
                ein,
                f9_p8_total_revenue
            FROM f9_p08_t00_revenue
            WHERE f9_p8_total_revenue IS NOT NULL
        """

        df = pd.read_sql(query, con)

        for _, row in df.iterrows():
            try:
                revenue = float(row['f9_p8_total_revenue'])
                if revenue >= 0:
                    rule.add_pass()
                else:
                    rule.add_failure(f"Negative revenue: {row['ein']} = {revenue}")
            except (ValueError, TypeError):
                rule.add_failure(f"Non-numeric revenue: {row['f9_p8_total_revenue']}")

    except Exception as e:
        rule.add_failure(f"Table not available: {str(e)[:100]}")

    return rule


def validate_revenue_components_sum(con: sqlite3.Connection) -> ValidationRule:
    """Validate revenue components sum to total (within tolerance)"""
    rule = ValidationRule("Business Logic", "Revenue: Components sum to total", "WARNING")

    try:
        query = """
            SELECT
                objectid,
                ein,
                f9_p8_total_revenue,
                f9_p8_contributions_gifts_grants,
                f9_p8_program_service_revenue,
                f9_p8_investment_income,
                f9_p8_other_revenue
            FROM f9_p08_t00_revenue
            WHERE f9_p8_total_revenue IS NOT NULL
        """

        df = pd.read_sql(query, con)

        for _, row in df.iterrows():
            try:
                total = float(row['f9_p8_total_revenue'] or 0)
                components = [
                    float(row['f9_p8_contributions_gifts_grants'] or 0),
                    float(row['f9_p8_program_service_revenue'] or 0),
                    float(row['f9_p8_investment_income'] or 0),
                    float(row['f9_p8_other_revenue'] or 0)
                ]
                component_sum = sum(components)

                # Allow 1% tolerance for rounding
                tolerance = max(1.0, total * 0.01)

                if abs(total - component_sum) <= tolerance:
                    rule.add_pass()
                else:
                    rule.add_failure(
                        f"EIN {row['ein']}: Total={total:,.0f}, Components={component_sum:,.0f}, "
                        f"Diff={total - component_sum:,.0f}"
                    )

            except (ValueError, TypeError) as e:
                rule.add_failure(f"Calculation error: {str(e)[:50]}")

    except Exception as e:
        rule.add_failure(f"Table not available: {str(e)[:100]}")

    return rule


def validate_completeness(con: sqlite3.Connection, table_name: str, key_columns: List[str]) -> List[ValidationRule]:
    """Validate key columns are not NULL"""
    rules = []

    cursor = con.cursor()

    # Get actual columns in table
    try:
        columns_query = f"PRAGMA table_info({table_name})"
        columns = [row[1] for row in cursor.execute(columns_query).fetchall()]
    except:
        return rules

    for col in key_columns:
        if col in columns:
            rule = ValidationRule("Completeness", f"{table_name}: {col} not null", "ERROR")

            query = f"""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) as null_count
                FROM {table_name}
            """

            try:
                result = cursor.execute(query).fetchone()
                total = result[0]
                null_count = result[1]

                rule.passed = total - null_count
                rule.failed = null_count

                if null_count > 0:
                    rule.add_failure(f"{null_count} NULL values out of {total} total")

            except Exception as e:
                rule.add_failure(f"Query error: {str(e)[:100]}")

            rules.append(rule)

    return rules


def validate_outliers(con: sqlite3.Connection, table_name: str, column: str, threshold: float = 3.0) -> ValidationRule:
    """Detect outliers using z-score method"""
    rule = ValidationRule("Data Quality", f"{table_name}: {column} outliers", "WARNING")

    query = f"""
        SELECT objectid, ein, {column}
        FROM {table_name}
        WHERE {column} IS NOT NULL
    """

    try:
        df = pd.read_sql(query, con)

        if len(df) < 10:  # Need enough data for statistics
            rule.add_failure("Insufficient data for outlier detection")
            return rule

        # Convert to numeric
        df[column] = pd.to_numeric(df[column], errors='coerce')
        df = df.dropna(subset=[column])

        # Calculate z-scores
        mean = df[column].mean()
        std = df[column].std()

        if std == 0:
            rule.add_failure("No variance in data")
            return rule

        df['z_score'] = np.abs((df[column] - mean) / std)

        # Find outliers
        outliers = df[df['z_score'] > threshold]

        rule.passed = len(df) - len(outliers)
        rule.failed = len(outliers)

        for _, row in outliers.head(5).iterrows():
            rule.add_failure(
                f"EIN {row['ein']}: {column}={row[column]:,.0f} "
                f"(z-score={row['z_score']:.2f})"
            )

    except Exception as e:
        rule.add_failure(f"Analysis error: {str(e)[:100]}")

    return rule


def validate_cross_table_consistency(con: sqlite3.Connection) -> List[ValidationRule]:
    """Validate consistency across related tables"""
    rules = []

    # Rule 1: Revenue in summary matches revenue table
    rule = ValidationRule("Consistency", "Summary revenue matches detail revenue", "ERROR")

    try:
        query = """
            SELECT
                s.ein,
                s.f9_p1_total_revenue as summary_revenue,
                r.f9_p8_total_revenue as detail_revenue
            FROM f9_p01_t00_summary s
            INNER JOIN f9_p08_t00_revenue r ON s.objectid = r.objectid
            WHERE s.f9_p1_total_revenue IS NOT NULL
                AND r.f9_p8_total_revenue IS NOT NULL
        """

        df = pd.read_sql(query, con)

        for _, row in df.iterrows():
            summary = float(row['summary_revenue'])
            detail = float(row['detail_revenue'])

            if summary == detail:
                rule.add_pass()
            else:
                rule.add_failure(
                    f"EIN {row['ein']}: Summary={summary:,.0f}, Detail={detail:,.0f}"
                )

    except Exception as e:
        rule.add_failure(f"Tables not available: {str(e)[:100]}")

    rules.append(rule)

    # Rule 2: Tax year matches across joined tables
    rule = ValidationRule("Consistency", "Tax year matches across joins", "ERROR")

    try:
        query = """
            SELECT
                h.ein,
                h.tax_year as header_year,
                r.tax_year as revenue_year
            FROM f9_p00_t00_header h
            INNER JOIN f9_p08_t00_revenue r ON h.objectid = r.objectid
        """

        df = pd.read_sql(query, con)

        for _, row in df.iterrows():
            if row['header_year'] == row['revenue_year']:
                rule.add_pass()
            else:
                rule.add_failure(
                    f"EIN {row['ein']}: Header year={row['header_year']}, "
                    f"Revenue year={row['revenue_year']}"
                )

    except Exception as e:
        rule.add_failure(f"Tables not available: {str(e)[:100]}")

    rules.append(rule)

    return rules


def validate_temporal_consistency(con: sqlite3.Connection) -> List[ValidationRule]:
    """Validate temporal patterns (for multi-year data)"""
    rules = []

    # Rule: Organizations shouldn't skip years
    rule = ValidationRule("Temporal", "Organizations file consecutively", "WARNING")

    try:
        query = """
            SELECT ein, GROUP_CONCAT(tax_year) as years
            FROM f9_p00_t00_header
            GROUP BY ein
            HAVING COUNT(DISTINCT tax_year) > 1
        """

        df = pd.read_sql(query, con)

        for _, row in df.iterrows():
            years = sorted([int(y) for y in str(row['years']).split(',')])

            # Check for gaps
            has_gap = False
            for i in range(len(years) - 1):
                if years[i + 1] - years[i] > 1:
                    has_gap = True
                    break

            if has_gap:
                rule.add_failure(f"EIN {row['ein']}: Filed in years {years}")
            else:
                rule.add_pass()

    except Exception as e:
        rule.add_failure(f"Analysis error: {str(e)[:100]}")

    rules.append(rule)

    return rules


def generate_validation_report(all_rules: List[ValidationRule]):
    """Generate comprehensive validation report"""
    print_header("VALIDATION REPORT SUMMARY")

    # Count by severity
    errors = [r for r in all_rules if r.severity == "ERROR" and r.failed > 0]
    warnings = [r for r in all_rules if r.severity == "WARNING" and r.failed > 0]
    info = [r for r in all_rules if r.severity == "INFO" and r.failed > 0]

    total_checks = sum(r.passed + r.failed for r in all_rules)
    failed_checks = sum(r.failed for r in all_rules)
    passed_checks = sum(r.passed for r in all_rules)

    print(f"\nOverall Statistics:")
    print(f"  Total checks: {total_checks:,}")
    print(f"  Passed: {passed_checks:,} ({passed_checks/max(1,total_checks)*100:.1f}%)")
    print(f"  Failed: {failed_checks:,} ({failed_checks/max(1,total_checks)*100:.1f}%)")
    print(f"\nIssues by Severity:")
    print(f"  Errors: {len(errors)}")
    print(f"  Warnings: {len(warnings)}")
    print(f"  Info: {len(info)}")

    # Show critical errors
    if errors:
        print("\n❌ CRITICAL ERRORS:")
        for rule in errors[:5]:
            print(f"\n  {rule.category} - {rule.rule_name}")
            print(f"    Failed: {rule.failed:,} / {rule.passed + rule.failed:,}")
            if rule.details:
                print(f"    Example: {rule.details[0]}")

    # Show warnings
    if warnings:
        print("\n⚠️  WARNINGS:")
        for rule in warnings[:5]:
            print(f"\n  {rule.category} - {rule.rule_name}")
            print(f"    Failed: {rule.failed:,} / {rule.passed + rule.failed:,}")
            if rule.details:
                print(f"    Example: {rule.details[0]}")

    # Category summary
    print("\nValidation by Category:")
    categories = {}
    for rule in all_rules:
        if rule.category not in categories:
            categories[rule.category] = {'passed': 0, 'failed': 0}
        categories[rule.category]['passed'] += rule.passed
        categories[rule.category]['failed'] += rule.failed

    for category, stats in sorted(categories.items()):
        total = stats['passed'] + stats['failed']
        rate = stats['passed'] / max(1, total) * 100
        print(f"  {category:<20} {stats['passed']:>8,} / {total:>8,} ({rate:>5.1f}%)")

    # Save to JSON
    report = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_checks': total_checks,
            'passed': passed_checks,
            'failed': failed_checks,
            'error_count': len(errors),
            'warning_count': len(warnings)
        },
        'rules': [r.to_dict() for r in all_rules],
        'categories': categories
    }

    with open(VALIDATION_REPORT, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n✓ Detailed report saved to: {VALIDATION_REPORT}")

    # Overall result
    if errors:
        print(f"\n❌ VALIDATION FAILED - {len(errors)} critical errors found")
        return False
    elif warnings:
        print(f"\n⚠️  VALIDATION PASSED WITH WARNINGS - {len(warnings)} warnings found")
        return True
    else:
        print(f"\n✅ VALIDATION PASSED - All checks successful!")
        return True


def main():
    """Run all validation checks"""
    print_header("IRS 990 DATA VALIDATION")

    # Check if database exists
    db_path = Path(SQLITE_DB)
    if not db_path.exists():
        print(f"\n❌ Database not found: {SQLITE_DB}")
        print("Run create_test_data.py or extract_all_tables.py first")
        return False

    con = sqlite3.connect(SQLITE_DB)

    # Get all tables
    cursor = con.cursor()
    tables = [row[0] for row in cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]

    print(f"\nDatabase: {SQLITE_DB}")
    print(f"Tables found: {len(tables)}")

    all_rules = []

    # Format validations
    print_header("FORMAT VALIDATION")
    for table in tables:
        if 'header' in table or 'revenue' in table:
            rule = validate_ein_format(con, table)
            all_rules.append(rule)
            print(f"  {rule.rule_name}: {rule.passed} passed, {rule.failed} failed")

    # Tax year validation
    print_header("TAX YEAR VALIDATION")
    for table in tables:
        rule = validate_tax_year_range(con, table)
        all_rules.append(rule)
        print(f"  {rule.rule_name}: {rule.passed} passed, {rule.failed} failed")

    # Completeness validation
    print_header("COMPLETENESS VALIDATION")
    key_columns = ['objectid', 'ein', 'tax_year']
    for table in tables:
        rules = validate_completeness(con, table, key_columns)
        all_rules.extend(rules)
        for rule in rules:
            if rule.failed > 0:
                print(f"  {rule.rule_name}: {rule.passed} passed, {rule.failed} failed")

    # Business logic validation
    print_header("BUSINESS LOGIC VALIDATION")

    rule = validate_revenue_non_negative(con)
    all_rules.append(rule)
    print(f"  {rule.rule_name}: {rule.passed} passed, {rule.failed} failed")

    rule = validate_revenue_components_sum(con)
    all_rules.append(rule)
    print(f"  {rule.rule_name}: {rule.passed} passed, {rule.failed} failed")

    # Cross-table consistency
    print_header("CROSS-TABLE CONSISTENCY")
    rules = validate_cross_table_consistency(con)
    all_rules.extend(rules)
    for rule in rules:
        print(f"  {rule.rule_name}: {rule.passed} passed, {rule.failed} failed")

    # Outlier detection
    print_header("OUTLIER DETECTION")
    if 'f9_p08_t00_revenue' in tables:
        rule = validate_outliers(con, 'f9_p08_t00_revenue', 'f9_p8_total_revenue')
        all_rules.append(rule)
        print(f"  {rule.rule_name}: {rule.passed} passed, {rule.failed} failed")

    # Temporal consistency (if multi-year)
    print_header("TEMPORAL CONSISTENCY")
    rules = validate_temporal_consistency(con)
    all_rules.extend(rules)
    for rule in rules:
        print(f"  {rule.rule_name}: {rule.passed} passed, {rule.failed} failed")

    con.close()

    # Generate report
    success = generate_validation_report(all_rules)

    return success


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
