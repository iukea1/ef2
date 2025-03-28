###
###  Steps to Set Up an R API with DuckDB and Plumber
###


###  1. Install Required Packages

install.packages("plumber")
install.packages("duckdb")
install.packages("DBI")


###  2. Create an R Script (api.R)


library(plumber)
library(DBI)
library(duckdb)

# S3 DuckDB file path
# https://nccs-efile.s3.us-east-1.amazonaws.com/duckdb/EFILE2022B.duckdb
S3_DUCKDB_PATH <- "s3://nccs-efile/duckdb/EFILE2022B.duckdb"


#* @get /query
#* @param sql The SQL query to execute
#* @serializer json
function(sql = "SELECT * FROM FLATXML LIMIT 10") {
  con <- dbConnect(duckdb::duckdb(), dbdir = S3_DUCKDB_PATH, read_only = TRUE)
  on.exit(dbDisconnect(con))
  
  result <- dbGetQuery(con, sql)
  return(result)
}


###  3. Run the API Server

setwd( "C:/Users/jdlec/Documents/duckdb" )

library(plumber)
pr("api.R") %>%
  pr_run(port = 8000, host = "0.0.0.0")


###  4. Query the API
###     You can send a request to fetch data from DuckDB:

httr::GET( "http://localhost:8000/query", query = list(sql = "SELECT * FROM FLATXML LIMIT 5") )


# Use the official R image
FROM rocker/r-ver:latest

# Install required system dependencies
RUN apt-get update && apt-get install -y \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev

# Install R packages
RUN R -e "install.packages(c('plumber', 'DBI', 'duckdb'), repos='https://cran.r-project.org')"

# Copy API script into the container
COPY api.R /api.R

# Expose the API port
EXPOSE 8000

# Run the API
CMD ["R", "-e", "pr <- plumber::plumb('/api.R'); pr$run(host = '0.0.0.0', port = 8000)"]



###  Step 5: Create a Dockerfile
###          Save this as Dockerfile in the same directory.

# Use the official R image
FROM rocker/r-ver:latest

# Install required system dependencies
RUN apt-get update && apt-get install -y \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev

# Install R packages
RUN R -e "install.packages(c('plumber', 'DBI', 'duckdb'), repos='https://cran.r-project.org')"

# Copy API script into the container
COPY api.R /api.R

# Expose the API port
EXPOSE 8000

# Run the API
CMD ["R", "-e", "pr <- plumber::plumb('/api.R'); pr$run(host = '0.0.0.0', port = 8000)"]




###  Step 6: Build and Run the Docker Container
###
###  1. Build the Docker Image
###     Run this in your terminal:

docker build -t r-duckdb-api .




###  2. Run the Container
###     Your API will then be accessible at http://localhost:8000.

docker run -p 8000:8000 r-duckdb-api


###  Step 7: Query the API

httr::GET("http://localhost:8000/query", query = list(sql = "SELECT * FROM my_table LIMIT 5"))



###  Step 8: Deploying to a Cloud Service
###          You can deploy this Dockerized API to:
###          https://www.rplumber.io/articles/hosting.html

###  AWS ECS (Elastic Container Service)
###  Google Cloud Run
###  Azure Container Apps
###  A Kubernetes Cluster (k8s)