import sqlite3
from config import DB_NAME

def get_db():
    """Devuelve una conexión nueva a la base de datos.
    Use un contexto (with) para asegurar cierre automático.
    """
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
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
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO lesson_history (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        conn.commit()


# UNUSED: función comentada porque no se está usando
# def get_recent_history(session_id, n_turns=3):
#     with get_db() as conn:
#         cursor = conn.cursor()
#         cursor.execute(
#             """
#             SELECT role, content FROM lesson_history
#             WHERE session_id=?
#             ORDER BY id DESC LIMIT ?
#             """,
#             (session_id, n_turns * 2),
#         )
#         rows = cursor.fetchall()
#         return list(reversed(rows))
