library( dplyr )        # data wrangling
library( xmltools )     # xml utilities
library( xml2 )         # xml utilities
library( XML )          # xml utilities 
library( knitr )        # formatting 
library( irs990efile )
library( DBI )
library( duckdb )
library( tictoc )
library( tidyr )

con <- dbConnect( duckdb::duckdb(), "EFILE2020.duckdb" )

# dbDisconnect(con)

dbListTables(con)

print(dbGetQuery(con, "SELECT * FROM ATTRIBUTES LIMIT 5"))
print(dbGetQuery(con, "SELECT * FROM FLATXML LIMIT 5"))

dbListFields( con, "FLATXML" )

flatxml <- tbl(con, "FLATXML")

flatxml %>% 
  filter( VARIABLE_NAME == "F9_00_TAX_YEAR" ) %>%
  count( VALUE ) %>% 
  collect()

temp <- 
  flatxml %>% 
  filter( VARIABLE_NAME == "F9_00_TAX_YEAR" ) %>%
  select( OBJECTID, VARIABLE_NAME, VALUE ) %>% 
  collect()


df <- flatxml %>% collect()

flatxml <- tbl(con, "EFILE2009.FLATXML")

summary <- 
  flatxml %>% 
  filter( TYPE == "terminal" ) %>%
  mutate( IN_CCF = (RDB_TABLE != "") ) %>%
  group_by(XPATH2) %>% 
  summarise( N=sum(IN_CCF), MISSING=sum(!IN_CCF) ) %>% 
  arrange( XPATH2 ) 

# see query
summary %>% show_query()
as.data.frame(summary) |> knitr::kable()


# Check the first few rows of each table
print(dbGetQuery(con, "SELECT * FROM FLATXML LIMIT 5"))
print(dbGetQuery(con, "SELECT * FROM ATTRIBUTES LIMIT 5"))
print(dbGetQuery(con, "SELECT * FROM KEYS LIMIT 5"))
print(dbGetQuery(con, "SELECT * FROM FAILED_URLS LIMIT 5"))


dbListTables(con)
db <- dplyr::tbl( con,  table_name )
existing_cols <- colnames(db)

flatxml <- 
  con %>%
  tbl( "FLATXML" ) %>% 
  collect() %>% 
  unique()