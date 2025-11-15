#!/usr/bin/env Rscript

# Script to connect to S3 DuckDB, extract table to CSV, and import to SQLite
# Author: EF2 Workflow
# Date: 2025-11-15

cat("=== EF2 S3 to SQLite Workflow ===\n\n")

# Install required packages if needed
required_packages <- c("duckdb", "DBI", "RSQLite", "dplyr", "tidyr", "ef2", "irs990efile")
for (pkg in required_packages) {
  if (!require(pkg, character.only = TRUE, quietly = TRUE)) {
    cat(paste0("Installing package: ", pkg, "\n"))
    install.packages(pkg, repos = "https://cloud.r-project.org")
    library(pkg, character.only = TRUE)
  }
}

cat("Step 1: Loading ef2 library...\n")
library(ef2)
library(duckdb)
library(DBI)
library(RSQLite)
library(dplyr)
library(tidyr)

cat("Step 2: Connecting to S3 DuckDB database...\n")
# Connect to the 2021 database on S3
# The database is stored at: s3://nccs-efile/duckdb/efile_v2_1/EFILE2021.duckdb
year <- 2021
filename <- paste0("EFILE", year, ".duckdb")

# Use the ef2 function to connect to S3
con <- get_s3_database(filename = filename, anonymous = TRUE)

cat("\nStep 3: Loading concordance file...\n")
# Get the concordance file which maps xpaths to table names
ccf <- get_concordance(gh = TRUE)

cat("\nStep 4: Listing available tables in the database...\n")
tables <- DBI::dbListTables(con)
cat(paste0("Available tables: ", paste(tables, collapse = ", "), "\n\n"))

cat("Step 5: Extracting a table - F9-P08-T00-REVENUE...\n")
# This is a revenue table from Form 990 Part VIII
table_name <- "F9-P08-T00-REVENUE"

# Create CSV directory if it doesn't exist
dir.create("CSV", showWarnings = FALSE, recursive = TRUE)

# Extract the table using flatten_table and add_keys
cat("  - Flattening table from XML...\n")
wide_table <- flatten_table(table_name = table_name, year = year, con = con)

cat("  - Adding key columns...\n")
wide_table <- add_keys(db_tbl = wide_table,
                       table_name = table_name,
                       year = year,
                       cc_file = ccf,
                       con = con)

cat("  - Collecting data from database...\n")
# Collect the data (this brings it into memory)
# For large tables, you might want to limit the rows
table_data <- wide_table %>%
  head(1000) %>%  # Limiting to 1000 rows for demo
  collect()

cat(paste0("  - Table has ", nrow(table_data), " rows and ", ncol(table_data), " columns\n"))

# Save to CSV
csv_filename <- paste0("CSV/", table_name, "-", year, ".csv")
cat(paste0("Step 6: Writing to CSV: ", csv_filename, "\n"))
write.csv(table_data, csv_filename, row.names = FALSE)

cat(paste0("\nCSV file created successfully: ", csv_filename, "\n"))
cat(paste0("File size: ", file.size(csv_filename), " bytes\n\n"))

# Disconnect from DuckDB
DBI::dbDisconnect(con, shutdown = TRUE)

cat("Step 7: Creating SQLite database and importing CSV...\n")
# Create SQLite database
sqlite_db <- "ef2_data.sqlite"
sqlite_con <- dbConnect(RSQLite::SQLite(), sqlite_db)

cat("  - Reading CSV file...\n")
csv_data <- read.csv(csv_filename)

cat(paste0("  - Writing to SQLite table: ", table_name, "\n"))
# Write to SQLite
dbWriteTable(sqlite_con,
             name = gsub("-", "_", table_name),  # Replace dashes with underscores for SQL
             value = csv_data,
             overwrite = TRUE)

cat("\nStep 8: Verifying data in SQLite...\n")
# Verify the data was written
table_name_sqlite <- gsub("-", "_", table_name)
row_count <- dbGetQuery(sqlite_con, paste0("SELECT COUNT(*) as count FROM ", table_name_sqlite))
cat(paste0("  - Rows in SQLite table: ", row_count$count, "\n"))

# Show first few rows
cat("\n  - Sample data from SQLite:\n")
sample_data <- dbGetQuery(sqlite_con, paste0("SELECT * FROM ", table_name_sqlite, " LIMIT 5"))
print(sample_data)

# List all tables in SQLite
cat("\n  - All tables in SQLite database:\n")
sqlite_tables <- dbListTables(sqlite_con)
cat(paste0("    ", paste(sqlite_tables, collapse = ", "), "\n"))

# Disconnect from SQLite
dbDisconnect(sqlite_con)

cat("\n=== WORKFLOW COMPLETED SUCCESSFULLY ===\n")
cat(paste0("CSV file: ", csv_filename, "\n"))
cat(paste0("SQLite database: ", sqlite_db, "\n"))
cat(paste0("SQLite table: ", table_name_sqlite, "\n"))
cat("\nYou can now query the SQLite database using:\n")
cat(paste0("  sqlite3 ", sqlite_db, "\n"))
cat(paste0("  SELECT * FROM ", table_name_sqlite, " LIMIT 10;\n"))
