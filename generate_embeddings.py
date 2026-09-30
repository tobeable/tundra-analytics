"""Generate embeddings: reads Snowflake connections.toml + .streamlit/secrets.toml.
Usage: python generate_embeddings.py
Requires: snowflake-connector-python, psycopg2-binary, toml
"""
import json
import os
import configparser

import psycopg2
import snowflake.connector
import toml

secrets = toml.load(r".streamlit\secrets.toml")

conn_file = os.path.join(os.path.expanduser("~"), ".snowflake", "connections.toml")
cfg = configparser.ConfigParser()
cfg.read(conn_file)

# Find a password-based Snowflake connection
sf_cfg = None
for section in cfg.sections():
    if cfg[section].get("password"):
        sf_cfg = dict(cfg[section])
        break
if not sf_cfg:
    raise SystemExit("No password-based Snowflake connection found in connections.toml")

sf_conn = snowflake.connector.connect(
    account=sf_cfg["account"], user=sf_cfg["user"],
    password=sf_cfg["password"],
    warehouse=sf_cfg.get("warehouse", "COMPUTE_WH"),
)
sf_cur = sf_conn.cursor()

pg = secrets["postgres"]
pg_conn = psycopg2.connect(
    host=pg["host"], port=pg["port"], dbname=pg["dbname"],
    user=pg["user"], password=pg["password"],
    sslmode="require", connect_timeout=15,
)
pg_conn.autocommit = True
pg_cur = pg_conn.cursor()

pg_cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
pg_cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_customer_embeddings_hnsw
    ON customer_embeddings USING hnsw (embedding vector_cosine_ops)
""")

pg_cur.execute("""
    SELECT c.customer_id, c.description FROM customers c
    LEFT JOIN customer_embeddings ce ON ce.customer_id = c.customer_id
    WHERE ce.customer_id IS NULL ORDER BY c.customer_id
""")
rows = pg_cur.fetchall()
print(f"Generating embeddings for {len(rows)} customers...")

BATCH = 200
for i in range(0, len(rows), BATCH):
    batch = rows[i:i + BATCH]
    for cid, desc in batch:
        sf_cur.execute(
            "SELECT SNOWFLAKE.CORTEX.EMBED_TEXT_1024("
            "'snowflake-arctic-embed-l-v2.0', %s) AS emb", (desc,))
        emb = sf_cur.fetchone()[0]
        if isinstance(emb, str):
            emb = json.loads(emb)
        vec_str = "[" + ",".join(f"{v:.8f}" for v in emb) + "]"
        pg_cur.execute(
            "INSERT INTO customer_embeddings (customer_id, embedding) "
            "VALUES (%s, %s::vector) ON CONFLICT DO NOTHING", (cid, vec_str))
    print(f"  {min(i + BATCH, len(rows))}/{len(rows)} done")

pg_cur.close(); pg_conn.close()
sf_cur.close(); sf_conn.close()
print("Complete.")
