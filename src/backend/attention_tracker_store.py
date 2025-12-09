from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    PickleType,
    String,
    create_engine,
    func,
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class AttentionTracker(Base):
    __tablename__ = "attention_tracker"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    timestamp = Column(DateTime, default=func.now(), onupdate=func.now(), index=True)
    process_name = Column(String, nullable=True, index=True)
    window_title = Column(String, nullable=True, index=True)


class AttentionTrackerStore:
    """Handles database interactions for attention tracker."""

    def __init__(self, db_url="sqlite:///attention_tracker.db"):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def save_attention(self, process_name: str, window_title: str):
        """Insert a new attention record with normalized fields."""
        session = self.Session()
        new_attention_tracker = AttentionTracker(
            process_name=process_name,
            window_title=window_title,
        )
        session.add(new_attention_tracker)
        session.commit()
        session.close()
