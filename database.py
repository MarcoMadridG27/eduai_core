import json
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
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS lesson_sessions (
            session_id TEXT PRIMARY KEY,
            source TEXT DEFAULT 'frontend',
            status TEXT DEFAULT 'draft',
            input_data TEXT,
            generated_data TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
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


def _upsert_session_row(session_id, source="frontend", status="draft", input_data=None, generated_data=None):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO lesson_sessions (session_id, source, status, input_data, generated_data, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(session_id) DO UPDATE SET
                source=excluded.source,
                status=excluded.status,
                input_data=COALESCE(excluded.input_data, lesson_sessions.input_data),
                generated_data=COALESCE(excluded.generated_data, lesson_sessions.generated_data),
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                session_id,
                source,
                status,
                input_data,
                generated_data,
            ),
        )
        conn.commit()


def save_session_input(session_id, input_data, source="frontend", status="draft"):
    payload = json.dumps(input_data, ensure_ascii=False)
    _upsert_session_row(session_id, source=source,
                        status=status, input_data=payload)


def save_generated_session(session_id, generated_data, source="frontend", status="completed"):
    payload = json.dumps(generated_data, ensure_ascii=False)
    _upsert_session_row(session_id, source=source,
                        status=status, generated_data=payload)


def update_session_status(session_id, status, source="frontend"):
    _upsert_session_row(session_id, source=source, status=status)


def get_all_sessions_db():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT session_id, source, status, input_data, generated_data, created_at, updated_at
            FROM lesson_sessions
            ORDER BY created_at DESC
            """
        )
        rows = cursor.fetchall()

    sessions = []
    for row in rows:
        input_data = json.loads(row[3]) if row[3] else None
        generated_data = json.loads(row[4]) if row[4] else None
        sessions.append({
            "session_id": row[0],
            "source": row[1],
            "status": row[2],
            "input_data": input_data,
            "generated_data": generated_data,
            "created_at": row[5],
            "updated_at": row[6],
        })
    return sessions


def get_session(session_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT session_id, source, status, input_data, generated_data, created_at, updated_at
            FROM lesson_sessions
            WHERE session_id=?
            """,
            (session_id,),
        )
        row = cursor.fetchone()

    if not row:
        return None

    input_data = json.loads(row[3]) if row[3] else None
    generated_data = json.loads(row[4]) if row[4] else None
    return {
        "session_id": row[0],
        "source": row[1],
        "status": row[2],
        "input_data": input_data,
        "generated_data": generated_data,
        "created_at": row[5],
        "updated_at": row[6],
    }


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
