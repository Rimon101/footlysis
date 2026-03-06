import sqlite3

def clean_duplicates():
    conn = sqlite3.connect("footlysis.db")
    c = conn.cursor()
    # Find duplicate sets (keep the one with the smallest id, or one that has home_goals)
    # the easiest way in sqlite: DELETE FROM matches WHERE id NOT IN (SELECT MIN(id) FROM matches GROUP BY home_team_id, away_team_id, substr(match_date, 1, 10))
    # Wait, the dates might vary up to 1-2 days! So GROUP BY is tricky.
    # We can fetch all matches ordered by match_date
    c.execute("SELECT id, home_team_id, away_team_id, match_date, home_goals FROM matches ORDER BY match_date")
    matches = c.fetchall()
    
    seen = {}
    to_delete = []
    
    from datetime import datetime
    
    def parse_date(ds):
        try:
            return datetime.fromisoformat(ds.replace("Z", "+00:00")).date()
        except:
            return datetime.strptime(ds[:10], "%Y-%m-%d").date()
            
    for m in matches:
        mid, hid, aid, date_str, h_goals = m
        d = parse_date(date_str)
        key_stem = f"{hid}-{aid}-{d.year}"
        
        # Check if we have seen it within +/- 7 days (in the same year, 7 days is safe)
        found = False
        for k in list(seen.keys()):
            s_d = seen[k]['date']
            if k.startswith(f"{hid}-{aid}-") and abs((d - s_d).days) <= 7:
                # Duplicate!
                found = True
                if h_goals is not None and seen[k]['h_goals'] is None:
                    # Keep this one, mark previous for deletion
                    to_delete.append(seen[k]['id'])
                    seen[k] = {'id': mid, 'date': d, 'h_goals': h_goals}
                elif h_goals is None and seen[k]['h_goals'] is not None:
                    to_delete.append(mid)
                else:
                    # just delete the newer one
                    to_delete.append(mid)
                break
                
        if not found:
            seen[f"{hid}-{aid}-{d.isoformat()}"] = {'id': mid, 'date': d, 'h_goals': h_goals}

    print(f"Found {len(to_delete)} duplicate records to delete.")
    for d_id in to_delete:
        c.execute("DELETE FROM matches WHERE id = ?", (d_id,))
        c.execute("DELETE FROM predictions WHERE match_id = ?", (d_id,))
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    clean_duplicates()
