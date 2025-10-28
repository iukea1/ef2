library( irs990efile )
library( ef2 )

PATH <- "C:/Users/jdlec/DATA/DUCKDB_2025"


###
###    2024
###

YEAR <- 2024
index_y <- readRDS( paste0( PATH,"/index/index",YEAR,".rds" ) )
URLS <- index_y$URL

build_database( 
  year=YEAR, 
  urls = URLS, 
  group.size = 25,
  ccf = NULL, 
  path = PATH )

###
###    2023
###

YEAR <- 2023
index_y <- readRDS( paste0( PATH,"/index/index",YEAR,".rds" ) )
URLS <- index_y$URL

build_database( 
  year=YEAR, 
  urls = URLS, 
  group.size = 25,
  ccf = NULL, 
  path = PATH )


###
###    2022
###

YEAR <- 2022
index_y <- readRDS( paste0( PATH,"/index/index",YEAR,".rds" ) )
URLS <- index_y$URL

build_database( 
  year=YEAR, 
  urls = URLS, 
  group.size = 25,
  ccf = NULL, 
  path = PATH )



###
###    2021
###

YEAR <- 2021
index_y <- readRDS( paste0( PATH,"/index/index",YEAR,".rds" ) )
URLS <- index_y$URL

build_database( 
  year=YEAR, 
  urls = URLS, 
  group.size = 25,
  ccf = NULL, 
  path = PATH )


###
###    2020
###

YEAR <- 2020
index_y <- readRDS( paste0( PATH,"/index/index",YEAR,".rds" ) )
URLS <- index_y$URL

build_database( 
  year=YEAR, 
  urls = URLS, 
  group.size = 25,
  ccf = NULL, 
  path = PATH )


###
###    2019
###

YEAR <- 2019
index_y <- readRDS( paste0( PATH,"/index/index",YEAR,".rds" ) )
URLS <- index_y$URL

build_database( 
  year=YEAR, 
  urls = URLS, 
  group.size = 25,
  ccf = NULL, 
  path = PATH )





###
###    INSPECT DB AFTER COMPLETE
###

YEAR <- 2021

inspect_ddb( paste0(YEAR,"/EFILE",YEAR,".duckdb") )

# get specific table:

flatxml <- inspect_ddb( paste0(YEAR,"/EFILE",YEAR,".duckdb"), "FLATXML", n=1000 )
flatxml$XPATH2





