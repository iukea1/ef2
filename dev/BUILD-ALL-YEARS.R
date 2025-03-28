library( DBI )
library( duckdb )
library( dplyr )
library( dbplyr )
library( irs990efile )

wd <- "C:/Users/jdlec/Documents/duckdb"
setwd( wd )
source( "DUCKDB-TOOLS.R" )

#  - open_database()
#  - get_s3_database()
#  - build_table()
#    - flatten_table()
#    - add_keys()
#  - build_rdb_table()
#  - configure_aws_credentials() 
#  - write_csv_to_s3()


con <- get_s3_database( "EFILE2009.duckdb", anonymous=TRUE )
db <- tbl( con, "EFILE2009.FLATXML" )


all.tables <- irs990efile::get_table_names()
one.to.one.tables  <- grep( "-T00-", all.tables, value=TRUE )
one.to.many.tables <- grep( "-T0[1-9]{1}-", all.tables, value=TRUE )

ccfile <- irs990efile::get_concordance()
TABLE.HEADERS <- irs990efile::get_table_headers()



# dbSendQuery(con, "SET enable_progress_bar = true;")
# dbSendQuery(con, "SET enable_progress_bar_print = true;")
# dbGetQuery(con, "SELECT current_setting('enable_progress_bar');")
# dbGetQuery(con, "SELECT current_setting('enable_progress_bar_print');")



# Redirect standard output and messages
zz <- file( "BUILD-LOG.txt", open = "at" )
sink( zz, split = TRUE )                          
sink( zz, type = "message", append = TRUE )        

if( ! dir.exists("CSV") ){ dir.create("CSV") }

for( i in 2009:2023 ){

   print( paste0( "LOOP ", i ) )

   filename <- paste0( "EFILE", i, ".duckdb" )
   con <- get_s3_database( filename, anonymous=TRUE )

   purrr::walk( 
     one.to.one.tables, 
     build_table, 
     year=i, 
     con=con, 
     cc_file=ccfile, 
     post_to_s3=FALSE )

   cat( "-- Done building one-to-one tables\n" ) 

   purrr::walk( 
     one.to.many.tables, 
     build_rdb_table, 
     year=i, 
     TABLE.HEADERS=TABLE.HEADERS,
     con=con, 
     cc_file=ccfile, 
     post_to_s3=FALSE )

   cat( "-- Done building one-to-many tables\n\n" )  

   dbDisconnect( con, shutdown = TRUE )
   # duckdb::duckdb_shutdown( duck.driver )

}



sink(type = "message")      # Restore message output to console
sink()                      # Restore standard output
close(zz)                   # Close the file connection
file.show("BUILD-LOG.txt")  # View the logs


