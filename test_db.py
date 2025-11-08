# test_db.py
from db import get_conn

try:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT DATABASE() AS db;")
    result = cur.fetchone()
    print("✅ Connected successfully to:", result["db"])
    cur.close()
    conn.close()
except Exception as e:
    print("❌ Connection failed:", e)
