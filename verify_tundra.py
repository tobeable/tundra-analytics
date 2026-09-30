import psycopg2

conn = psycopg2.connect(
    host='vqr6mmj6ubhxjhbeiejzryqfui.icqrhwu-tw95108.eu-central-1.aws.postgres.snowflake.app',
    port=5432, dbname='postgres', user='snowflake_admin',
    password='REDACTED',
    sslmode='require', connect_timeout=10
)
cur = conn.cursor()

# 1. Row counts
print('=== 1. Row Counts ===')
for t in ['countries','plans','customers','subscriptions','usage_events','invoices','customer_embeddings']:
    cur.execute(f'SELECT count(*) FROM {t}')
    print(f'  {t:25s} {cur.fetchone()[0]:>8,}')

# 2. Schema check: column names per table
print('\n=== 2. Column Names (vs AGENTS.md) ===')
for t in ['countries','plans','customers','subscriptions','usage_events','invoices','customer_embeddings']:
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
    """, (t,))
    cols = [r[0] for r in cur.fetchall()]
    print(f'  {t}: {", ".join(cols)}')

# 3. Allowed values checks
print('\n=== 3. Allowed Values ===')

cur.execute("SELECT DISTINCT status FROM subscriptions ORDER BY status")
print(f'  subscriptions.status: {[r[0] for r in cur.fetchall()]}')

cur.execute("SELECT DISTINCT status FROM invoices ORDER BY status")
print(f'  invoices.status:      {[r[0] for r in cur.fetchall()]}')

cur.execute("SELECT DISTINCT industry FROM customers ORDER BY industry")
print(f'  customers.industry:   {[r[0] for r in cur.fetchall()]}')

cur.execute("SELECT DISTINCT plan_name FROM plans ORDER BY plan_name")
print(f'  plans.plan_name:      {[r[0] for r in cur.fetchall()]}')

cur.execute("SELECT DISTINCT event_type FROM usage_events ORDER BY event_type")
print(f'  usage_events.type:    {[r[0] for r in cur.fetchall()]}')

# 4. Churn rate
print('\n=== 4. Subscription Status Distribution ===')
cur.execute("""
    SELECT status, count(*) AS cnt, round(100.0 * count(*) / sum(count(*)) over(), 2) AS pct
    FROM subscriptions GROUP BY status ORDER BY cnt DESC
""")
for r in cur.fetchall():
    print(f'  {r[0]:10s} {r[1]:>6,}  ({r[2]}%)')

# 5. Join key validation
print('\n=== 5. Join Key Validation ===')
cur.execute("SELECT count(*) FROM customers c JOIN countries co ON c.country_code = co.country_code")
print(f'  customers JOIN countries on country_code: {cur.fetchone()[0]:,} rows')

cur.execute("SELECT count(*) FROM subscriptions s JOIN plans p ON s.plan_id = p.plan_id")
print(f'  subscriptions JOIN plans on plan_id:      {cur.fetchone()[0]:,} rows')

cur.execute("SELECT count(*) FROM subscriptions s JOIN customers c ON s.customer_id = c.customer_id")
print(f'  subscriptions JOIN customers on customer_id: {cur.fetchone()[0]:,} rows')

cur.execute("SELECT count(*) FROM invoices i JOIN customers c ON i.customer_id = c.customer_id")
print(f'  invoices JOIN customers on customer_id:   {cur.fetchone()[0]:,} rows')

cur.execute("SELECT count(*) FROM usage_events u JOIN customers c ON u.customer_id = c.customer_id")
print(f'  usage_events JOIN customers on customer_id: {cur.fetchone()[0]:,} rows')

# 6. Monthly revenue NOT flat
print('\n=== 6. Monthly Invoice Revenue ===')
cur.execute("""
    SELECT to_char(invoice_date, 'YYYY-MM') AS month,
           count(*) AS invoices,
           round(sum(amount)::numeric, 2) AS total_revenue
    FROM invoices GROUP BY 1 ORDER BY 1
""")
amounts = []
for r in cur.fetchall():
    amounts.append(float(r[2]))
    print(f'  {r[0]}   invoices={r[1]:>5,}   revenue={r[2]:>12}')

mn, mx = min(amounts), max(amounts)
spread = (mx - mn) / mn * 100
print(f'\n  Spread: {spread:.1f}% — {"NOT flat" if spread > 5 else "FLAT (problem!)"}')

# 7. Top 10 countries by active MRR
print('\n=== 7. Top 10 Countries by Active MRR ===')
cur.execute("""
    SELECT c.country_code, co.country_name, count(s.subscription_id) AS active_subs,
           round(sum(s.mrr)::numeric, 2) AS total_mrr
    FROM subscriptions s
    JOIN customers c ON c.customer_id = s.customer_id
    JOIN countries co ON co.country_code = c.country_code
    WHERE s.status = 'active'
    GROUP BY c.country_code, co.country_name
    ORDER BY total_mrr DESC
    LIMIT 10
""")
print(f'  {"Code":<6} {"Country":<22} {"Subs":>6} {"MRR":>14}')
for r in cur.fetchall():
    print(f'  {r[0]:<6} {r[1]:<22} {r[2]:>6,} {r[3]:>14,}')

cur.close()
conn.close()
