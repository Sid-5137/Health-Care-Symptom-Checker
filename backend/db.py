import os
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

# Use the same SQLite database as the Django frontend by default
# This enables shared data (e.g., users, histories) across both services.
DEFAULT_SQLITE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "db.sqlite3")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")
print(f"[Backend] Using DATABASE_URL={DATABASE_URL}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class QueryHistory(Base):
    __tablename__ = "query_history"
    id = Column(Integer, primary_key=True, index=True)
    symptoms = Column(Text, nullable=False)
    probable_conditions = Column(Text, nullable=False)
    recommendations = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)
