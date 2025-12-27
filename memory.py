import sqlite3, time
from typing import Optional

DB = "data/memory.sqlite"


def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS users (
      user_id TEXT PRIMARY KEY,
      nickname TEXT,
      lang TEXT,
      premium INTEGER DEFAULT 0,
      summary TEXT DEFAULT ''
    )
    """
    )
    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS messages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id TEXT,
      role TEXT,
      content TEXT,
      ts INTEGER
    )
    """
    )
    conn.commit()
    conn.close()


def get_user(user_id: str):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, nickname, lang, premium, summary FROM users WHERE user_id=?",
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "user_id": row[0],
        "nickname": row[1],
        "lang": row[2],
        "premium": bool(row[3]),
        "summary": row[4],
    }


def upsert_user(
    user_id: str,
    nickname: Optional[str] = None,
    lang: Optional[str] = None,
    premium: Optional[bool] = None,
    summary: Optional[str] = None,
):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO users(user_id, nickname, lang, premium, summary) VALUES(?,?,?,?,?)",
        (user_id, nickname or "", lang or "uz+ru", 1 if premium else 0, summary or ""),
    )
    if nickname is not None:
        cur.execute("UPDATE users SET nickname=? WHERE user_id=?", (nickname, user_id))
    if lang is not None:
        cur.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, user_id))
    if premium is not None:
        cur.execute(
            "UPDATE users SET premium=? WHERE user_id=?", (1 if premium else 0, user_id)
        )
    if summary is not None:
        cur.execute("UPDATE users SET summary=? WHERE user_id=?", (summary, user_id))
    conn.commit()
    conn.close()


def add_message(user_id: str, role: str, content: str):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages(user_id, role, content, ts) VALUES(?,?,?,?)",
        (user_id, role, content, int(time.time())),
    )
    conn.commit()
    conn.close()


def last_messages(user_id: str, limit: int = 12):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT role, content FROM messages WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return list(reversed([{"role": r, "content": c} for r, c in rows]))
