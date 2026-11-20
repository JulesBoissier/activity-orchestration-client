from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

# Stored in SQLite's PRAGMA user_version.
# 0: timestamps written by SQLite CURRENT_TIMESTAMP, which is UTC.
# 1: timestamps in local time, the clock the dashboard filters with.
# 2: gap_reason column (why a sample has no process: no face, camera unavailable, ...).
SCHEMA_VERSION = 2


class AttentionTracker(Base):
    __tablename__ = "attention_tracker"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    # Local time, set by Python: the dashboard compares against datetime.now().
    timestamp = Column(DateTime, default=datetime.now, index=True)
    process_name = Column(String, nullable=True, index=True)
    window_title = Column(String, nullable=True, index=True)
    # Set for gap rows (empty process_name): see src.backend.attribution for the values.
    gap_reason = Column(String, nullable=True)


def _utc_to_local(text: str) -> str:
    utc = datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
    return utc.astimezone().replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S.%f")


class AttentionTrackerStore:
    """Handles database interactions for attention tracker."""

    def __init__(self, db_url="sqlite:///attention_tracker.db"):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        if self.engine.dialect.name == "sqlite":
            self._migrate_sqlite()
        self.Session = sessionmaker(bind=self.engine)

    def _migrate_sqlite(self):
        """Bring an existing database up to SCHEMA_VERSION, once.

        Version 0 -> 1 converts UTC timestamps to local time; the gap_reason column (2)
        is added to any table that lacks it. The tracker and the dashboard
        both open the store, possibly at the same moment: BEGIN IMMEDIATE makes one of them
        wait, and the version check makes the second a no-op.
        """
        raw = self.engine.raw_connection()
        conn = raw.driver_connection
        previous_isolation = conn.isolation_level
        conn.isolation_level = None  # manage the transaction explicitly
        try:
            cur = conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                version = cur.execute("PRAGMA user_version").fetchone()[0]
                if version < 1:
                    rows = cur.execute(
                        "SELECT id, timestamp FROM attention_tracker WHERE timestamp IS NOT NULL"
                    ).fetchall()
                    cur.executemany(
                        "UPDATE attention_tracker SET timestamp = ? WHERE id = ?",
                        [(_utc_to_local(ts), row_id) for row_id, ts in rows],
                    )
                columns = {row[1] for row in cur.execute("PRAGMA table_info(attention_tracker)")}
                if "gap_reason" not in columns:
                    cur.execute("ALTER TABLE attention_tracker ADD COLUMN gap_reason VARCHAR")
                if version < SCHEMA_VERSION:
                    cur.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                cur.execute("COMMIT")
            except Exception:
                cur.execute("ROLLBACK")
                raise
        finally:
            conn.isolation_level = previous_isolation
            raw.close()

    def save_attention(self, process_name: str, window_title: str, gap_reason: str = None):
        """Insert one sample. Gap samples have an empty process name and a ``gap_reason``."""
        session = self.Session()
        new_attention_tracker = AttentionTracker(
            process_name=process_name,
            window_title=window_title,
            gap_reason=gap_reason,
        )
        session.add(new_attention_tracker)
        session.commit()
        session.close()
