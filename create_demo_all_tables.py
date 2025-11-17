#!/usr/bin/env python3
"""
Create sample data for irs990_all_tables.sqlite in demo mode
Generates multiple tables with snake_case formatting for testing
"""

import sqlite3
import pandas as pd
from pathlib import Path

SQLITE_DB = "irs990_all_tables.sqlite"

print("=" * 80)
print("Creating Sample Multi-Table Database")
print("=" * 80)

# Remove old database if it exists
if Path(SQLITE_DB).exists():
    Path(SQLITE_DB).unlink()
    print(f"✓ Removed existing {SQLITE_DB}")

# Create connection
con = sqlite3.connect(SQLITE_DB)
cursor = con.cursor()

print(f"\nGenerating sample data for multiple IRS 990 tables...\n")

# Table 1: f9_p00_t00_header (Header information)
header_data = pd.DataFrame({
    'objectid': ['OID-202120139349301207', 'OID-202120139349301208', 'OID-202120139349301209'],
    'ein': ['123456789', '987654321', '555555555'],
    'taxpayer_name': ['Sample Nonprofit 1', 'Sample Nonprofit 2', 'Sample Nonprofit 3'],
    'tax_year': [2021, 2021, 2021],
    'form_type': ['990', '990', '990EZ'],
    'return_timestamp': ['2022-01-15', '2022-02-20', '2022-03-10'],
    'tax_period_begin_date': ['2021-01-01', '2021-01-01', '2021-01-01'],
    'tax_period_end_date': ['2021-12-31', '2021-12-31', '2021-12-31'],
    'business_name_line1': ['Sample Nonprofit One', 'Sample Nonprofit Two', 'Sample Nonprofit Three'],
    'city': ['New York', 'Los Angeles', 'Chicago'],
    'state': ['NY', 'CA', 'IL'],
    'zip': ['10001', '90001', '60601']
})
header_data.to_sql('f9_p00_t00_header', con, if_exists='replace', index=False)
print(f"✓ Created f9_p00_t00_header ({len(header_data)} rows)")

# Table 2: f9_p01_t00_summary (Summary financial data)
summary_data = pd.DataFrame({
    'objectid': ['OID-202120139349301207', 'OID-202120139349301208', 'OID-202120139349301209'],
    'ein': ['123456789', '987654321', '555555555'],
    'tax_year': [2021, 2021, 2021],
    'form_type': ['990', '990', '990EZ'],
    'total_revenue': [850000, 425000, 160000],
    'total_expenses': [750000, 375000, 140000],
    'net_assets_eoy': [2500000, 1200000, 450000],
    'gross_receipts': [850000, 425000, 160000],
    'total_functional_expenses': [750000, 375000, 140000]
})
summary_data.to_sql('f9_p01_t00_summary', con, if_exists='replace', index=False)
print(f"✓ Created f9_p01_t00_summary ({len(summary_data)} rows)")

# Table 3: f9_p08_t00_revenue (Revenue details)
revenue_data = pd.DataFrame({
    'objectid': ['OID-202120139349301207', 'OID-202120139349301208', 'OID-202120139349301209'],
    'ein': ['123456789', '987654321', '555555555'],
    'taxpayer_name': ['Sample Nonprofit 1', 'Sample Nonprofit 2', 'Sample Nonprofit 3'],
    'tax_year': [2021, 2021, 2021],
    'form_type': ['990', '990', '990EZ'],
    'contributions_gifts_grants': [500000, 250000, 100000],
    'program_service_revenue': [300000, 150000, 50000],
    'investment_income': [50000, 25000, 10000],
    'total_revenue': [850000, 425000, 160000]
})
revenue_data.to_sql('f9_p08_t00_revenue', con, if_exists='replace', index=False)
print(f"✓ Created f9_p08_t00_revenue ({len(revenue_data)} rows)")

# Table 4: f9_p09_t00_expenses (Expense details)
expense_data = pd.DataFrame({
    'objectid': ['OID-202120139349301207', 'OID-202120139349301208', 'OID-202120139349301209'],
    'ein': ['123456789', '987654321', '555555555'],
    'tax_year': [2021, 2021, 2021],
    'form_type': ['990', '990', '990EZ'],
    'grants_paid': [200000, 100000, 40000],
    'salaries_compensation': [400000, 200000, 75000],
    'professional_fees': [50000, 25000, 10000],
    'occupancy_rent': [75000, 37500, 12000],
    'depreciation': [25000, 12500, 3000],
    'total_expenses': [750000, 375000, 140000]
})
expense_data.to_sql('f9_p09_t00_expenses', con, if_exists='replace', index=False)
print(f"✓ Created f9_p09_t00_expenses ({len(expense_data)} rows)")

# Table 5: f9_p10_t00_balance_sheet (Balance sheet)
balance_data = pd.DataFrame({
    'objectid': ['OID-202120139349301207', 'OID-202120139349301208', 'OID-202120139349301209'],
    'ein': ['123456789', '987654321', '555555555'],
    'tax_year': [2021, 2021, 2021],
    'form_type': ['990', '990', '990EZ'],
    'cash_eoy': [500000, 250000, 100000],
    'savings_temp_investments_eoy': [1000000, 500000, 200000],
    'accounts_receivable_eoy': [200000, 100000, 50000],
    'total_assets_eoy': [3000000, 1500000, 500000],
    'accounts_payable_eoy': [100000, 50000, 20000],
    'total_liabilities_eoy': [500000, 300000, 50000],
    'net_assets_eoy': [2500000, 1200000, 450000]
})
balance_data.to_sql('f9_p10_t00_balance_sheet', con, if_exists='replace', index=False)
print(f"✓ Created f9_p10_t00_balance_sheet ({len(balance_data)} rows)")

# Table 6: f9_p07_t01_compensation (Compensation details - one-to-many)
compensation_data = pd.DataFrame({
    'objectid': ['OID-202120139349301207', 'OID-202120139349301207', 'OID-202120139349301208', 
                 'OID-202120139349301208', 'OID-202120139349301209'],
    'ein': ['123456789', '123456789', '987654321', '987654321', '555555555'],
    'tax_year': [2021, 2021, 2021, 2021, 2021],
    'person_name': ['John Smith', 'Jane Doe', 'Bob Johnson', 'Alice Williams', 'Tom Brown'],
    'title': ['Executive Director', 'CFO', 'CEO', 'COO', 'Director'],
    'reportable_compensation': [150000, 120000, 100000, 90000, 75000],
    'other_compensation': [15000, 12000, 10000, 9000, 7500],
    'total_compensation': [165000, 132000, 110000, 99000, 82500]
})
compensation_data.to_sql('f9_p07_t01_compensation', con, if_exists='replace', index=False)
print(f"✓ Created f9_p07_t01_compensation ({len(compensation_data)} rows)")

# Create indexes for better query performance
print("\nCreating indexes...")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_header_ein ON f9_p00_t00_header(ein);")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_header_objectid ON f9_p00_t00_header(objectid);")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_summary_ein ON f9_p01_t00_summary(ein);")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_revenue_ein ON f9_p08_t00_revenue(ein);")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_ein ON f9_p09_t00_expenses(ein);")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_balance_ein ON f9_p10_t00_balance_sheet(ein);")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_compensation_ein ON f9_p07_t01_compensation(ein);")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_compensation_objectid ON f9_p07_t01_compensation(objectid);")
print("✓ Created 8 indexes")

con.commit()

# Verify database
print("\n" + "=" * 80)
print("Database Verification")
print("=" * 80)

tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;", con)
print(f"\nTables created: {len(tables)}")
for idx, table_name in enumerate(tables['name'], 1):
    row_count = cursor.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    print(f"  {idx}. {table_name} ({row_count} rows)")

# Show sample join query
print("\n" + "=" * 80)
print("Sample Join Query: Revenue + Expenses")
print("=" * 80)

join_query = """
    SELECT 
        h.taxpayer_name,
        r.total_revenue,
        e.total_expenses,
        (r.total_revenue - e.total_expenses) as net_income,
        b.net_assets_eoy
    FROM f9_p08_t00_revenue r
    JOIN f9_p09_t00_expenses e ON r.ein = e.ein AND r.tax_year = e.tax_year
    JOIN f9_p10_t00_balance_sheet b ON r.ein = b.ein AND r.tax_year = b.tax_year
    JOIN f9_p00_t00_header h ON r.ein = h.ein AND r.tax_year = h.tax_year
    ORDER BY r.total_revenue DESC
"""
result = pd.read_sql_query(join_query, con)
print(result.to_string(index=False))

con.close()

print("\n" + "=" * 80)
print(f"✓ Successfully created {SQLITE_DB}")
print("=" * 80)

