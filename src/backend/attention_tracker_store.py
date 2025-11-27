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
    viewed_window_info = Column(String, unique=False, nullable=False, index=True)


class AttentionTrackerStore:
    """Handles database interactions for attention tracker."""

    def __init__(self, db_url="sqlite:///attention_tracker.db"):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def save_attention(self, viewed_window_info: str):
        """Save a calibration profile by name, updating it if it already exists."""
        session = self.Session()
        new_attention_tracker = AttentionTracker(viewed_window_info=viewed_window_info)
        session.add(new_attention_tracker)
        session.commit()
        session.close()
