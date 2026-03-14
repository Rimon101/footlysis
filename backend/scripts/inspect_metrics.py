
import sqlite3
import os

db_path = os.path.abspath(os.path.join(os.getcwd(), "footlysis.db"))
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("--- TEAM STATS ---")
cursor.execute("SELECT * FROM team_stats LIMIT 3")
rows = cursor.fetchall()
for r in rows:
    print(dict(r))

print("\n--- PLAYER IMPACT DATA ---")
cursor.execute("SELECT name, xg_per90, xa_per90, is_injured FROM players WHERE xg_per90 > 0.3 LIMIT 5")
rows = cursor.fetchall()
for r in rows:
    print(dict(r))

conn.close()
