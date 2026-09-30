"""Verify: embeddings count + dashboard drill-down for USA vs Global."""
import psycopg2
import toml

secrets = toml.load(r".streamlit\secrets.toml")
pg = secrets["postgres"]
conn = psycopg2.connect(
    host=pg["host"], port=pg["port"], dbname=pg["dbname"],
    user=pg["user"], password=pg["password"],
    sslmode="require", connect_timeout=10,
)
cur = conn.cursor()

# Embeddings count
cur.execute("SELECT count(*) FROM customer_embeddings")
print(f"Embeddings: {cur.fetchone()[0]}")

# HNSW index
cur.execute("SELECT indexname FROM pg_indexes WHERE tablename='customer_embeddings' AND indexname LIKE '%hnsw%'")
idx = cur.fetchall()
print(f"HNSW index: {[r[0] for r in idx]}")

# Global metrics
cur.execute("""
    SELECT round(coalesce(sum(s.mrr), 0)::numeric, 2) AS total_mrr,
           count(*) FILTER (WHERE s.status = 'active') AS active_subs,
           round(100.0 * count(*) FILTER (WHERE s.status = 'churned') / NULLIF(count(*), 0), 1) AS churn_pct,
           round(avg(s.seats)::numeric, 1) AS avg_seats
    FROM subscriptions s
""")
row = cur.fetchone()
print(f"\n=== Global ===")
print(f"  Total MRR:    ${row[0]:,}")
print(f"  Active Subs:  {row[1]:,}")
print(f"  Churn Rate:   {row[2]}%")
print(f"  Avg Seats:    {row[3]}")

# USA metrics
cur.execute("""
    SELECT round(coalesce(sum(s.mrr), 0)::numeric, 2) AS total_mrr,
           count(*) FILTER (WHERE s.status = 'active') AS active_subs,
           round(100.0 * count(*) FILTER (WHERE s.status = 'churned') / NULLIF(count(*), 0), 1) AS churn_pct,
           round(avg(s.seats)::numeric, 1) AS avg_seats
    FROM subscriptions s
    JOIN customers c ON c.customer_id = s.customer_id
    WHERE c.country_code = 'USA'
""")
row = cur.fetchone()
print(f"\n=== USA ===")
print(f"  Total MRR:    ${row[0]:,}")
print(f"  Active Subs:  {row[1]:,}")
print(f"  Churn Rate:   {row[2]}%")
print(f"  Avg Seats:    {row[3]}")

cur.close()
conn.close()
