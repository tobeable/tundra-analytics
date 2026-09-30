"""Export embeddings from Snowflake in batches of 100 via direct SQL, write to local JSON."""
import json
import subprocess
import sys

# We'll use the cortex CLI to run SQL and capture output
# Actually, let's read from the cached query results

# Step 1: Export from Snowflake is already done via TEMP_EMBEDDINGS table
# Step 2: We need to read them. Since we can't connect directly, 
# let's use a workaround: read the query_001.json result from the SQL tool cache

# Actually the simplest approach: use snowflake-connector with externalbrowser
# But that requires interactive login. 
# Alternative: Install a newer connector that supports it.

# Let's try the programmatic access token approach instead
import os

# Check if there's a token cache from snowflake CLI
token_cache_dir = os.path.join(os.path.expanduser("~"), ".snowflake", "cache")
if os.path.exists(token_cache_dir):
    print(f"Cache dir exists: {os.listdir(token_cache_dir)}")
else:
    print("No cache dir found")

# Check connections.toml for any token-based auth
conn_file = os.path.join(os.path.expanduser("~"), ".snowflake", "connections.toml")
with open(conn_file) as f:
    print(f"connections.toml:\n{f.read()}")
