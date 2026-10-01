import psycopg2
import toml

pg = toml.load(r".streamlit\secrets.toml")["postgres"]
conn = psycopg2.connect(
    host=pg["host"], port=pg["port"], dbname=pg["dbname"],
    user=pg["user"], password=pg["password"],
    sslmode="require", connect_timeout=10,
)
cur = conn.cursor()

tables = ['countries','plans','customers','subscriptions','usage_events','invoices']
print('=== Row Counts ===')
for t in tables:
    cur.execute(f'SELECT count(*) FROM {t}')
    print(f'  {t:20s} {cur.fetchone()[0]:>8,}')

print('\n=== Subscription Status ===')
cur.execute('SELECT status, count(*), round(100.0*count(*)/sum(count(*)) over(), 1) AS pct FROM subscriptions GROUP BY status ORDER BY count(*) DESC')
for r in cur.fetchall():
    print(f'  {r[0]:10s} {r[1]:>6,}  ({r[2]}%)')

print('\n=== Invoice Amount Stats ===')
cur.execute('SELECT count(*), round(min(amount),2), round(avg(amount)::numeric,2), round(max(amount),2), round(sum(amount),2) FROM invoices')
r = cur.fetchone()
print(f'  count={r[0]:,}  min={r[1]}  avg={r[2]}  max={r[3]}  total={r[4]}')

print('\n=== Sample Invoices (first 5) ===')
cur.execute('SELECT invoice_id, subscription_id, invoice_date, amount, paid FROM invoices ORDER BY invoice_id LIMIT 5')
for r in cur.fetchall():
    print(f'  id={r[0]}  sub={r[1]}  date={r[2]}  amount={r[3]}  paid={r[4]}')

print('\n=== Custom Indexes ===')
cur.execute("SELECT indexname FROM pg_indexes WHERE schemaname='public' AND indexname LIKE 'idx_%' ORDER BY indexname")
for r in cur.fetchall():
    print(f'  {r[0]}')

cur.close()
conn.close()
