make_price_figure <- function(monthly, series) {
  if (!requireNamespace("plotly", quietly = TRUE) || !requireNamespace("htmlwidgets", quietly = TRUE)) {
    stop("Install plotly and htmlwidgets first; see README.md.")
  }
  ordered <- lapply(series$series_id, function(id) monthly[monthly$series_id == id, ])
  cumulative <- lapply(ordered, function(x) unname(x$cumulative_pct))
  annual <- lapply(ordered, function(x) unname(x$annual_pct))
  hover <- lapply(seq_len(nrow(series)), function(i) {
    x <- ordered[[i]]
    paste0("<b>", series$label[i], "</b><br>", format(x$date, "%b %Y"),
      "<br>Since Dec 2019: ", sprintf("%.1f", x$cumulative_pct), "%",
      "<br>Year-over-year: ", sprintf("%.1f", x$annual_pct), "%")
  })

  # End-of-line labels. Endpoints closer than the gap (about 20 pixels on a desktop) are
  # nudged apart, and a short leader line joins each label to its line.
  end_date <- max(monthly$date)
  label_date <- end_date + 28  # stays before January so no "2025" tick appears
  spread_labels <- function(values) {
    ends <- vapply(values, function(v) v[length(v)], numeric(1))
    gap <- 0.055 * diff(range(c(0, unlist(values))))
    o <- order(ends)
    p <- ends[o]
    for (k in 1:200) {
      moved <- FALSE
      for (j in 2:length(p)) {
        if (p[j] - p[j - 1] < gap) {
          shift <- (gap - (p[j] - p[j - 1])) / 2
          p[j] <- p[j] + shift
          p[j - 1] <- p[j - 1] - shift
          moved <- TRUE
        }
      }
      if (!moved) break
    }
    out <- numeric(length(ends))
    out[o] <- p
    list(ends = ends, label_y = out,
         text = paste0(series$label, " ", sprintf("%.1f", ends), "%"))
  }
  labels_cumulative <- spread_labels(cumulative)
  labels_annual <- spread_labels(annual)
  label_y <- function(labels) lapply(seq_len(nrow(series)), function(i) c(labels$ends[i], labels$label_y[i]))
  label_text <- function(labels) lapply(labels$text, function(t) c("", t))

  # Titles state each view's finding, computed from the data rather than typed.
  categories <- series$label[series$role == "category"]
  ends_cumulative <- labels_cumulative$ends[series$role == "category"]
  ranked <- categories[order(ends_cumulative, decreasing = TRUE)]
  title_cumulative <- sprintf("%s rose most since Dec 2019;<br>%s and %s were next",
    ranked[1], tolower(ranked[2]), tolower(ranked[3]))
  overall <- ordered[[which(series$role == "benchmark")]]
  peak <- overall[which.max(overall$annual_pct), ]
  # Line breaks keep each title line narrow enough for a phone screen.
  title_annual <- sprintf("Overall annual inflation fell from<br>%.1f%% (%s) to %.1f%% (%s)",
    peak$annual_pct, format(peak$date, "%b %Y"),
    overall$annual_pct[nrow(overall)], format(end_date, "%b %Y"))
  title_layout <- function(text) list(text = text, x = 0.02, xanchor = "left", y = 0.985,
    yanchor = "top", font = list(size = 16))

  p <- plotly::plot_ly(height = 650)
  for (i in seq_len(nrow(series))) {
    x <- ordered[[i]]
    p <- plotly::add_trace(p, x = x$date, y = x$cumulative_pct, type = "scatter", mode = "lines",
      name = series$label[i], legendrank = i, legendgroup = series$label[i],
      text = hover[[i]],
      line = list(color = series$color[i], dash = series$dash[i], width = if (i == 1L) 3 else 2.5),
      connectgaps = FALSE,
      hovertemplate = "%{text}<extra></extra>")
  }
  # Label traces share each line's legend group, so legend clicks hide or isolate both.
  for (i in seq_len(nrow(series))) {
    p <- plotly::add_trace(p, x = c(end_date, label_date), y = label_y(labels_cumulative)[[i]],
      type = "scatter", mode = "lines+text", legendgroup = series$label[i], showlegend = FALSE,
      text = label_text(labels_cumulative)[[i]], textposition = "middle right",
      textfont = list(color = series$color[i], size = 11),
      line = list(color = series$color[i], width = 1), cliponaxis = FALSE, hoverinfo = "skip")
  }
  button <- function(label, values, labels, axis_title, title) {
    list(label = label, method = "update", args = list(
      list(y = c(values, label_y(labels)), text = c(hover, label_text(labels))),
      list(title = title_layout(title),
           yaxis = list(title = list(text = axis_title), autorange = TRUE,
                        rangemode = "tozero", fixedrange = TRUE, gridcolor = "#e7edf2",
                        ticksuffix = "%", zeroline = TRUE, zerolinecolor = "#999999"))))
  }
  p <- plotly::layout(p, autosize = TRUE,
    title = title_layout(title_cumulative),
    font = list(family = "Arial, sans-serif", size = 13, color = "#273442"),
    paper_bgcolor = "#ffffff", plot_bgcolor = "#ffffff",
    margin = list(l = 64, r = 104, t = 160, b = 110),
    hovermode = "closest", uirevision = "price-explorer-v2",
    xaxis = list(title = "", type = "date", range = as.character(c(min(monthly$date), label_date)),
      tickformat = "%Y", showgrid = FALSE,
      rangeslider = list(visible = FALSE),
      # Starts at the plot's right edge, above the label margin, so it never
      # overlaps the menu or subtitle when a phone legend shrinks the plot.
      rangeselector = list(x = 1, xanchor = "left", y = 1.26, yanchor = "top",
        buttons = list(list(step = "all", label = "Reset dates")))),
    yaxis = list(title = list(text = "Price change since Dec 2019"),
      autorange = TRUE, rangemode = "tozero", fixedrange = TRUE,
      ticksuffix = "%", gridcolor = "#e7edf2",
      zeroline = TRUE, zerolinecolor = "#999999"),
    legend = list(orientation = "h", x = 0, y = -0.17, xanchor = "left",
      itemclick = "toggle", itemdoubleclick = "toggleothers", groupclick = "togglegroup"),
    updatemenus = list(list(type = "dropdown", direction = "down", showactive = TRUE,
      x = 0, y = 1.274, xanchor = "left", yanchor = "top", active = 0,
      buttons = list(button("Since Dec 2019", cumulative, labels_cumulative,
                            "Price change since Dec 2019", title_cumulative),
                     button("Year-over-year", annual, labels_annual,
                            "Price change from 12 months earlier", title_annual)))),
    annotations = list(list(x = 0, y = 1.02, xref = "paper", yref = "paper", xanchor = "left",
      yanchor = "bottom", showarrow = FALSE, font = list(size = 11, color = "#536372"),
      text = "U.S. CPI-U, Dec 2019 to Dec 2024.<br>Labels show December 2024 values.", align = "left")))
  plotly::config(p, displaylogo = FALSE, displayModeBar = FALSE, responsive = TRUE, scrollZoom = FALSE,
    modeBarButtonsToRemove = c("select2d", "lasso2d", "autoScale2d"),
    toImageButtonOptions = list(format = "png", filename = "everyday-prices", width = 1200, height = 700))
}
