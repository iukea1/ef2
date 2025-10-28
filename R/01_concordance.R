
#' Retrieve the Concordance File
#'
#' Downloads the master concordance file from GitHub or loads a packaged version.
#'
#' @param gh Logical; if TRUE, fetches the concordance from GitHub.
#' @return A data.table or data.frame containing the concordance.
#' @export
get_concordance <- function( gh=TRUE ){
  concordance <- NULL
  if( gh ){
    base <- "https://raw.githubusercontent.com/"
    gh.id <- "Nonprofit-Open-Data-Collective/"
    rn <- "irs-efile-master-concordance-file/refs/heads/master/"
    fn <- "concordance.csv"
    url <- paste0( base, gh.id, rn, fn )
    utils::download.file( url, fn, quiet = TRUE )
    concordance <- data.table::fread( fn, showProgress = FALSE )
  }
  if( is.null(concordance) || ! gh ){ utils::data(concordance, package = "ef2", envir = environment()) }
  return( concordance )
}

#' Prepare a concordance crosswalk (uppercase colnames)
#'
#' @param ccf Optional concordance; if NULL, loads via `get_concordance()`.
#' @return Data frame with columns XPATH, VARIABLE_NAME, RDB_TABLE.
#' @export
prep_concordance <- function( ccf=NULL ){
  if( is.null(ccf) ){ ccf <- get_concordance() }
  ccf <- as.data.frame( ccf )
  ccf <- ccf[c("xpath","variable_name","rdb_table")]
  names(ccf) <- toupper(names(ccf))
  return(ccf)
}
