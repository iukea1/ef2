# Function to check if a table exists and write it to CSV
export_table_to_csv <- function(con, table_name, output_csv) {

  # Check if the table exists
  table_exists <- 
   dbGetQuery( con, 
     paste0(  "SELECT COUNT(*) AS count FROM information_schema.tables 
               WHERE table_name = '", table_name, "';"
     ))$count > 0

  # If the table exists, export it to CSV
  if (table_exists) {
    
    # Fetch table data
    df <- dbGetQuery(con, paste0("SELECT * FROM ", table_name, ";"))
    
    # Write to CSV
    write.csv( df, output_csv, row.names = FALSE )
    
    print(paste("Table", table_name, "exported"))
  } 
}


library( dplyr )
library( dbplyr )

tbl <- tbl( con, "efile.FAILED_URLS" )


