import json
import re

import plotly.express as px
import streamlit as st

from src.cortex import cortex_complete
from src.db import get_schema_context, run_query_df

_SYSTEM_PROMPT = f"""You are a chart-building assistant for a Postgres SaaS analytics database.

{get_schema_context()}

The user describes a chart in plain English. You must return a JSON object with:
- "sql": a SELECT query that fetches the data (Postgres-compatible, max 500 rows)
- "chart_type": one of "bar", "line", "area", "scatter", "pie"
- "x": the column name for the x-axis
- "y": the column name for the y-axis (or "values" for pie)
- "color": (optional) column for color grouping
- "title": a short chart title

Rules:
- NEVER use 'cancelled'; the correct status is 'churned'.
- Always use round((expr)::numeric, 2) for rounding.
- Return ONLY valid JSON, no explanation, no markdown fences.

Worked example:
User: Show me monthly revenue as a line chart
Assistant: {{"sql": "SELECT to_char(i.invoice_date, 'YYYY-MM') AS month, round(sum(i.amount)::numeric, 2) AS revenue FROM invoices i GROUP BY 1 ORDER BY 1", "chart_type": "line", "x": "month", "y": "revenue", "title": "Monthly Revenue"}}
"""

_EXAMPLES = [
    "Bar chart of active MRR by plan",
    "Line chart of monthly revenue over time",
    "Pie chart of subscriptions by status",
    "Scatter plot of employee count vs MRR",
    "Area chart of monthly usage events by type",
]


def _parse_spec(text: str) -> dict | None:
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    raw = fenced.group(1).strip() if fenced else text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        brace = raw.find("{{")
        if brace == -1:
            brace = raw.find("{")
        if brace >= 0:
            try:
                return json.loads(raw[brace:])
            except json.JSONDecodeError:
                pass
    return None


def _render_chart(df, spec: dict):
    ct = spec.get("chart_type", "bar")
    x = spec.get("x")
    y = spec.get("y")
    color = spec.get("color")
    title = spec.get("title", "Chart")

    kwargs = {"data_frame": df, "x": x, "y": y, "title": title}
    if color and color in df.columns:
        kwargs["color"] = color

    chart_fn = {
        "bar": px.bar,
        "line": px.line,
        "area": px.area,
        "scatter": px.scatter,
        "pie": lambda **kw: px.pie(
            data_frame=kw["data_frame"],
            names=kw["x"],
            values=kw["y"],
            title=kw["title"],
        ),
    }.get(ct, px.bar)

    fig = chart_fn(**kwargs)
    fig.update_layout(margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig, width="stretch")


def show():
    st.header("Charts")
    st.caption("Describe a chart and get it instantly.")

    if "chart_history" not in st.session_state:
        st.session_state.chart_history = []

    clicked_example = None
    cols = st.columns(len(_EXAMPLES))
    for i, ex in enumerate(_EXAMPLES):
        if cols[i].button(ex, key=f"chart_ex_{i}"):
            clicked_example = ex

    question = st.chat_input("Describe the chart you want...") or clicked_example

    for entry in st.session_state.chart_history:
        with st.chat_message("user"):
            st.markdown(entry["question"])
        with st.chat_message("assistant"):
            if "error" in entry:
                st.error(entry["error"])
            else:
                st.code(entry["sql"], language="sql")
                _render_chart(entry["df"], entry["spec"])

    if question:
        st.session_state.chart_history.append({"question": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Generating chart..."):
                prompt = f"{_SYSTEM_PROMPT}\n\nUser: {question}\nAssistant:"
                response = cortex_complete(prompt)

            spec = _parse_spec(response)
            if not spec or "sql" not in spec:
                err = f"Could not parse chart spec from model response:\n{response}"
                st.error(err)
                st.session_state.chart_history[-1]["error"] = err
            else:
                sql = spec["sql"]
                st.code(sql, language="sql")
                try:
                    df = run_query_df(sql)
                    if df.empty:
                        st.info("Query returned no rows.")
                        st.session_state.chart_history[-1]["error"] = "No rows returned."
                    else:
                        _render_chart(df, spec)
                        st.session_state.chart_history[-1].update(
                            {"sql": sql, "spec": spec, "df": df}
                        )
                except Exception as e:
                    err = f"Query error: {e}"
                    st.error(err)
                    st.session_state.chart_history[-1]["error"] = err
        st.rerun()
