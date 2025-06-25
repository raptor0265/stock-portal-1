import sqlite3

conn = sqlite3.connect("top_stocks.db")
cur = conn.cursor()

cur.execute("SELECT * FROM top10 LIMIT 5")
rows = cur.fetchall()

for row in rows:
    print(row)

conn.close()