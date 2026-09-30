import plotly.express as px
import streamlit as st

from src.db import run_query, run_query_df


def show():
    st.header("Executive Summary")

    row = run_query("""
        SELECT
            round(sum(s.mrr)::numeric, 2)                              AS total_mrr,
            count(*) FILTER (WHERE s.status = 'active')                AS active_subs,
            count(DISTINCT s.customer_id)                              AS total_customers,
            round(100.0 * count(*) FILTER (WHERE s.status = 'churned')
                  / NULLIF(count(*), 0), 1)                            AS churn_pct,
            round(avg(s.mrr) FILTER (WHERE s.status = 'active')::numeric, 2) AS avg_mrr,
            round(sum(i.total_rev)::numeric, 2)                        AS total_revenue
        FROM subscriptions s
        LEFT JOIN (
            SELECT customer_id, sum(amount) AS total_rev
            FROM invoices GROUP BY customer_id
        ) i ON i.customer_id = s.customer_id
    """)[0]

    c1, c2, c3 = st.columns(3)
    c1.metric("Total MRR", f"${row['total_mrr']:,.2f}")
    c2.metric("Active Subscriptions", f"{row['active_subs']:,}")
    c3.metric("Total Customers", f"{row['total_customers']:,}")

    c4, c5, c6 = st.columns(3)
    c4.metric("Churn Rate", f"{row['churn_pct'] or 0:.1f}%")
    c5.metric("Avg MRR (Active)", f"${row['avg_mrr']:,.2f}")
    c6.metric("Total Revenue", f"${row['total_revenue']:,.2f}")

    st.divider()

    st.subheader("Revenue Trend (Last 6 Months)")
    rev = run_query_df("""
        SELECT to_char(invoice_date, 'YYYY-MM') AS month,
               round(sum(amount)::numeric, 2)    AS revenue
        FROM invoices
        WHERE invoice_date >= CURRENT_DATE - INTERVAL '6 months'
        GROUP BY 1 ORDER BY 1
    """)
    if rev.empty:
        st.info("No recent invoice data.")
    else:
        fig = px.area(rev, x="month", y="revenue", markers=True)
        fig.update_layout(
            xaxis_title="Month",
            yaxis_title="Revenue ($)",
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig, width="stretch")

    st.divider()

    left, right = st.columns(2)
    with left:
        st.subheader("MRR by Plan")
        plan_mrr = run_query_df("""
            SELECT p.plan_name, round(sum(s.mrr)::numeric, 2) AS mrr
            FROM subscriptions s
            JOIN plans p ON p.plan_id = s.plan_id
            WHERE s.status = 'active'
            GROUP BY p.plan_name ORDER BY mrr DESC
        """)
        if not plan_mrr.empty:
            fig = px.bar(plan_mrr, x="plan_name", y="mrr")
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, width="stretch")

    with right:
        st.subheader("Subscriptions by Status")
        status_df = run_query_df("""
            SELECT status, count(*) AS count
            FROM subscriptions GROUP BY status ORDER BY count DESC
        """)
        if not status_df.empty:
            fig = px.pie(status_df, names="status", values="count", hole=0.4)
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, width="stretch")
