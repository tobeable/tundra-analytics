import psycopg2
import psycopg2.extras
import pandas as pd
import streamlit as st


@st.cache_resource
def _get_connection():
    cfg = st.secrets["postgres"]
    return psycopg2.connect(
        host=cfg["host"],
        port=cfg["port"],
        dbname=cfg["dbname"],
        user=cfg["user"],
        password=cfg["password"],
        sslmode="require",
        connect_timeout=10,
    )


def _conn():
    """Return a live connection, reconnecting if the previous one died."""
    conn = _get_connection()
    try:
        conn.cursor().execute("SELECT 1")
    except Exception:
        conn.close()
        _get_connection.clear()
        conn = _get_connection()
    return conn


def run_query(sql: str, params: dict | None = None) -> list[dict]:
    conn = _conn()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def run_query_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    conn = _conn()
    return pd.read_sql_query(sql, conn, params=params)


def get_schema_context() -> str:
    return (
        "Schema (Postgres):\n"
        "- countries(country_code CHAR(3) PK, country_name, region, latitude, longitude)\n"
        "- plans(plan_id PK, plan_name, monthly_price, seat_limit, features TEXT[])\n"
        "- customers(customer_id PK, company_name, country_code FK, industry, employee_count, signup_date, account_tier, description)\n"
        "- subscriptions(subscription_id PK, customer_id FK, plan_id FK, seats, mrr, status, subscription_period TSTZRANGE, started_at, canceled_at)\n"
        "- usage_events(event_id PK, customer_id FK, event_date, event_type, api_calls, metadata JSONB)\n"
        "- invoices(invoice_id PK, customer_id FK, amount, invoice_date, status)\n"
        "- customer_embeddings(customer_id FK, embedding vector(1024))\n"
        "\n"
        "Join keys:\n"
        "- subscriptions.plan_id = plans.plan_id\n"
        "- subscriptions.customer_id = customers.customer_id\n"
        "- customers.country_code = countries.country_code\n"
        "\n"
        "Allowed values:\n"
        "- subscriptions.status: active, trial, churned\n"
        "- invoices.status: paid, pending, overdue\n"
        "- customers.industry: SaaS, Finance, Healthcare, Retail, Manufacturing, Media\n"
        "- plans.plan_name: Starter, Pro, Enterprise\n"
        "- usage_events.event_type: login, api_call, report_run, export\n"
        "\n"
        "Gotchas:\n"
        "- round(x, 2) needs numeric cast: round((expr)::numeric, 2)\n"
        "- Parameterize all user values with %(name)s; never interpolate.\n"
    )
