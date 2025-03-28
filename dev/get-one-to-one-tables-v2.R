library(DBI)
library(duckdb)
library(dplyr, warn.conflicts = FALSE)
library(dbplyr, warn.conflicts = FALSE)

# Connect to DuckDB database
con <- dbConnect(duckdb::duckdb(), dbdir = "EFILE2025.duckdb")

# Reference the DuckDB table using `tbl()`
flatxml <- tbl(con, "FLATXML")


dbListFields( con, "FLATXML" )

flatxml %>% 
  filter( VARIABLE_NAME == "F9_00_TAX_YEAR" ) %>%
  count( VALUE ) %>% 
  collect()


# Query the first matching value using `dplyr`
F9_01_EXP_BEN_PAID_MEMB_CY <- 
  flatxml %>%
  filter(xpath %in% possible_xpaths) %>%
  select(value) %>%
  collect() %>%  # Executes query and returns data in R
  slice_head(n = 1) %>%
  pull(value)


# Define possible XPaths
possible_xpaths <- c(
  "/Return/ReturnData/IRS990/BenefitsPaidToMembersCY",
  "/Return/ReturnData/IRS990/CYBenefitsPaidToMembersAmt",
  "/Return/ReturnData/IRS990/Form990PartI/BenefitsPaidToMembersCurrYear",
  "/Return/ReturnData/IRS990EZ/BenefitsPaidToOrForMembers",
  "/Return/ReturnData/IRS990EZ/BenefitsPaidToOrForMembersAmt"
)

# Query the first matching value using `dplyr`
F9_01_EXP_BEN_PAID_MEMB_CY <- xml_tbl %>%
  filter(xpath %in% possible_xpaths) %>%
  select(value) %>%
  collect() %>%  # Executes query and returns data in R
  slice_head(n = 1) %>%
  pull(value)

# Print result
print(F9_01_EXP_BEN_PAID_MEMB_CY)

# Disconnect from DuckDB
dbDisconnect(con, shutdown = TRUE)