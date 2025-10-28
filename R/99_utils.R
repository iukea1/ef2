
#' Extract an OBJECTID from a filing URL
#'
#' Converts known IRS 990 e-file XML URLs into a standardized OBJECTID
#' (prefixed with `OID-`) used as a database key.
#'
#' @param url Character. Full XML URL.
#' @return Character scalar OBJECTID.
#' @examples
#' get_object_id2("https://nccs-efile.s3.us-east-1.amazonaws.com/xml/202220139349301207_public.xml")
#' @export
get_object_id2 <- function (url) {
  base_01 <- "https://gt990datalake-rawdata.s3.amazonaws.com/EfileData/XmlFiles/"
  base_02 <- "https://nccs-efile.s3.us-east-1.amazonaws.com/xml/"
  base_03 <- "https://nccs-efile.s3.us-east-1.amazonaws.com/xml2/2022_TEOS_XML_01A/"
  base_04 <- "https://nccs-efile.s3.us-east-1.amazonaws.com/xml2/2022_TEOS_XML_02A/"
  object.id <- gsub(paste0(base_01,"|",base_02,"|",base_03,"|",base_04), "", url)
  object.id <- gsub("_public.xml", "", object.id)
  object.id <- paste0("OID-", object.id)
  return(object.id)
}

#' Format Employer Identification Numbers (EINs)
#'
#' @description
#' Converts between numeric EINs (e.g., `"123456789"`) and standardized
#' ID-style EINs (e.g., `"EIN-12-3456789"`).
#'
#' This utility ensures EINs are properly zero-padded to nine digits and
#' formatted consistently for joining or matching across datasets.
#'
#' @param x Character or numeric vector of EINs. Can contain mixed formats
#'   (e.g., `"123456789"`, `"EIN-12-3456789"`, or `"12-3456789"`).
#' @param to Character. Direction of formatting:
#'   \describe{
#'     \item{`"id"`}{Convert to standardized EIN ID format (`"EIN-XX-XXXXXXX"`).}
#'     \item{`"n"`}{Convert to numeric-only form (digits only, no punctuation or prefix).}
#'   }
#'
#' @return A character vector of reformatted EINs.
#'
#' @examples
#' # Convert to EIN ID format
#' format_ein(c("123456789", "987654321"), to = "id")
#' #> [1] "EIN-12-3456789" "EIN-98-7654321"
#'
#' # Convert back to numeric-only
#' format_ein(c("EIN-12-3456789", "EIN-98-7654321"), to = "n")
#' #> [1] "123456789" "987654321"
#'
#' @export
format_ein <- function(x, to = "id") {
  # Ensure input is character
  x <- as.character(x)

  # Normalize and route based on target format
  if (to == "id") {
    # Keep only digits and pad to 9 characters
    x <- gsub("[^0-9]", "", x)
    x <- stringr::str_pad(x, 9, side = "left", pad = "0")

    # Split and rebuild EIN format
    sub1 <- substr(x, 1, 2)
    sub2 <- substr(x, 3, 9)
    ein  <- paste0("EIN-", sub1, "-", sub2)
    return(ein)
  }

  if (to == "n") {
    # Remove non-numeric characters
    x <- gsub("[^0-9]", "", x)
    return(x)
  }

  # Handle invalid direction argument
  stop("Invalid value for argument 'to'. Use 'id' or 'n'.")
}


#' Extract the last bracketed index from an xpath
#'
#' For an xpath like "`/Return/.../ScheduleO[3]/.../Line[12]`" returns "12".
#'
#' @param x Character scalar xpath.
#' @return Character index (defaults to "0" if none).
#' @export
get_n <- function(x) {
  matches <- stringr::str_extract_all(x, "\\[\\d+\\]")[[1]]
  if (length(matches) >= 1) {
    N <- tail(matches, 1)
    N <- stringr::str_remove_all(N, "\\[|\\]")  # <-- fixed
    return(N)
  } else {
    return("0")
  }
}

#' Make a TABLE_ID from a vector of xpaths
#'
#' @param xpaths Character vector of xpaths.
#' @return Character vector like "TID-00003".
#' @export
get_table_id <- function( xpaths ) {
  table.n <- sapply( xpaths, get_n, USE.NAMES=FALSE )
  table.n <- sprintf( "%05.0f", as.numeric(table.n) )
  table.n <- paste0( "TID-", table.n )
  return( table.n )  
}

#' Compute the TABLE_HEADER from an xpath
#'
#' @param xpath Character scalar xpath.
#' @param type One of "parent" or "terminal".
#' @return Character scalar header xpath (two-level context).
#' @export
get_header <- function( xpath, type ){
  px <- strsplit( xpath, "\\/" ) |> unlist()
  px <- px[ px != "" ]

  if( length(px) > 2 ) { hd <- px[(length(px)-2):length(px)] }
  if( length(px) <= 2 ) { hd <- px }

  if( type == "parent" )   { hd <- hd[ - 1 ] }
  if( type == "terminal" ) { hd <- hd[ - length(hd) ] }

  header <- paste0( "//", paste0( hd, collapse="/" ) )
  return(header)
}

#' Find parent node xpaths for a set of xpaths
#'
#' @param xpath_list Character vector.
#' @return Character vector of unique parent xpaths.
#' @export
find_parent_nodes <- function(xpath_list) {
  xpath_list <- sort(xpath_list)
  parent_nodes <- character()
  seen <- list()
  for (xpath in xpath_list) {
    parts <- strsplit(xpath, "/")[[1]]
    for (i in seq_len(length(parts) - 1)) {
      parent <- paste(parts[1:i], collapse = "/")
      if (!parent %in% names(seen)) {
        parent_nodes <- c(parent_nodes, parent)
        seen[[parent]] <- TRUE
      }
    }
  }
  return(unique(parent_nodes))
}

#' Find terminal node xpaths for a set of xpaths
#'
#' @param xpath_list Character vector.
#' @return Character vector of terminal xpaths.
#' @export
find_terminal_nodes <- function(xpath_list) {
  xpath_list <- sort(xpath_list)
  terminal_nodes <- c()
  for (i in seq_along(xpath_list)) {
    if (i == length(xpath_list) || !startsWith(xpath_list[i + 1], paste0(xpath_list[i], "/"))) {
      terminal_nodes <- c(terminal_nodes, xpath_list[i])
    }
  }
  return(terminal_nodes)
}

#' Classify xpaths as parent or terminal
#'
#' @param xpath Character vector of xpaths.
#' @return Character vector with values "parent" or "terminal".
#' @export
get_type <- function(xpath){
  parent_xpaths <- find_parent_nodes(xpath)
  terminal_xpaths <- find_terminal_nodes(xpath)
  type <- rep( "", length(xpath) )
  type[ xpath %in% parent_xpaths ]   <- "parent"
  type[ xpath %in% terminal_xpaths ] <- "terminal"
  return(type)
}

#' Get the last node name from an xpath
#'
#' @param x Character scalar xpath.
#' @return Character node name.
#' @export
get_xpath_vname <- function(x){
  last.x <- strsplit( x, "\\/" ) |> unlist() |> dplyr::last()
  return(last.x)
}

#' Vectorized variable name extraction from xpaths
#'
#' @param xpath Character vector.
#' @param type Character vector (ignored; reserved for future behavior).
#' @return Character vector of variable names.
#' @export
get_vnames <- function(xpath,type){
  vname <- purrr::map_chr( xpath, get_xpath_vname )
  return(vname)
}


