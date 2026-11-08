import sqlite3
con = sqlite3.connect("data/app.db")
con.row_factory = sqlite3.Row
tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
print("Tables:", tables)
for t in tables:
    cols = [r[1] for r in con.execute(f"pragma table_info({t})")]
    n = con.execute(f"select count(*) from {t}").fetchone()[0]
    print(f"\n== {t} ({n} rows) ==\ncolumns: {cols}")
    if "channel" in t.lower() or "schedule" in t.lower():
        for r in con.execute(f"select * from {t} limit 5"):
            d = dict(r)
            for k in list(d):
                if any(x in k.lower() for x in ("token", "secret", "key")):
                    d[k] = "***"
            print(d)
