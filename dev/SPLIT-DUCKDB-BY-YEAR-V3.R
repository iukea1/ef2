
factor_by_year <- function( vintage ){

  FILENAME <- paste0("EFILE", vintage, ".duckdb")
  FILEPATH <- normalizePath(FILENAME, winslash = "/", mustWork = TRUE)

  # Open the original database connection
  con_orig <- dbConnect(duckdb::duckdb(), dbdir = FILENAME, read_only = TRUE)
  dbListTables( con_orig )

  # Ensure FALED directory exists
  if( ! dir.exists("FAILED") ){ dir.create("FAILED") }

  # Write failed URL list to file
  FN.CSV <- paste0( "FAILED/FAILED-URLS-", vintage, ".CSV" )
  export_table_to_csv( con_orig, table_name="FAILED_URLS", output_csv=FN.CSV )

  # Get distinct TAX_YEAR values
  tax_years <- dbGetQuery(con_orig, "SELECT DISTINCT TAX_YEAR FROM KEYS;")$TAX_YEAR
  tax_years <- sort(tax_years)

  ROW.COUNT <- list()
  row_count <- dbGetQuery(con_orig, paste0( "SELECT COUNT(*) AS num_rows FROM KEYS;" ))
  ROW.COUNT[["TOTAL"]] <- row_count
  print( paste0( "NUMBER OF ROWS IN ", FILENAME, " KEYS: ", row_count ) )

  # Disconnect from the original database
  dbDisconnect( con_orig, shutdown = TRUE )

  # Ensure SPLITS directory exists
  if (!dir.exists("SPLITS")) { dir.create("SPLITS") }

  # Loop over each TAX_YEAR and create a subset
  for (year in tax_years) {
    print(paste("Processing TAX_YEAR:", year))

    # Define new database file
    DB_OUT   <- paste0( "SPLITS/EFILE_", year, "_FROM_", vintage, ".duckdb" )
    # PATH_OUT <- normalizePath( DB_OUT, winslash = "/", mustWork = TRUE )

    # Create a new connection for the subset database
    con_subset <- dbConnect(duckdb::duckdb(), dbdir = DB_OUT )

    # Attach the original database so we can query from it
    dbExecute(con_subset, paste0("ATTACH '", FILEPATH, "' AS orig_db;"))
    dbListTables( con_subset )

    # Create KEYS subset in the new database
    dbExecute(con_subset, paste0("
      CREATE TABLE KEYS AS 
      SELECT * FROM orig_db.KEYS WHERE TAX_YEAR = ", year, ";
    "), immediate = TRUE)

    # Create FLATXML subset in the new database
    dbExecute(con_subset, paste0("
      CREATE TABLE FLATXML AS 
      SELECT f.* FROM orig_db.FLATXML f
      JOIN KEYS k ON f.OBJECTID = k.OBJECTID;
    "), immediate = TRUE)

    # Create ATTRIBUTES subset in the new database
    dbExecute(con_subset, paste0("
      CREATE TABLE ATTRIBUTES AS 
      SELECT a.* FROM orig_db.ATTRIBUTES a
      JOIN KEYS k ON a.OBJECTID = k.OBJECTID;
    "), immediate = TRUE)

    row_count <- dbGetQuery(con_subset, paste0( "SELECT COUNT(*) AS num_rows FROM KEYS;" ))
    ROW.COUNT[[paste0("Y_",year)]] <- row_count
    print( paste0( "NUMBER OF ROWS IN ", year, " KEYS: ", row_count ) )

    # dbGetQuery(con_subset, "PRAGMA database_list;") 
    print(paste("Saved:", DB_OUT ))

    flush.console()

    # Close the subset database connection
    dbDisconnect( con_subset, shutdown = TRUE )

  }

  cat( paste0( "Original size: ", ROW.COUNT[[ "TOTAL" ]], " rows\n" ) )
  ROW.COUNT[[ "TOTAL" ]] <- NULL
  fin <- ROW.COUNT |> unlist() |> sum()
  cat( paste0( "Final size: ", fin , " rows\n" ) )

}