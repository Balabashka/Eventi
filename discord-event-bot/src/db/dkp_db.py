import sqlite3
from pathlib import Path
from typing import List, Tuple, Optional

# dkp.sqlite3 will sit in src/ next to bot.py
DB_PATH = Path(__file__).resolve().parent.parent / "dkp.sqlite3"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create DKP tables if they don't exist."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS dkp (
            server_id INTEGER NOT NULL,
            user_id   INTEGER NOT NULL,
            points    INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (server_id, user_id)
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS dkp_log (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            server_id INTEGER NOT NULL,
            user_id   INTEGER NOT NULL,
            change    INTEGER NOT NULL,
            reason    TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    conn.commit()
    conn.close()


def _change_dkp(
    server_id: int,
    user_id: int,
    delta: int,
    reason: Optional[str],
) -> int:
    """Internal helper: apply a delta and return new total."""
    conn = get_connection()
    cur = conn.cursor()

    # Ensure row exists
    cur.execute(
        """
        INSERT INTO dkp (server_id, user_id, points)
        VALUES (?, ?, 0)
        ON CONFLICT(server_id, user_id) DO NOTHING;
        """,
        (server_id, user_id),
    )

    # Apply change
    cur.execute(
        "UPDATE dkp SET points = points + ? WHERE server_id = ? AND user_id = ?;",
        (delta, server_id, user_id),
    )

    # Log entry
    cur.execute(
        """
        INSERT INTO dkp_log (server_id, user_id, change, reason)
        VALUES (?, ?, ?, ?);
        """,
        (server_id, user_id, delta, reason),
    )

    # Get new total
    cur.execute(
        "SELECT points FROM dkp WHERE server_id = ? AND user_id = ?;",
        (server_id, user_id),
    )
    row = cur.fetchone()
    conn.commit()
    conn.close()

    return int(row["points"]) if row else 0


def add_dkp(
    server_id: int,
    user_id: int,
    amount: int,
    reason: Optional[str] = None,
) -> int:
    """Add DKP to a user and return new total."""
    return _change_dkp(server_id, user_id, abs(amount), reason)


def remove_dkp(
    server_id: int,
    user_id: int,
    amount: int,
    reason: Optional[str] = None,
) -> int:
    """Remove DKP from a user and return new total."""
    return _change_dkp(server_id, user_id, -abs(amount), reason)


def get_dkp(server_id: int, user_id: int) -> int:
    """Get current DKP for a user."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT points FROM dkp WHERE server_id = ? AND user_id = ?;",
        (server_id, user_id),
    )
    row = cur.fetchone()
    conn.close()
    return int(row["points"]) if row else 0


def get_leaderboard(server_id: int, limit: int = 10) -> List[Tuple[int, int]]:
    """Return list of (user_id, points) sorted by DKP desc."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT user_id, points
        FROM dkp
        WHERE server_id = ?
        ORDER BY points DESC
        LIMIT ?;
        """,
        (server_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return [(int(r["user_id"]), int(r["points"])) for r in rows]
