TN <- "SI-P02-T01-GRANTS-US-ORGS-GOVTS"
dd <- get_rdb_many( table.name=TN, con )


get_rdb_many <- function( table.name, con ){

  # Reference the DuckDB table
  db <- tbl( con, "efile.FLATXML" )

  TABLE.HEADERS <- irs990efile::get_table_headers()

  hd <- TABLE.HEADERS[[ table.name ]]
  hd <- gsub( "//", "/", hd )
  all <- paste0( hd, collapse="|" )

  dft <- 
    db %>%
    filter( grepl( all, XPATH2 ) ) %>%
    filter( TYPE == "terminal" ) %>% 
    filter( RDB_TABLE == table.name ) %>%
    select(  OBJECTID, TABLE_ID, VARIABLE_NAME, VALUE ) %>%
    pivot_wider( 
      names_from = VARIABLE_NAME, 
      values_from = VALUE,
      values_fill = "" )  

  tb <- 
    dft %>%
    collect() 

  ccf <- irs990efile::get_concordance()

  new.order <- 
    ccf %>%
    filter( rdb_table == table.name ) %>%
    arrange( xpath ) %>%
    pull( variable_name ) %>%
    unique() 

  tb <- tb[ c("OBJECTID",new.order) ]

    return(tb)
}



KEYS
FLATXML
ATTRIBUTES


