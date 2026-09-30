import json
import pathlib

import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

from src.db import run_query, run_query_df

_ASSETS = pathlib.Path(__file__).parent / "assets"


# ── GeoJSON ────────────────────────────────────────────────────────
@st.cache_data
def _load_geojson():
    with open(_ASSETS / "countries.geojson", encoding="utf-8") as f:
        return json.load(f)


# ── Queries (all parameterized; scoped when country_code is set) ──
def _where(alias: str = "") -> str:
    prefix = f"{alias}." if alias else ""
    return f"WHERE {prefix}country_code = %(cc)s"


def _mrr_by_country() -> pd.DataFrame:
    return run_query_df(
        """
        SELECT c.country_code,
               co.country_name,
               co.latitude,
               co.longitude,
               round(coalesce(sum(s.mrr), 0)::numeric, 2) AS active_mrr
        FROM countries co
        LEFT JOIN customers c   ON c.country_code  = co.country_code
        LEFT JOIN subscriptions s ON s.customer_id = c.customer_id
                                  AND s.status = 'active'
        GROUP BY c.country_code, co.country_name, co.latitude, co.longitude
        """
    )


def _metrics(cc: str | None) -> dict:
    filt = "AND c.country_code = %(cc)s" if cc else ""
    row = run_query(
        f"""
        SELECT round(coalesce(sum(s.mrr), 0)::numeric, 2)       AS total_mrr,
               count(*) FILTER (WHERE s.status = 'active')       AS active_subs,
               round(100.0 * count(*) FILTER (WHERE s.status = 'churned')
                     / NULLIF(count(*), 0), 1)                   AS churn_pct,
               round(avg(s.seats)::numeric, 1)                   AS avg_seats
        FROM subscriptions s
        JOIN customers c ON c.customer_id = s.customer_id
        {filt}
        """,
        {"cc": cc} if cc else None,
    )[0]
    return dict(row)


def _accounts(cc: str | None) -> pd.DataFrame:
    filt = _where("c") if cc else ""
    return run_query_df(
        f"""
        SELECT c.company_name, c.industry, c.account_tier,
               p.plan_name, s.seats, s.mrr, s.status
        FROM customers c
        JOIN subscriptions s ON s.customer_id = c.customer_id
        JOIN plans p         ON p.plan_id     = s.plan_id
        {filt}
        ORDER BY s.mrr DESC
        LIMIT 50
        """,
        {"cc": cc} if cc else None,
    )


def _monthly_revenue(cc: str | None) -> pd.DataFrame:
    filt = "AND c.country_code = %(cc)s" if cc else ""
    return run_query_df(
        f"""
        SELECT to_char(i.invoice_date, 'YYYY-MM') AS month,
               round(sum(i.amount)::numeric, 2)    AS revenue
        FROM invoices i
        JOIN customers c ON c.customer_id = i.customer_id
        {filt}
        GROUP BY 1 ORDER BY 1
        """,
        {"cc": cc} if cc else None,
    )


def _plan_features(cc: str | None) -> pd.DataFrame:
    filt = "AND c.country_code = %(cc)s" if cc else ""
    return run_query_df(
        f"""
        SELECT f AS feature, count(*) AS cnt
        FROM subscriptions s
        JOIN customers c ON c.customer_id = s.customer_id
        JOIN plans p     ON p.plan_id     = s.plan_id
        CROSS JOIN LATERAL unnest(p.features) AS f
        WHERE s.status = 'active' {filt}
        GROUP BY f ORDER BY cnt DESC
        """,
        {"cc": cc} if cc else None,
    )


# ── Map ────────────────────────────────────────────────────────────
def _render_map(geojson: dict, mrr_df: pd.DataFrame):
    mrr_map = dict(zip(mrr_df["country_code"], mrr_df["active_mrr"]))
    max_mrr = max(mrr_map.values()) if mrr_map else 1

    for feat in geojson["features"]:
        code = feat["properties"].get("ADM0_A3", "")
        val = float(mrr_map.get(code, 0))
        ratio = val / max_mrr if max_mrr else 0
        r = int(20 + 200 * ratio)
        g = int(60 + 120 * (1 - ratio))
        b = int(180 - 80 * ratio)
        feat["properties"]["_fill"] = [r, g, b, 180]
        feat["properties"]["_mrr"] = val

    geo_layer = pdk.Layer(
        "GeoJsonLayer",
        id="countries",
        data=geojson,
        pickable=True,
        stroked=True,
        filled=True,
        get_fill_color="properties._fill",
        get_line_color=[255, 255, 255, 40],
        line_width_min_pixels=0.5,
        auto_highlight=True,
        highlight_color=[255, 200, 0, 120],
    )

    scatter_df = mrr_df[mrr_df["active_mrr"] > 0].copy()
    scatter_layer = pdk.Layer(
        "ScatterplotLayer",
        id="points",
        data=scatter_df,
        pickable=True,
        get_position=["longitude", "latitude"],
        get_radius=30000,
        get_fill_color=[41, 181, 232, 200],
        radius_min_pixels=3,
        radius_max_pixels=8,
    )

    view = pdk.ViewState(latitude=20, longitude=0, zoom=1.2, pitch=0)
    deck = pdk.Deck(
        layers=[geo_layer, scatter_layer],
        initial_view_state=view,
        map_style="dark",
        tooltip={"text": "{properties.NAME}: ${properties._mrr}"},
    )
    selection = st.pydeck_chart(deck, selection_mode="single-object", on_select="rerun")
    return selection


def _extract_country_code(selection) -> str | None:
    try:
        objects = selection.selection["objects"]
    except (AttributeError, KeyError, TypeError):
        return None

    if "countries" in objects and objects["countries"]:
        return objects["countries"][0].get("properties", {}).get("ADM0_A3")
    if "points" in objects and objects["points"]:
        return objects["points"][0].get("country_code")
    return None


# ── Page entry point ───────────────────────────────────────────────
def show():
    st.header("Dashboard")

    geojson = _load_geojson()
    mrr_df = _mrr_by_country()

    selection = _render_map(geojson, mrr_df)
    cc = _extract_country_code(selection)

    if cc:
        name_row = run_query(
            "SELECT country_name FROM countries WHERE country_code = %(cc)s",
            {"cc": cc},
        )
        label = name_row[0]["country_name"] if name_row else cc
        st.caption(f"Filtered to **{label}** ({cc})")
    else:
        label = "Global"
        st.caption("Click a country to filter, or viewing **Global**")

    # ── Metrics row ────────────────────────────────────────────────
    m = _metrics(cc)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total MRR", f"${m['total_mrr']:,.2f}")
    c2.metric("Active Subscriptions", f"{m['active_subs']:,}")
    c3.metric("Churn Rate", f"{m['churn_pct'] or 0:.1f}%")
    c4.metric("Avg Seats", f"{m['avg_seats'] or 0:.1f}")

    st.divider()

    # ── Accounts table ─────────────────────────────────────────────
    st.subheader(f"Accounts — {label}")
    accts = _accounts(cc)
    if accts.empty:
        st.info("No accounts for this selection.")
    else:
        st.dataframe(accts, hide_index=True, width="stretch")

    st.divider()

    # ── Charts side by side ────────────────────────────────────────
    left, right = st.columns(2)

    with left:
        st.subheader("Monthly Revenue")
        rev = _monthly_revenue(cc)
        if rev.empty:
            st.info("No invoice data.")
        else:
            fig = px.line(rev, x="month", y="revenue", markers=True)
            fig.update_layout(
                xaxis_title="Month",
                yaxis_title="Revenue ($)",
                margin=dict(l=0, r=0, t=10, b=0),
            )
            st.plotly_chart(fig, width="stretch")

    with right:
        st.subheader("Most-Used Plan Features")
        feat = _plan_features(cc)
        if feat.empty:
            st.info("No feature data.")
        else:
            fig = px.pie(
                feat,
                names="feature",
                values="cnt",
                hole=0.45,
            )
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, width="stretch")
