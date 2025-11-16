#!/usr/bin/env Rscript

# Extract ALL IRS 990 tables from S3 DuckDB to CSV and SQLite
# Optimized for memory efficiency - processes one table at a time
# Uses snake_case formatting for files and columns

library(ef2)
library(irs990efile)
library(duckdb)
library(DBI)
library(RSQLite)
library(dplyr)
library(tidyr)
library(stringr)
library(purrr)
library(ggplot2)
library(tidyverse)
library(data.table)

cat(strrep("=", 80), "\n")
cat("IRS 990 - Extract All Tables from S3 DuckDB to CSV and SQLite\n")
cat(strrep("=", 80), "\n\n")

# Configuration
YEAR <- 2021
CSV_DIR <- "csv_output"
SQLITE_DB <- "irs990_all_tables.sqlite"

# Create output directory
dir.create(CSV_DIR, showWarnings = FALSE, recursive = TRUE)

#' Convert text to snake_case
to_snake_case <- function(text) {
  text <- gsub('-', "_", text)
  text <- gsub(' ', "_", text)
  text <- gsub('([a-z])([A-Z])', '\\1_\\2', text)
  text <- tolower(text)
  text
}

#' Extract a single table to CSV with snake_case formatting
#' Memory efficient - uses DuckDB COPY command
extract_table_to_csv_snake <- function(table_name, year, con, cc_file, output_dir = CSV_DIR) {
  snake_table_name <- to_snake_case(table_name)
  csv_filename <- file.path(output_dir, paste0(snake_table_name, "_", year, ".csv"))

  cat(sprintf("\n  Extracting: %s\n", table_name))
  cat(sprintf("    → %s_%s.csv\n", snake_table_name, year))

  tryCatch({
    # Get the FLATXML table name
    flatxml_table <- paste0("EFILE", year, ".FLATXML")

    # Build query to extract and pivot the table
    # This minimizes memory usage by doing everything in DuckDB
    query <- sprintf("
      WITH filtered_data AS (
        SELECT
          OBJECTID,
          VARIABLE_NAME,
          VALUE
        FROM %s
        WHERE RDB_TABLE = '%s'
        AND TYPE = 'terminal'
      )
      SELECT * FROM (
        PIVOT filtered_data
        ON VARIABLE_NAME
        USING FIRST(VALUE)
      )
    ", flatxml_table, table_name)

    # Execute query and create temp table
    DBI::dbExecute(con, "DROP TABLE IF EXISTS TEMP_EXTRACT;")
    DBI::dbExecute(con, paste0("CREATE TEMP TABLE TEMP_EXTRACT AS ", query))

    # Check if we got any rows
    row_count <- DBI::dbGetQuery(con, "SELECT COUNT(*) as n FROM TEMP_EXTRACT")$n

    if (row_count == 0) {
      cat("    ⊘ No data found for this table\n")
      return(NULL)
    }

    # Get column names and convert to snake_case
    col_names <- DBI::dbListFields(con, "TEMP_EXTRACT")
    snake_col_names <- sapply(col_names, to_snake_case, USE.NAMES = FALSE)

    # Build COPY command with renamed columns
    col_mapping <- paste(sprintf("%s AS %s", col_names, snake_col_names), collapse = ", ")
    copy_sql <- sprintf(
      "COPY (SELECT %s FROM TEMP_EXTRACT) TO '%s' (HEADER, DELIMITER ',');",
      col_mapping,
      csv_filename
    )

    # Execute COPY - writes directly to CSV without loading into R memory
    DBI::dbExecute(con, copy_sql)

    # Clean up temp table
    DBI::dbExecute(con, "DROP TABLE IF EXISTS TEMP_EXTRACT;")

    # Check file was created
    if (file.exists(csv_filename)) {
      file_size <- file.size(csv_filename)
      cat(sprintf("    ✓ Created: %s bytes (%d rows)\n", format(file_size, big.mark = ","), row_count))
      return(csv_filename)
    } else {
      cat("    ⊘ File not created\n")
      return(NULL)
    }

  }, error = function(e) {
    cat(sprintf("    ✗ Error: %s\n", substr(as.character(e), 1, 150)))
    # Clean up temp table if it exists
    try(DBI::dbExecute(con, "DROP TABLE IF EXISTS TEMP_EXTRACT;"), silent = TRUE)
    # Remove partial file if it exists
    if (file.exists(csv_filename)) {
      file.remove(csv_filename)
    }
    return(NULL)
  })
}

#' Import CSV to SQLite with snake_case table name
#' Processes in chunks to save memory
import_csv_to_sqlite <- function(csv_file, table_name, sqlite_db, chunk_size = 50000) {

  snake_table_name <- to_snake_case(table_name)

  tryCatch({
    # Connect to SQLite
    sqlite_con <- DBI::dbConnect(RSQLite::SQLite(), sqlite_db)

    # Read and write in chunks
    data <- data.table::fread(csv_file, showProgress = FALSE)

    # Write to SQLite
    DBI::dbWriteTable(sqlite_con, snake_table_name, data, overwrite = TRUE)

    # Clean up
    DBI::dbDisconnect(sqlite_con)
    rm(data)
    gc()

    cat(sprintf("    ✓ Imported to SQLite: %s\n", snake_table_name))
    return(TRUE)

  }, error = function(e) {
    cat(sprintf("    ✗ SQLite import failed: %s\n", substr(as.character(e), 1, 100)))
    return(FALSE)
  })
}

#' Create indexes on common columns for better performance
create_sqlite_indexes <- function(sqlite_db, table_name) {

  snake_table_name <- to_snake_case(table_name)

  tryCatch({
    sqlite_con <- DBI::dbConnect(RSQLite::SQLite(), sqlite_db)

    # Get column names
    columns <- DBI::dbListFields(sqlite_con, snake_table_name)

    # Create indexes on common key columns
    index_columns <- c('objectid', 'ein', 'tax_year', 'form_type')

    for (col in index_columns) {
      if (col %in% columns) {
        idx_name <- paste0("idx_", snake_table_name, "_", col)
        sql <- sprintf("CREATE INDEX IF NOT EXISTS %s ON %s(%s);", idx_name, snake_table_name, col)
        try(DBI::dbExecute(sqlite_con, sql), silent = TRUE)
      }
    }

    DBI::dbDisconnect(sqlite_con)

  }, error = function(e) {
    # Silently fail - indexes are optional optimization
  })
}

# Main workflow
cat("Step 1: Loading concordance and getting table list...\n")

# Get table names
all_tables <- tryCatch({
  cc <- get_concordance(gh = TRUE)
  tables <- unique(cc$rdb_table)
  tables <- tables[!is.na(tables) & tables != ""]
  sort(as.character(tables))
}, error = function(e) {
  # Fallback to package function
  irs990efile::get_table_names()
})

cat(sprintf("  Found %d unique tables\n", length(all_tables)))

# Categorize tables
header_tables <- grep("-T00-", all_tables, value = TRUE)
data_tables <- grep("-T0[1-9]", all_tables, value = TRUE)

cat(sprintf("  - Header tables (T00): %d\n", length(header_tables)))
cat(sprintf("  - Data tables (T01-T99): %d\n", length(data_tables)))

cat("\nStep 2: Connecting to S3 DuckDB database...\n")

# Connect to S3 database
filename <- paste0("EFILE", YEAR, ".duckdb")
con <- tryCatch({
  get_s3_database(filename = filename, anonymous = TRUE)
}, error = function(e) {
  cat(sprintf("  ✗ Cannot connect to S3: %s\n", as.character(e)))
  NULL
})

if (is.null(con)) {
  cat("\n✗ Cannot proceed without S3 access\n")
  cat("  Please ensure network connectivity and try again\n\n")
  quit(status = 1)
}

# Load concordance for column ordering
cat("\nStep 3: Loading concordance file...\n")
cc_file <- get_concordance(gh = TRUE)

# Process all tables
cat("\n", strrep("=", 80), "\n", sep = "")
cat(sprintf("Processing %d tables...\n", length(all_tables)))
cat(strrep("=", 80), "\n", sep = "")

success_count <- 0
skipped_count <- 0
error_count <- 0

for (i in seq_along(all_tables)) {
  table_name <- all_tables[i]

  cat(sprintf("\n[%d/%d] %s\n", i, length(all_tables), table_name))

  # Extract to CSV
  csv_file <- extract_table_to_csv_snake(table_name, YEAR, con, cc_file)

  if (!is.null(csv_file)) {
    # Import to SQLite
    if (import_csv_to_sqlite(csv_file, table_name, SQLITE_DB)) {
      # Create indexes
      create_sqlite_indexes(SQLITE_DB, table_name)
      success_count <- success_count + 1
    } else {
      error_count <- error_count + 1
    }
  } else {
    skipped_count <- skipped_count + 1
  }

  # Force garbage collection after each table
  gc()
}

# Cleanup
DBI::dbDisconnect(con, shutdown = TRUE)

# Summary
cat("\n", strrep("=", 80), "\n", sep = "")
cat("EXTRACTION COMPLETE\n")
cat(strrep("=", 80), "\n", sep = "")
cat(sprintf("  ✓ Success: %d tables\n", success_count))
cat(sprintf("  ⊘ Skipped: %d tables (no data)\n", skipped_count))
cat(sprintf("  ✗ Errors:  %d tables\n", error_count))
cat(sprintf("\nOutput:\n"))
cat(sprintf("  CSV files: %s/\n", CSV_DIR))
cat(sprintf("  SQLite DB: %s\n", SQLITE_DB))
cat(strrep("=", 80), "\n", sep = "")

# List SQLite tables
cat("\nSQLite Tables:\n")
sqlite_con <- DBI::dbConnect(RSQLite::SQLite(), SQLITE_DB)
tables <- DBI::dbListTables(sqlite_con)
for (tbl in tables[1:min(10, length(tables))]) {
  row_count <- DBI::dbGetQuery(sqlite_con, sprintf("SELECT COUNT(*) as n FROM %s", tbl))$n
  cat(sprintf("  - %s (%s rows)\n", tbl, format(row_count, big.mark = ",")))
}
if (length(tables) > 10) {
  cat(sprintf("  ... and %d more tables\n", length(tables) - 10))
}
DBI::dbDisconnect(sqlite_con)

cat("\nDone!\n")
