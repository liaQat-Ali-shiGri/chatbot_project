"""Graph generation with plotly (FR20).

Builds the seven dashboard graphs as plotly figures from the computed chart
data. The browser renders them with plotly.js, so they stay interactive
(hover values, legend toggles, zoom).
"""
import json
import plotly.graph_objects as go

# Colour-blind-safe categorical palette; each topic keeps its slot in every scope.
THEMES = {
    "light": {"series": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"],
              "ink": "#52514e", "grid": "#e1e0d9", "surface": "#ffffff"},
    "dark": {"series": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300"],
             "ink": "#c3c2b7", "grid": "#2c2c2a", "surface": "#1e1e1e"},
}
STATUS_COLORS = {"correct": "#0ca30c", "partial": "#fab219", "incorrect": "#d03b3b"}
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
# plotly's default style is the same in every figure, so it is sent to the browser once, not in each graph.
TEMPLATE = json.loads(go.Figure().to_json())["layout"]["template"]


def topic_colors(topics, theme_name):
    """Colour of each topic, the same in the graphs and the topic-based performance cards"""
    return dict(zip(topics, THEMES[theme_name]["series"]))


def _finish(fig, theme, legend=False, x=None, y=None, legend_on_top=False):
    """Apply the shared dashboard style and return a JSON-ready figure without the shared template"""
    legend_y = {"y": 1.02, "yanchor": "bottom"} if legend_on_top else {"y": -0.12, "yanchor": "top"}
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": FONT, "color": theme["ink"], "size": 12},
        margin={"l": 52, "r": 16, "t": 20, "b": 8},
        showlegend=legend,
        legend={"orientation": "h", "x": 0.5, "xanchor": "center", "traceorder": "normal", **legend_y},
        barcornerradius=4,
        bargap=0.3,
    )
    if x is not None:
        fig.update_xaxes(**{"showgrid": False, "zeroline": False, "linecolor": theme["grid"], "automargin": True, **x})
    if y is not None:
        fig.update_yaxes(**{"gridcolor": theme["grid"], "zeroline": False, "automargin": True, **y})
    figure = json.loads(fig.to_json())
    del figure["layout"]["template"]
    return figure


def _whole_ticks(count, limit, many=None):
    # Whole-number ticks, one per value when there are few, so no rounded label repeats.
    return {"tickformat": "d", **({"dtick": 1} if count <= limit else many or {})}


def _count_axis(max_count):
    return {"rangemode": "tozero", **_whole_ticks(max_count, 6)}


def _pie(labels, values, colors, theme, unit):
    fig = go.Figure(go.Pie(
        labels=labels, values=values, sort=False, direction="clockwise",
        marker={"colors": colors, "line": {"color": theme["surface"], "width": 2}},
        textinfo="percent", textfont={"color": "#ffffff"},
        hovertemplate=f"%{{label}}: %{{value}} {unit} (%{{percent}})<extra></extra>",
    ))
    return _finish(fig, theme, legend=True)


def _bar(labels, values, theme, hover, y, x_title):
    fig = go.Figure(go.Bar(x=labels, y=values, marker={"color": theme["series"][0]}, hovertemplate=hover))
    return _finish(fig, theme, x={"type": "category", "title": x_title}, y=y)


def _horizontal_bar(labels, values, theme, hover, x):
    # Horizontal bars keep long category names readable.
    fig = go.Figure(go.Bar(x=values, y=labels, orientation="h", marker={"color": theme["series"][0]},
                           hovertemplate=hover))
    return _finish(fig, theme, x={"showgrid": True, "gridcolor": theme["grid"], "zeroline": False, **x},
                   y={"showgrid": False, "autorange": "reversed"})


def _line(x_values, y_values, theme, hover, x, y, customdata=None):
    fig = go.Figure(go.Scatter(
        x=x_values, y=y_values, customdata=customdata, mode="lines+markers", connectgaps=False, cliponaxis=False,
        line={"color": theme["series"][0], "width": 2},
        marker={"size": 8, "color": theme["series"][0], "line": {"color": theme["surface"], "width": 2}},
        hovertemplate=hover,
    ))
    return _finish(fig, theme, x=x, y=y)


def build_figures(chart_data, colors, theme_name="light"):
    """All seven FR20 graphs, keyed like the chart data; colors maps each topic to its colour"""
    theme = THEMES[theme_name]
    percent_axis = {"range": [0, 100], "ticksuffix": "%"}

    topic_dist = chart_data["topic_distribution"]
    correctness = chart_data["correctness_per_reply"]
    stacked = go.Figure([
        go.Bar(
            name=series["name"], x=correctness["labels"], y=series["values"],
            marker={"color": STATUS_COLORS[series["key"]], "line": {"color": theme["surface"], "width": 2}},
            hovertemplate=f"Turn %{{x}}: %{{y}} {series['name'].lower()}<extra></extra>",
        )
        for series in correctness["series"]
    ])
    stacked.update_layout(barmode="stack")
    stack_max = max(map(sum, zip(*(series["values"] for series in correctness["series"]))), default=0)

    # Replies are evenly spaced in time order; the time is shown on hover.
    trend = chart_data["response_time_trend"]
    length = chart_data["length_preference"]
    return {
        "topic_distribution": _pie(topic_dist["labels"], topic_dist["values"],
                                   [colors[topic] for topic in topic_dist["labels"]], theme, "replies"),
        "accuracy_per_topic": _horizontal_bar(
            chart_data["accuracy_per_topic"]["labels"], chart_data["accuracy_per_topic"]["values"], theme,
            "%{y}: %{x}% accuracy<extra></extra>", percent_axis),
        "accuracy_vs_phase": _line(
            chart_data["accuracy_vs_phase"]["labels"], chart_data["accuracy_vs_phase"]["values"], theme,
            "%{x} phase: %{y}% accuracy<extra></extra>", {}, percent_axis),
        # Legend above the plot so it never collides with the turn axis title.
        "correctness_per_reply": _finish(
            stacked, theme, legend=True, legend_on_top=True,
            x={"title": "Turn in session", **_whole_ticks(len(correctness["labels"]), 12)},
            y={**_count_axis(stack_max), "title": "Replies"}),
        "response_time_trend": _line(
            list(range(1, len(trend["labels"]) + 1)), trend["values"], theme,
            "Reply %{x} (%{customdata}): %{y} s<extra></extra>",
            {"title": "Replies, oldest to newest", **_whole_ticks(len(trend["labels"]), 12, {"nticks": 8})},
            {"rangemode": "tozero", "ticksuffix": " s"}, customdata=trend["labels"]),
        "rating_distribution": _bar(
            chart_data["rating_distribution"]["labels"], chart_data["rating_distribution"]["values"], theme,
            "Rating %{x}: %{y} replies<extra></extra>",
            _count_axis(max(chart_data["rating_distribution"]["values"], default=0)), "Rating (1-4)"),
        "length_preference": _pie(length["labels"], length["values"], theme["series"][:3], theme, "replies"),
    }
