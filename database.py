"""
SQLite database management for the application.

Use locking to ensure thread safety when accessing the database from multiple threads.
Use WAL mode for better concurrency. All database operations are performed on the calling thread, 
so if you need to access the database from multiple threads, use the provided lock to ensure thread safety.
"""

import sqlite3
import threading
from pathlib import Path
from datetime import datetime

from settings import CONFIG_DIR, DEFAULT_SETTINGS
from models import ClipEntry

DB_PATH = Path(CONFIG_DIR) / "pinboard.db"

_lock = threading.Lock()

def get_connection() -> sqlite3.Connection:
    """Get a thread-local SQLite connection with WAL mode enabled."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)

    conn.row_factory = sqlite3.Row # Enable dict-like access to rows eg: row["content"] 

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

class Database:
    """Database manager for clipboard entries."""

    def __init__(self):
        Path(CONFIG_DIR).mkdir(parents=True, exist_ok=True)
        self._conn = get_connection()

        self._create_table()


    # Create clips table if it doesn't exist
    def _create_table(self) -> None:
        """Create the clips table if it doesn't exist."""
        with _lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS clips (
                    id           INTEGER PRIMARY KEY,
                    type         TEXT NOT NULL DEFAULT 'text',
                    content      TEXT NOT NULL DEFAULT '',
                    html_content TEXT,
                    image_dib    NULL,
                    image_path   TEXT,                    
                    pinned       INTEGER NOT NULL DEFAULT 0,
                    pinned_order INTEGER,
                    created_at   TEXT,
                    last_used    TEXT,
                    use_count    INTEGER NOT NULL DEFAULT 0,
                    favorite     INTEGER NOT NULL DEFAULT 0
                );
            """)

            # Create indexes for faster lookups
            self._conn.executescript("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_non_pinned_clips
                ON clips (content, type, COALESCE(image_path, ""))
                WHERE pinned = 0;

                CREATE INDEX IF NOT EXISTS idx_clips_pinned
                ON clips (pinned DESC, pinned_order ASC);

                CREATE INDEX IF NOT EXISTS idx_clips_last_used
                ON clips (last_used DESC);
            """)

            self._conn.commit()


    # 1. WRITE OPERATIONS
    
    def add(self, entry: ClipEntry) -> int | None:
        """Insert or update a clip and return its ID."""

        with _lock:
            cursor = self._conn.execute(
                """
                INSERT INTO clips (
                    type,
                    content,
                    html_content,
                    image_dib,
                    image_path,
                    pinned,
                    pinned_order,
                    created_at,
                    last_used,
                    use_count,
                    favorite
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(content, type, COALESCE(image_path, "")) WHERE pinned=0
                DO UPDATE SET
                    html_content = COALESCE(excluded.html_content, clips.html_content),
                    created_at = COALESCE(excluded.created_at, clips.created_at)
                RETURNING id 
                """,
                (
                    entry.type,
                    entry.content,
                    entry.html_content,
                    entry.image_dib,
                    entry.image_path,
                    int(entry.pinned),
                    entry.pinned_order,
                    entry.created_at,
                    entry.last_used,
                    int(entry.use_count),
                    int(entry.favorite),
                ),
            )

            clip_id = cursor.fetchone()["id"]

            # If pinned, assign proper order
            if entry.pinned:
                cursor = self._conn.execute(
                    "SELECT COALESCE(MAX(pinned_order), 0) AS pinned_order FROM clips WHERE pinned=1"
                )
                next_order = cursor.fetchone()["pinned_order"] + 1

                self._conn.execute(
                    "UPDATE clips SET pinned_order=? WHERE id=?",
                    (next_order, clip_id),
                )

            self._conn.commit()
            return clip_id

    def delete_clip(self, clip_id: int) -> None:
        with _lock:
            self._conn.execute("DELETE FROM clips WHERE id = ?", (clip_id,))
            self._conn.commit()

    def toggle_pin(self, clip_id: int) -> None:
        with _lock:
            # Get current pinned state
            cursor = self._conn.execute("SELECT pinned FROM clips WHERE id = ?", (clip_id,))
            row = cursor.fetchone()
            if not row:
                return
            current_pinned = bool(row["pinned"])
            # Toggle pinned state
            if current_pinned:
                # Unpin: set pinned=0 and clear pinned_order
                self._conn.execute(
                    "UPDATE clips SET pinned=0, pinned_order=NULL WHERE id = ?", (clip_id,)
                ) 
            else:
                # Pin – assign next order slot
                max_order = self._conn.execute(
                    "SELECT COALESCE(MAX(pinned_order), 0) AS pinned_order FROM clips WHERE pinned=1"
                ).fetchone()["pinned_order"]
                self._conn.execute(
                    "UPDATE clips SET pinned=1, pinned_order=? WHERE id=?",
                    (max_order + 1, clip_id),
                )
            self._conn.commit()

    def update_used_count(self, clip_id: int) -> None:
        """Increment use_count and update last_used timestamp."""
        with _lock:
            self._conn.execute(
                """UPDATE clips
                   SET use_count = use_count + 1,
                       last_used = ?
                   WHERE id = ?""",
                (datetime.now().isoformat(), clip_id),
            )
            self._conn.commit()

    def clear_history(self) -> None:
        """Delete all non-pinned entries."""
        with _lock:
            self._conn.execute("DELETE FROM clips WHERE pinned=0")
            self._conn.commit()

    def update_pinned_order(self, clip_id: int, new_order: int) -> None:
        """Move a pinned clip to a new position and shift others accordingly."""
        with _lock:
            cursor = self._conn.execute(
                "SELECT pinned, pinned_order FROM clips WHERE id=?",
                (clip_id,),
            )
            row = cursor.fetchone()
            if not row or not row["pinned"]:
                return  # not found or not pinned

            old_order = row["pinned_order"]

            # No change needed
            if old_order == new_order:
                return

            if new_order < old_order:
                # Moving UP: shift others DOWN
                self._conn.execute("""
                    UPDATE clips
                    SET pinned_order = pinned_order + 1
                    WHERE pinned = 1
                    AND pinned_order >= ?
                    AND pinned_order < ?
                """, (new_order, old_order))

            else:
                # Moving DOWN: shift others UP
                self._conn.execute("""
                    UPDATE clips
                    SET pinned_order = pinned_order - 1
                    WHERE pinned = 1
                    AND pinned_order > ?
                    AND pinned_order <= ?
                """, (old_order, new_order))

            # Place item in new position
            self._conn.execute(
                "UPDATE clips SET pinned_order=? WHERE id=?",
                (new_order, clip_id),
            )

            self._conn.commit()

    def _prune_history(self) -> None:
        """Keep only the most recent max_history non-pinned entries."""
        with _lock:
            max_history = DEFAULT_SETTINGS.get("max_history", 500)
            self._conn.execute("""
                DELETE FROM clips
                WHERE id IN (
                    SELECT id FROM clips
                    WHERE pinned=0
                    ORDER BY created_at DESC
                    LIMIT -1 OFFSET ?
                )
            """, (max_history,))
            self._conn.commit()


    # 2. READ OPERATIONS

    def get_all(self, search: str = "") -> list:
        """
        Return all clips, optionally filtered by search term in content.
        Pinned clips are returned first (ordered by pinned_order), followed by non-pinned clips ordered by created_at descending.
        """
        with _lock:
            if search:
                like = f"%{search}%"
                rows = self._conn.execute(
                    """
                    SELECT id, type, content, html_content, image_dib, image_path,
                           pinned, pinned_order, created_at, last_used,
                           use_count, favorite
                    FROM clips
                    WHERE content LIKE ?
                    ORDER BY
                        pinned DESC,
                        CASE WHEN pinned=1 THEN pinned_order END ASC,
                        created_at DESC
                    """,
                    (like,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    """
                    SELECT id, type, content, html_content, image_dib, image_path,
                           pinned, pinned_order, created_at, last_used,
                           use_count, favorite
                    FROM clips
                    ORDER BY
                        pinned DESC,
                        CASE WHEN pinned=1 THEN pinned_order END ASC,
                        created_at DESC
                    """
                ).fetchall()
            
            return [ClipEntry(
                id=row["id"],
                type=row["type"],
                content=row["content"],
                html_content=row["html_content"],
                image_dib=row["image_dib"],
                image_path=row["image_path"],
                pinned=row["pinned"],
                pinned_order=row["pinned_order"],
                created_at=row["created_at"],
                last_used=row["last_used"],
                use_count=row["use_count"],
                favorite=["favorite"]
                ) for row in rows]
    
    def get_clip_by_id(self, clip_id: int) -> dict | None:
        """Return a single clip by ID, or None if not found."""
        with _lock:
            row = self._conn.execute(
                """
                SELECT id, type, content, html_content, image_dib, image_path,
                       pinned, pinned_order, created_at, last_used,
                       use_count, favorite
                FROM clips
                WHERE id=?
                """,
                (clip_id,),
            ).fetchone()

        return dict(row) if row else None
    
    def get_pinned_clips(self) -> list[dict]:
        """Return all pinned clips ordered by pinned_order."""
        with _lock:
            rows = self._conn.execute(
                """
                SELECT id, type, content, html_content, image_dib, image_path,
                       pinned, pinned_order, created_at, last_used,
                       use_count, favorite
                FROM clips
                WHERE pinned=1
                ORDER BY pinned_order ASC
                """
            ).fetchall()

        return [dict(row) for row in rows]
    
    # 3. OTHER OPERATIONS

    def close(self) -> None:
        """Close the database connection."""
        with _lock:
            self._conn.close()