library(devtools)

usethis::create_package( "ef2" )


# -------------


setwd( "ef2" )
devtools::document()


setwd( ".." )
devtools::install( "ef2", dependencies=FALSE )


# -------------


library( ef2 )


# to update concordance

source("data-raw/update-concordance.R")