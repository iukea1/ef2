# -*- coding: UTF-8 -*-
#' Inspect a DuckDB database interactively
#'
#' Lists all tables in a DuckDB file, showing their dimensions and sample
#' contents. If a specific table name is provided, previews the first `n`
#' rows from that table.
#'
#' @param db Path to a DuckDB database file (default `"EFILE2021.duckdb"`).
#' @param table Optional. Name of a table to inspect. If `NULL` (default),
#'   shows all tables with their dimensions and first 10 rows.
#' @param n Integer. Number of rows to return when inspecting a specific
#'   table (default `25`).
#'
#' @return Invisibly returns either:
#'   \itemize{
#'     \item a list of table summaries (if `table = NULL`), or
#'     \item a data frame preview (if a table is specified)
#'   }
#' @examples
#' \dontrun{
#' inspect_ddb("EFILE2021.duckdb")            # Overview of all tables
#' inspect_ddb("EFILE2021.duckdb", "FLATXML") # Preview first 25 rows
#' }
#' @export
inspect_ddb <- function(db = "EFILE2021.duckdb", table = NULL, n = 25) {
  stopifnot(file.exists(db))

  con <- DBI::dbConnect(duckdb::duckdb(), dbdir = db, read_only = TRUE)
  on.exit(DBI::dbDisconnect(con, shutdown = TRUE), add = TRUE)

  tables <- DBI::dbListTables(con)

  if (is.null(table)) {
    message("Database: ", db)
    message("Tables found: ", length(tables), "\n")

    info_list <- lapply(tables, function(tbl) {
      tryCatch({
        count_q <- sprintf('SELECT COUNT(*) AS n FROM "%s"', tbl)
        res <- DBI::dbGetQuery(con, count_q)
        n_rows <- res$n
        first  <- DBI::dbGetQuery(con, sprintf('SELECT * FROM "%s" LIMIT 10', tbl))
        list(name = tbl, rows = n_rows, cols = ncol(first), preview = first)
      }, error = function(e) {
        list(name = tbl, rows = NA, cols = NA, preview = NULL, error = e$message)
      })
    })

    for (info in info_list) {
      cat("\n--------------------------------\n")
      cat("Table:", info$name, "\n")
      cat("   Rows:", info$rows, " | Cols:", info$cols, "\n")
      if (!is.null(info$preview)) {
        print(utils::head(info$preview, 10))
      } else {
        cat("   Warning: Could not preview table.\n")
      }
    }
    invisible(info_list)

  } else {
    if (!(table %in% tables)) {
      stop("Table '", table, "' not found. Available: ",
           paste(tables, collapse = ", "))
    }

    message("Previewing table '", table, "' (first ", n, " rows):\n")
    res <- DBI::dbGetQuery(con, sprintf('SELECT * FROM "%s" LIMIT %d', table, n))
    print(res)
    invisible(res)
  }
}



#' Summarize the attribute schema from a tidy ATTRIBUTES table
#'
#' Provides a summary of attribute usage in a tidy `ATTRIBUTES` table,
#' reporting the number of occurrences, unique OBJECTIDs, and example values.
#'
#' @param attr_df Data frame produced by \code{\link{get_attr_df}()}.
#'
#' @return A data frame with one row per attribute, including:
#'   \itemize{
#'     \item \code{attr_name} - attribute name
#'     \item \code{n_records} - total number of rows containing it
#'     \item \code{n_objects} - distinct OBJECTIDs it appears in
#'     \item \code{n_unique_vals} - number of distinct values observed
#'     \item \code{example_value} - representative example value
#'   }
#'
#' @examples
#' \dontrun{
#' attrs <- get_attr_df("data/2021/EFILE2021.duckdb")
#' summarize_attr_schema(attrs)
#' }
#' @export
summarize_attr_schema <- function(attr_df) {
  stopifnot(all(c("OBJECTID", "attr_name", "attr_value") %in% names(attr_df)))

  attr_df |>
    dplyr::group_by(attr_name) |>
    dplyr::summarise(
      n_records     = dplyr::n(),
      n_objects     = dplyr::n_distinct(OBJECTID),
      n_unique_vals = dplyr::n_distinct(attr_value),
      example_value = dplyr::first(attr_value[!is.na(attr_value) & attr_value != ""]),
      .groups = "drop"
    ) |>
    dplyr::arrange(dplyr::desc(n_records))
}



#' Retrieve attribute data from a DuckDB database
#'
#' Queries the `ATTRIBUTES` table in a DuckDB database and returns
#' a tidy data frame with one row per XML node attribute.
#'
#' @param db Path to the DuckDB database file (e.g., `"EFILE2021.duckdb"`).
#' @param objectid Optional character vector of OBJECTIDs to filter by.
#'   If NULL (default), all records are returned.
#' @param url Optional character URL (used to derive OBJECTID automatically
#'   via \code{get_object_id2()}).
#' @param limit Optional integer limit on number of rows (default Inf).
#' @param read_only Logical; open connection read-only for safety (default TRUE).
#'
#' @return A tidy \code{data.frame} with columns:
#'   \itemize{
#'     \item \code{OBJECTID}
#'     \item \code{node_name}
#'     \item \code{xpath}
#'     \item \code{attr_name}
#'     \item \code{attr_value}
#'   }
#'
#' @examples
#' \dontrun{
#' get_attr_df("data/2021/EFILE2021.duckdb")
#' get_attr_df("data/2021/EFILE2021.duckdb",
#'              objectid = "OID-202323179349200212")
#' get_attr_df("data/2021/EFILE2021.duckdb",
#'              url = "https://efile...202323179349200212_public.xml")
#' }
#' @export
retrieve_attr_df <- function(db,
                        objectid = NULL,
                        url = NULL,
                        limit = Inf,
                        read_only = TRUE) {

  stopifnot(file.exists(db))

  if (!is.null(url)) {
    objectid <- get_object_id2(url)
  }

  con <- DBI::dbConnect(duckdb::duckdb(), dbdir = db, read_only = read_only)
  on.exit(DBI::dbDisconnect(con, shutdown = TRUE), add = TRUE)

  sql <- "SELECT OBJECTID, node_name, xpath, attr_name, attr_value FROM ATTRIBUTES"

  if (!is.null(objectid)) {
    obj_vec <- paste(sprintf("'%s'", objectid), collapse = ", ")
    sql <- sprintf("%s WHERE OBJECTID IN (%s)", sql, obj_vec)
  }

  if (is.finite(limit)) {
    sql <- sprintf("%s LIMIT %d", sql, limit)
  }

  attr_df <- DBI::dbGetQuery(con, sql)
  return(attr_df)
}



#' Summarize attribute structure from a DuckDB database
#'
#' Convenience wrapper that reads the `ATTRIBUTES` table from a DuckDB
#' database and summarizes its contents using
#' \code{\link{summarize_attr_schema}()}. The result provides a compact
#' overview of all attribute names, their frequencies, and example values.
#'
#' @param db_name Path to a DuckDB database file (e.g., `"EFILE2021.duckdb"`).
#'
#' @return A tidy \code{data.frame} summarizing attribute usage, typically
#'   including columns such as:
#'   \itemize{
#'     \item \code{attr_name} - the attribute name
#'     \item \code{n_records} - number of occurrences across all nodes
#'     \item \code{n_objects} - number of unique OBJECTIDs containing it
#'     \item \code{n_unique_vals} - number of distinct values observed
#'     \item \code{example_value} - representative example value
#'   }
#'
#' @examples
#' \dontrun{
#' summarize_attr_table("data/2021/EFILE2021.duckdb")
#' }
#' @seealso \code{\link{get_attr_df}}, \code{\link{summarize_attr_schema}}
#' @export
summarize_attr_table <- function(db_name) {
  db_name |>
    retrieve_attr_df() |>
    summarize_attr_schema()
}