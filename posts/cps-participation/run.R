here::i_am("posts/cps-participation/run.R")
post_dir <- here::here("posts", "cps-participation")
source(file.path(post_dir, "R", "analysis.R"))
run_analysis(post_dir)
