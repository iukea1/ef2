#!/usr/bin/env python3
"""
Create comprehensive test data to demonstrate database quality tests
Including proper relationships between tables
"""

import sqlite3
import pandas as pd
from pathlib import Path

# Configuration
SQLITE_DB = "irs990_all_tables.sqlite"
CSV_DIR = "csv_output"

# Create output directory
Path(CSV_DIR).mkdir(exist_ok=True)

# Sample data with relationships
YEAR = 2021

# Shared objectids for consistent joins
objectids = [
    'OID-202120139349301207',
    'OID-202120139349301208',
    'OID-202120139349301209',
    'OID-202120139349301210',
    'OID-202120139349301211'
]

eins = ['123456789', '987654321', '555555555', '111222333', '999888777']
org_names = [
    'Community Health Services Inc',
    'Education Foundation',
    'Arts Council',
    'Environmental Defense Fund',
    'Youth Sports League'
]

print("Creating comprehensive test data with relationships...\n")

# 1. Header table (f9_p00_t00_header)
header_data = pd.DataFrame({
    'objectid': objectids,
    'ein': eins,
    'taxpayer_name': org_names,
    'tax_year': [YEAR] * 5,
    'form_type': ['990', '990', '990EZ', '990', '990'],
    'organization_type': ['Corporation', 'Trust', 'Corporation', 'Corporation', 'Association'],
    'tax_period_begin': ['2021-01-01'] * 5,
    'tax_period_end': ['2021-12-31'] * 5,
    'url': [f'https://nccs-efile.s3.us-east-1.amazonaws.com/xml/{oid.replace("OID-", "")}_public.xml'
            for oid in objectids]
})

# 2. Revenue table (f9_p08_t00_revenue)
revenue_data = pd.DataFrame({
    'objectid': objectids,
    'ein': eins,
    'tax_year': [YEAR] * 5,
    'f9_p8_contributions_gifts_grants': ['500000', '250000', '100000', '750000', '150000'],
    'f9_p8_program_service_revenue': ['300000', '150000', '50000', '400000', '80000'],
    'f9_p8_investment_income': ['50000', '25000', '10000', '60000', '15000'],
    'f9_p8_other_revenue': ['25000', '10000', '5000', '30000', '8000'],
    'f9_p8_total_revenue': ['875000', '435000', '165000', '1240000', '253000']
})

# 3. Expenses table (f9_p09_t00_expenses)
expenses_data = pd.DataFrame({
    'objectid': objectids,
    'ein': eins,
    'tax_year': [YEAR] * 5,
    'f9_p9_grants_and_similar_paid': ['200000', '100000', '40000', '300000', '60000'],
    'f9_p9_compensation_officers': ['150000', '80000', '30000', '200000', '50000'],
    'f9_p9_other_salaries_wages': ['250000', '120000', '50000', '350000', '70000'],
    'f9_p9_professional_fees': ['75000', '35000', '15000', '100000', '20000'],
    'f9_p9_total_expenses': ['750000', '380000', '155000', '1100000', '230000']
})

# 4. Balance sheet table (f9_p10_t00_balance_sheet)
balance_sheet_data = pd.DataFrame({
    'objectid': objectids,
    'ein': eins,
    'tax_year': [YEAR] * 5,
    'f9_p10_cash_boy': ['100000', '50000', '20000', '150000', '30000'],
    'f9_p10_cash_eoy': ['225000', '105000', '30000', '290000', '53000'],
    'f9_p10_total_assets_boy': ['500000', '250000', '100000', '750000', '150000'],
    'f9_p10_total_assets_eoy': ['625000', '305000', '110000', '890000', '173000'],
    'f9_p10_total_liabilities_boy': ['50000', '25000', '10000', '75000', '15000'],
    'f9_p10_total_liabilities_eoy': ['40000', '20000', '8000', '60000', '12000'],
    'f9_p10_net_assets_eoy': ['585000', '285000', '102000', '830000', '161000']
})

# 5. Compensation table (f9_p07_t01_compensation) - one-to-many
# Multiple officers per organization
compensation_data = pd.DataFrame({
    'objectid': [objectids[0], objectids[0], objectids[1], objectids[1], objectids[2],
                 objectids[3], objectids[3], objectids[4]],
    'ein': [eins[0], eins[0], eins[1], eins[1], eins[2],
            eins[3], eins[3], eins[4]],
    'tax_year': [YEAR] * 8,
    'person_name': ['John Smith', 'Jane Doe', 'Bob Johnson', 'Alice Williams',
                    'Charlie Brown', 'David Lee', 'Emma Davis', 'Frank Miller'],
    'title': ['Executive Director', 'CFO', 'President', 'Treasurer',
              'Director', 'CEO', 'COO', 'Executive Director'],
    'average_hours_per_week': ['40', '40', '40', '35', '40', '40', '40', '35'],
    'reportable_compensation': ['120000', '85000', '95000', '65000', '75000',
                                '150000', '110000', '80000'],
    'other_compensation': ['15000', '10000', '12000', '8000', '5000',
                          '18000', '14000', '9000']
})

# 6. Summary table (f9_p01_t00_summary)
summary_data = pd.DataFrame({
    'objectid': objectids,
    'ein': eins,
    'tax_year': [YEAR] * 5,
    'taxpayer_name': org_names,
    'f9_p1_gross_receipts': ['900000', '450000', '170000', '1300000', '260000'],
    'f9_p1_total_revenue': ['875000', '435000', '165000', '1240000', '253000'],
    'f9_p1_total_expenses': ['750000', '380000', '155000', '1100000', '230000'],
    'f9_p1_net_assets': ['585000', '285000', '102000', '830000', '161000']
})

# Create database and write tables
print("Writing to SQLite database...")
con = sqlite3.connect(SQLITE_DB)

tables = {
    'f9_p00_t00_header': header_data,
    'f9_p08_t00_revenue': revenue_data,
    'f9_p09_t00_expenses': expenses_data,
    'f9_p10_t00_balance_sheet': balance_sheet_data,
    'f9_p07_t01_compensation': compensation_data,
    'f9_p01_t00_summary': summary_data
}

for table_name, data in tables.items():
    data.to_sql(table_name, con, if_exists='replace', index=False)
    print(f"  ✓ Created table: {table_name} ({len(data)} rows)")

    # Create indexes
    con.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_objectid ON {table_name}(objectid);")
    con.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_ein ON {table_name}(ein);")
    con.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_tax_year ON {table_name}(tax_year);")

    # Write to CSV
    csv_file = f"{CSV_DIR}/{table_name}_{YEAR}.csv"
    data.to_csv(csv_file, index=False)
    print(f"  ✓ Created CSV: {csv_file}")

con.commit()
con.close()

print("\n" + "=" * 80)
print("Test Data Summary")
print("=" * 80)
print(f"Organizations: {len(objectids)}")
print(f"Tables created: {len(tables)}")
print(f"Total records: {sum(len(df) for df in tables.values())}")
print("\nRelationships:")
print("  - Header (5) ← → Revenue (5) [one-to-one]")
print("  - Header (5) ← → Expenses (5) [one-to-one]")
print("  - Header (5) ← → Balance Sheet (5) [one-to-one]")
print("  - Header (5) ← → Compensation (8) [one-to-many]")
print("  - Header (5) ← → Summary (5) [one-to-one]")
print("\nKey Features:")
print("  ✓ All objectids are consistent across tables")
print("  ✓ All tax_years match (2021)")
print("  ✓ Revenue = Summary total_revenue (data consistency)")
print("  ✓ One-to-many relationship in compensation table")
print("  ✓ All tables use snake_case naming")
print("  ✓ Indexes created on objectid, ein, tax_year")
print("\n" + "=" * 80)
print("Ready for testing! Run: python3 test_database.py")
print("=" * 80)
