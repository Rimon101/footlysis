import sqlite3
import pandas as pd

conn = sqlite3.connect("footlysis.db")
query = """
SELECT match_date, home_team_id, away_team_id, COUNT(*)
FROM matches
GROUP BY match_date, home_team_id, away_team_id
HAVING COUNT(*) > 1
LIMIT 10
"""
df = pd.read_sql(query, conn)
print("Duplicates:")
print(df)
