library(DBI)
library(duckdb)
library(dplyr)
library(dbplyr)


open_database <- function( s3_region = "us-east-1", anonymous = TRUE ) {
  # Start an in-memory DuckDB connection
  duck.driver <- duckdb::duckdb()
  con <- dbConnect( duck.driver, dbdir = ":memory:" )

  # Load the HTTPFS extension for S3 support
  dbExecute(con, "INSTALL httpfs; LOAD httpfs;")

  # Configure S3 access
  dbExecute(con, paste0("SET s3_region='", s3_region, "';"))
  dbExecute(con, "SET s3_endpoint='s3.amazonaws.com';")

  # Enable anonymous access if needed
  if (anonymous) {
    dbExecute(con, "SET s3_access_key_id='';")
    dbExecute(con, "SET s3_secret_access_key='';")
  }

  return(con)
}


get_s3_database <- function( filename, anonymous=TRUE ){

  s3_base <- "s3://nccs-efile/duckdb/"
  s3_path <- paste0( s3_base, filename )
  con <- open_database( anonymous )
  
  dbname <- gsub( "\\.duckdb", "", filename )
  print( paste0( "Attached Database: ", dbname ) )
  
  SQL <- paste0( "ATTACH '", s3_path, "' AS ", dbname, ";" )  
  dbExecute( con, SQL )
  
  table.names <- dbListTables(con)
  print( paste0("Table Names: ", paste0(table.names, collapse="; ") ) )
  
  SQL <- paste0( "SELECT count(*) AS num_rows FROM ", dbname, ".KEYS;" )
  n_rows <- dbGetQuery( con, SQL )
  print( paste0( "Unique Returns: ", format(n_rows,big.mark=",") ) )
  
  return( con )
}




#  con <- get_s3_database( filename = "EFILE2009.duckdb" )
# 
#  dbDisconnect( con, shutdown = TRUE )
#  duckdb::duckdb_shutdown( duck.driver )






########
########      EFILE TABLES 
########


db <- tbl( con, "EFILE2009.FLATXML" )

db %>% pull(RDB_TABLE) %>% unique() %>% sort()

table_freq <- 
  flatxml %>% 
  filter( TYPE == "terminal" ) %>%
  filter( RDB_TABLE != "" ) %>%
  group_by(RDB_TABLE) %>% 
  summarise( N=n() ) %>% 
  arrange( desc(N) ) 

table_freq %>% as.data.frame() %>% knitr::kable()




####
####   ONE-TO-ONE TABLES 
####


add_keys <- function( db_tbl, table_name,  year, cc_file, con ){
 
  keys <- tbl( con, paste0( "EFILE", year, ".KEYS" ) )
  db_tbl <- right_join( keys, db_tbl, by="OBJECTID" )

  new.order <- 
    cc_file %>%
    filter( rdb_table == table_name ) %>%
    arrange( location_code_family, xpath ) %>%
    pull( variable_name ) %>%
    unique() 

  new.order <- new.order[ new.order %in% colnames(db_tbl) ]
  key.names <- colnames(keys)

  db_tbl <- 
    db_tbl %>% 
    dplyr::relocate( c( key.names, new.order ) ) 

  print( paste0( "TABLE: ", table_name ) )
  print( colnames(db_tbl) )

  return( db_tbl )
}

flatten_table <- function( table_name, year, con ){

  fn <- paste0( "EFILE", year, ".FLATXML" )
  db <- tbl( con, fn  )

  wide_00 <- 
    db %>%
    filter( TYPE == "terminal" ) %>% 
    filter( RDB_TABLE == table_name ) %>%
    select(  OBJECTID, VARIABLE_NAME, VALUE ) %>%
    tidyr::pivot_wider( 
      names_from = VARIABLE_NAME, 
      values_from = VALUE,
      values_fill = "" ) 

  return( wide_00 )
}







year <- 2009
table.name <- "F9-P01-T00-SUMMARY"
ccfile <- irs990efile::get_concordance()

t00 <- flatten_table( table.name, year, con )

t00 <- 
  add_keys( 
    db_tbl=t00, 
    table_name=table.name, 
    year=year, 
    cc_file=ccfile )

# write_csv_to_s3( db_tbl=t00, table.name, year )

t00 <- collect( t00 )
fn <- paste0( "CSV/", table.name, "-", year, ".CSV" ) 
data.table::fwrite( t00, fn )




#######    ALL TOGETHER

build_table <- function( table.name, year, con, ccfile, post_to_s3=TRUE ){

  wide_00 <- flatten_table( table_name=table.name, year=year, con=con )

  wide_00 <- 
    add_keys( db_tbl=wide_00, 
              table_name=table.name, 
              year=year, 
              cc_file=ccfile,
              con=con )
  
  if( post_to_s3 )
  { write_csv_to_s3( db_tbl=wide_00, table.name, year ) }

  if( ! post_to_s3 ) {
    fpath <- paste0( "CSV/", table.name, "-", year, ".CSV" ) 
    wide_00 %>% compute( "TEMP", temporary=TRUE, overwrite=TRUE )
    SQL <- paste0(   "COPY TEMP TO '", fpath, 
                    "' WITH (HEADER, DELIMITER ',');"  )
    dbExecute( con, SQL )
  }

  return( invisible(wide_00) )
}

t00 <- build_table( table.name, year, con, ccfile )

### 

all.tables <- db %>% pull(RDB_TABLE) %>% unique() %>% sort()
one.to.one.tables  <- grep( "-T00-", all.tables, value=TRUE )
one.to.many.tables <- grep( "-T0[1-9]{1}-", all.tables, value=TRUE )
if( ! dir.exists("CSV") ){ dir.create("CSV") }


year <- 2009

purrr::walk( 
  one.to.one.tables, 
  build_table, year=year, 
  con=con, ccfile=ccfile, 
  post_to_s3=FALSE )




####
####   ONE-TO-MANY TABLES 
####


build_rdb_table <- function( table.name, year, TABLE.HEADERS, con, ccfile, post_to_s3=FALSE ) {

  hd <- TABLE.HEADERS[[ table.name ]]
  hd <- gsub( "//", "/", hd )
  xpath.versions <- paste0( hd, collapse="|" )

  db <- tbl( con, paste0( "EFILE", year, ".FLATXML" ) )

  wide_xx <- 
    db %>%
    filter( grepl( xpath.versions, XPATH2 ) ) %>%
    filter( TYPE == "terminal" ) %>% 
    # filter( RDB_TABLE == table.name ) %>%
    select(  OBJECTID, TABLE_ID, VARIABLE_NAME, VALUE ) %>%
    tidyr::pivot_wider( 
      names_from = VARIABLE_NAME, 
      values_from = VALUE,
      values_fill = "" )  

  keys <- tbl( con, paste0( "EFILE", year, ".KEYS" ) )
  key.names <- colnames(keys)

  wide_xx <- right_join( keys, wide_xx, by="OBJECTID" )

  new.order <- 
    ccfile %>%
    filter( rdb_table == table.name ) %>%
    arrange( location_code_family, xpath ) %>%
    pull( variable_name ) %>%
    unique() 

  new.order <- new.order[ new.order %in% colnames(wide_xx) ]

  wide_xx <- 
    wide_xx %>% 
    dplyr::relocate( c( key.names, "TABLE_ID", new.order ) ) 

  if( post_to_s3 )
  { write_csv_to_s3( db_tbl=wide_xx, table.name, year ) }

  if( ! post_to_s3 ) {
    fpath <- paste0( "CSV/", table.name, "-", year, ".CSV" ) 
    wide_xx %>% compute( "TEMP", temporary=TRUE, overwrite=TRUE )
    SQL <- paste0(   "COPY TEMP TO '", fpath, 
                    "' WITH (HEADER, DELIMITER ',');"  )
    dbExecute( con, SQL )
  }

  return(invisible(wide_xx))
}



TABLE.HEADERS <- irs990efile::get_table_headers()
ccfile <- irs990efile::get_concordance()
year <- 2009
table.name <- "SR-P02-T01-ID-RLTD-TAX-EXEMPED-ORGS"

build_rdb_table( table.name, year, TABLE.HEADERS, con, ccfile, post_to_s3=FALSE )




all.tables <- db %>% pull(RDB_TABLE) %>% unique() %>% sort()
one.to.many.tables <- grep( "-T0[1-9]{1}-", all.tables, value=TRUE )

if( ! dir.exists("CSV") ){ dir.create("CSV") }


purrr::walk( 
  one.to.many.tables, 
  build_rdb_table, 
  year=year, 
  TABLE.HEADERS=TABLE.HEADERS,
  con=con, ccfile=ccfile, 
  post_to_s3=FALSE )






##  To write CSV files directly to S3:
##    make sure AWS credentials are
##    already installed on your machine

##  CREATE TOKENS: 
##  in windows cmd / powershell:   aws sts get-session-token
##
##  Sys.setenv("AWS_ACCESS_KEY_ID" = "xxxxxx",
##             "AWS_SECRET_ACCESS_KEY" = "xxxxxxx",
##             "AWS_DEFAULT_REGION" = "us-east-1",
##             "AWS_SESSION_TOKEN" = "xxxxxxx" )
##
##   locate_credentials()  # aws.signature package

dbDisconnect( con, shutdown = TRUE )
duckdb::duckdb_shutdown( duck.driver )

con <- "EFILE2009.duckdb" %>% get_s3_database( anonymous=FALSE )


configure_aws_credentials <- function(){

  credentials <- aws.signature::locate_credentials()
  SET_KEY    <- paste0( "SET s3_access_key_id='",     credentials$key,           "';" )
  SET_SECRET <- paste0( "SET s3_secret_access_key='", credentials$secret,        "';" )
  SET_TOKEN  <- paste0( "SET s3_session_token='",     credentials$session_token, "';" )

  dbExecute( con, SET_KEY    )
  dbExecute( con, SET_SECRET )
  dbExecute( con, SET_TOKEN  )  
  dbExecute( con, "SET s3_region='us-east-1';" ) 

}


year <- 2009

write_csv_to_s3 <- function( db_tbl, table.name, year ){

  fn <- paste0( table.name, "-", year, ".CSV" )
  s3_csv_base <- "s3://nccs-efile/public/v2025_03/"
  s3_csv_path <- paste0( s3_csv_base, fn ) 

  db_tbl %>% compute( "TEMP", temporary=TRUE )

  SQL <- paste0(   "COPY TEMP TO '", s3_csv_path, 
                   "' WITH (HEADER, DELIMITER ',');"  )

  dbExecute( con, SQL )
}


url <- "https://nccs-efile.s3.us-east-1.amazonaws.com/public/v2025_03/"
df  <- data.table::fread( paste0( url, fn ) ) 






#############################################################
#############################################################
#############################################################




  
# Define the S3 DuckDB file path
s3_path <- "s3://nccs-efile/duckdb/EFILE2009.duckdb"

# Open the DuckDB connection
con <- open_database( s3_region = "us-east-1", anonymous = TRUE )

# Attach the remote DuckDB file from S3 (THIS IS THE CORRECT WAY TO ACCESS IT)
dbExecute( con, paste0("ATTACH '", s3_path, "' AS efile;") )

# List tables to confirm update
dbListTables(con)

# Number of rows
dbGetQuery(con, "SELECT count(*) AS num_rows FROM efile.FLATXML;")

qry <- 
  "SELECT XPATH2, count(*) 
   FROM efile.FLATXML
   GROUP BY XPATH2"

dbGetQuery( con, qry )


library( dbplyr )
library( dplyr )
library( tidyr )
library( DBI )

df <- tbl( con, "efile.FLATXML" )

df %>% pull(OBJECTID) %>% unique() %>% length()

t <- 
  df %>%
  group_by( XPATH2 ) %>%
  summarize( n=n() ) %>%
  collect()

t %>% arrange( XPATH2 ) %>% data.table::fwrite( "XPATH2.CSV" )

# Disconnect when done
# dbDisconnect(con)






# Reference the DuckDB table
db <- tbl( con, "efile.FLATXML" )



# Transform the data using dbplyr

db2 <- 
  db %>%
  filter( TYPE == "terminal" ) %>% 
  filter( RDB_TABLE == "F9-P07-T01-COMPENSATION" ) %>%
  select(  OBJECTID, TABLE_ID, VARIABLE_NAME, VALUE ) %>%
  pivot_wider( 
    names_from = VARIABLE_NAME, 
    values_from = VALUE,
    values_fill = "" ) %>%
  select( -(TABLE_ID) )
 
w <- 
  db2 %>%
  collect() 

# OR bring data into R memory before using pivot_wider()

db2 <- 
  db %>%
  filter( TYPE == "terminal" ) %>% 
  filter( RDB_TABLE == "F9-P07-T01-COMPENSATION" ) %>%
  select(  OBJECTID, TABLE_ID, VARIABLE_NAME, VALUE )

w <- 
  db2 %>%
  collect() %>%   # Collect the result into an in-memory dataframe
  pivot_wider(names_from = VARIABLE_NAME, values_from = VALUE, values_fill = "")

dim( w )
names( w )
head( as.data.frame( w ) )

nm.ord <- 
  ccf %>%
  arrange( rdb_table, xpath ) %>%
  pull( variable_name ) %>%
  unique() 

# Save back to DuckDB
dbWriteTable( con, "TEMP", w, overwrite = TRUE )

# List tables to confirm new table exists
dbListTables(con)

# Reference the two tables
wide <- tbl(con, "memory.TEMP")
keys <- tbl(con, "efile.KEYS")
flat <- tbl(con, "efile.FLATXML")
atts <- tbl(con, "efile.ATTRIBUTES")

colnames(flat)
colnames(keys)
colnames(atts)

# Perform the join directly in DuckDB
m <- wide %>% left_join( keys, by = "OBJECTID" ) 

# Now, recreate the table
m %>% compute( name = "WIDE", temporary = FALSE )

# List tables to confirm update
dbListTables(con)

# Ensure DuckDB does not block table creation due to existing table
dbExecute(con, "DROP TABLE IF EXISTS TEMP")

# Disconnect when done
dbDisconnect(con)







# Reference the DuckDB table
db <- tbl( con, "efile.FLATXML" )

db %>% group_by( RDB_TABLE ) %>% summarize( n=n() ) %>% as.data.frame() %>% knitr::kable()

colnames( db )


# Transform the data using dbplyr
# Drop TABLE_ID for one-to-one tables

db2 <- 
  db %>%
  filter( TYPE == "terminal" ) %>% 
  filter( RDB_TABLE == "F9-P00-T00-HEADER" ) %>%
  select(  OBJECTID, VARIABLE_NAME, VALUE ) %>%
  pivot_wider( 
    names_from = VARIABLE_NAME, 
    values_from = VALUE,
    values_fill = "" )  
 
w <- 
  db2 %>%
  collect() 

head( as.data.frame(w) )


# Save back to DuckDB
dbWriteTable( con, "TEMP", w, overwrite = TRUE )

# List tables to confirm new table exists
dbListTables(con)

# Reference the two tables
wide <- tbl(con, "memory.TEMP")
keys <- tbl(con, "efile.KEYS")

# Perform the join directly in DuckDB
m <- wide %>% left_join( keys, by = "OBJECTID" ) 

# Now, recreate the table
m %>% compute( name = "F9-P00-T00-HEADER", temporary = FALSE )

# List tables to confirm update
dbListTables(con)

# Ensure DuckDB does not block table creation due to existing table
dbExecute(con, "DROP TABLE IF EXISTS TEMP")

# Faster - does not load table to memory 
dbExecute( con, "COPY 'F9-P00-T00-HEADER' TO 'p0-header.csv' (HEADER, DELIMITER ',')")

#  Load table into R
#  df <- tbl(con, "WIDE") %>% collect()
#  Write to CSV
#  write_csv(df, "wide_export.csv")

# Disconnect when done
dbDisconnect(con)






#######################



df2 <-   
  df %>%
  filter( TYPE == "terminal" ) %>%
  filter( RDB_TABLE == "SJ-P01-T00-COMPENSATION" ) %>%
  select( OBJECTID, VARIABLE_NAME, VALUE ) %>%
  pivot_wider(
    names_from = VARIABLE_NAME, 
    values_from = VALUE,
    values_fill = "" ) %>%
  show_query()
  


qyr <- 
  "SELECT *
   FROM (
     SELECT Store, Month, Sales
     FROM df_long
   ) AS SourceTable
   PIVOT (
     SUM(Sales) 
     FOR Month IN ([Jan], [Feb], [Mar], [Apr], [May], [Jun], [Jul], [Aug], [Sep], [Oct], [Nov], [Dec])
   ) AS PivotTable;"



# Verify that tables are created
dbListTables(con)

# Check the first few rows of each table
print(dbGetQuery(con, "SELECT * FROM FLATXML LIMIT 5"))
print(dbGetQuery(con, "SELECT * FROM ATTRIBUTES LIMIT 5"))
dbGetQuery(con, "SELECT * FROM efile.KEYS LIMIT 5") %>% as.data.frame()




# If tables exist, replace 'efile_table' with an actual table name
if (nrow(tables) > 0) {
  table_name <- tables$table_name[1]  # Use the first table for testing
  query <- paste0("SELECT * FROM efile_db.", table_name, " LIMIT 10;")
  df <- dbGetQuery(con, query)
  print(df)
} else {
  print("No tables found in the database.")
}

# Disconnect when done
dbDisconnect(con)