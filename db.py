import sqlite3
from pathlib import Path

# Cesta k databázi a SQL souboru
ROOT = Path(__file__).parent
DB_PATH = ROOT / "test.db"
INIT_SQL_PATH = ROOT / "init.sql"

# Připojení k SQLite
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Načtení a spuštění SQL skriptu
with open(INIT_SQL_PATH, "r", encoding="utf-8") as f:
    sql_script = f.read()

try:
    cur.executescript(sql_script)
    conn.commit()
    print("✅ Databáze byla úspěšně inicializována.")
except Exception as e:
    print("❌ Chyba při inicializaci databáze:", e)
finally:
    # Výpis existujících tabulek pro ověření
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cur.fetchall()]
    print("📋 Tabulky v databázi:", tables)

    cur.execute("SELECT * FROM users_ad")
    print("👤 Záznamy v users_ad:", cur.fetchall())

    conn.close()
