import sqlite3
from config import DB_NAME

# ========================
# Base de datos SQLite
# ========================
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = conn.cursor()

def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lesson_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        role TEXT,
        content TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()

def save_message(session_id, role, content):
    cursor.execute(
        "INSERT INTO lesson_history (session_id, role, content) VALUES (?, ?, ?)", 
        (session_id, role, content)
    )
    conn.commit()

def get_recent_history(session_id, n_turns=3):
    cursor.execute("""
        SELECT role, content FROM lesson_history 
        WHERE session_id=? 
        ORDER BY id DESC LIMIT ?
    """, (session_id, n_turns*2))
    rows = cursor.fetchall()
    return list(reversed(rows))

# Inicializar DB al importar
init_db()
