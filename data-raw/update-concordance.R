# data-raw/concordance.R
# Build the concordance dataset for the ef2 package.
# Run this script whenever you want to refresh the packaged data.

# Suggested deps in Imports: data.table, utils, tools
# (data.table is optional; you may use readr or base read.csv if you prefer)

# ---- Parameters ----
gh_base <- "https://raw.githubusercontent.com/"
repo    <- "Nonprofit-Open-Data-Collective/irs-efile-master-concordance-file"
branch  <- "master"
file    <- "concordance.csv"
gh_url  <- sprintf("%s%s/%s/%s", gh_base, repo, "refs/heads/master", file)

# Optional: a local fallback path (e.g., when offline)
local_fallback <- file.path("inst", "extdata", "concordance.csv")

# Ensure inst/extdata exists (so we can keep a raw copy)
usethis::use_directory("inst/extdata")

# ---- Fetch ----
message("Fetching concordance…")
tmp_csv <- tempfile(fileext = ".csv")

ok <- TRUE
tryCatch(
  utils::download.file(gh_url, tmp_csv, quiet = TRUE),
  error = function(e) { 
    message("Download failed: ", conditionMessage(e))
    ok <<- FALSE 
  }
)

if (!ok) {
  if (file.exists(local_fallback)) {
    message("Falling back to local: ", local_fallback)
    tmp_csv <- local_fallback
  } else {
    stop("Could not download concordance and no local fallback found.")
  }
}

# ---- Read & normalize ----
# Use data.table::fread for speed; switch to utils::read.csv if you prefer.
if (requireNamespace("data.table", quietly = TRUE)) {
  concordance <- data.table::fread(tmp_csv, showProgress = FALSE)
} else {
  concordance <- utils::read.csv(tmp_csv, stringsAsFactors = FALSE)
}

# Minimal column hygiene (keep names stable and lower case; adjust as needed)
names(concordance) <- tolower(names(concordance))


# ---- Save raw copy (optional) ----
# Keeping a canonical CSV in inst/extdata makes the raw content visible to users if needed.
raw_dest <- file.path("inst", "extdata", "concordance.csv")
if (tmp_csv != raw_dest) {
  file.copy(tmp_csv, raw_dest, overwrite = TRUE)
}

# ---- Write compressed package data ----
# This creates data/concordance.rda (compressed) available via `data(concordance)`
usethis::use_data(concordance, overwrite = TRUE, compress = "xz")

message("Concordance saved as package data (data/concordance.rda) and raw CSV at inst/extdata/concordance.csv")