# Thin wrapper: serve Brussels Plumber API (03_plumber/plumber.R) on port 8000.
# From repo root: Rscript 12_end/03_serve_model.R
# From 12_end/:      Rscript 03_serve_model.R

script_arg <- commandArgs(trailingOnly = FALSE)
script_path <- sub("^--file=", "", script_arg[grepl("^--file=", script_arg)][1])
script_dir <- if (!is.na(script_path) && nzchar(script_path)) {
  dirname(normalizePath(script_path, winslash = "/", mustWork = FALSE))
} else {
  normalizePath(".", winslash = "/", mustWork = FALSE)
}

plumb_file <- file.path(script_dir, "03_plumber", "plumber.R")
if (!file.exists(plumb_file)) {
  stop("Could not find ", plumb_file)
}

plumber::plumb(plumb_file)$run(host = "0.0.0.0", port = 8000L)
