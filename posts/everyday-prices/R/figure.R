make_price_figure <- function(monthly, series) {
  if (!requireNamespace("plotly", quietly = TRUE) || !requireNamespace("htmlwidgets", quietly = TRUE)) {
    stop("Install plotly and htmlwidgets first; see README.md.")
  }
  ordered <- lapply(series$series_id, function(id) monthly[monthly$series_id == id, ])
  cumulative <- lapply(ordered, function(x) unname(x$cumulative_pct))
  annual <- lapply(ordered, function(x) unname(x$annual_pct))
  p <- plotly::plot_ly(height = 620)
  for (i in seq_len(nrow(series))) {
    x <- ordered[[i]]
    p <- plotly::add_trace(p, x = x$date, y = x$cumulative_pct, type = "scatter", mode = "lines",
      name = series$label[i], legendrank = i,
      text = paste0("<b>", series$label[i], "</b><br>", format(x$date, "%b %Y"),
        "<br>Since Dec 2019: ", sprintf("%.1f", x$cumulative_pct), "%",
        "<br>Year-over-year: ", sprintf("%.1f", x$annual_pct), "%"),
      line = list(color = series$color[i], dash = series$dash[i], width = if (i == 1L) 3 else 2.5),
      connectgaps = FALSE,
      hovertemplate = "%{text}<extra></extra>")
  }
  button <- function(label, ys, axis_title) {
    list(label = label, method = "update", args = list(list(y = ys),
      list(yaxis = list(title = list(text = axis_title), autorange = TRUE,
                        rangemode = "tozero", fixedrange = TRUE,
                        ticksuffix = "%", zeroline = TRUE, zerolinecolor = "#999999"))))
  }
  p <- plotly::layout(p, autosize = TRUE,
    title = list(text = "Everyday prices", x = 0.02, y = 0.98, yanchor = "top", font = list(size = 19)),
    font = list(family = "Arial, sans-serif", size = 13, color = "#273442"),
    paper_bgcolor = "#ffffff", plot_bgcolor = "#ffffff",
    margin = list(l = 64, r = 22, t = 125, b = 110),
    hovermode = "closest", uirevision = "price-explorer-v1",
    xaxis = list(title = "", type = "date", range = as.character(range(monthly$date)),
      tickformat = "%Y", showgrid = FALSE,
      rangeslider = list(visible = FALSE),
      rangeselector = list(x = 0.98, xanchor = "right", y = 1.13,
        buttons = list(list(step = "all", label = "Reset dates")))),
    yaxis = list(title = list(text = "Price change since Dec 2019"),
      autorange = TRUE, rangemode = "tozero", fixedrange = TRUE,
      ticksuffix = "%", gridcolor = "#e7edf2",
      zeroline = TRUE, zerolinecolor = "#999999"),
    legend = list(orientation = "h", x = 0, y = -0.17, xanchor = "left",
      itemclick = "toggle", itemdoubleclick = "toggleothers"),
    updatemenus = list(list(type = "dropdown", direction = "down", showactive = TRUE,
      x = 0, y = 1.18, xanchor = "left", yanchor = "top", active = 0,
      buttons = list(button("Since Dec 2019", cumulative, "Price change since Dec 2019"),
                     button("Year-over-year", annual, "Price change from 12 months earlier")))),
    annotations = list(list(x = 0, y = 1.02, xref = "paper", yref = "paper", xanchor = "left",
      yanchor = "bottom", showarrow = FALSE, font = list(size = 11, color = "#536372"),
      text = "U.S. CPI-U, Dec 2019 to Dec 2024")))
  plotly::config(p, displaylogo = FALSE, displayModeBar = FALSE, responsive = TRUE, scrollZoom = FALSE,
    modeBarButtonsToRemove = c("select2d", "lasso2d", "autoScale2d"),
    toImageButtonOptions = list(format = "png", filename = "everyday-prices", width = 1200, height = 700))
}
