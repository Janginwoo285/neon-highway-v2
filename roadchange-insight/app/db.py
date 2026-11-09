"""SQLAlchemy models and database session. Local SQLite by default; Neon Postgres via DATABASE_URL."""
import os
from pathlib import Path
from sqlalchemy import create_engine, ForeignKey, String, Integer, Float, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = f"sqlite:///{ROOT / 'data' / 'roadchange.sqlite3'}"
DATABASE_URL = os.getenv('DATABASE_URL', DEFAULT_DB)
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql+psycopg://', 1)
elif DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite:') else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40))

class LoginSession(Base):
    __tablename__ = 'login_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    expires_at: Mapped[str] = mapped_column(String(40))

class RoadChange(Base):
    __tablename__ = 'road_changes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(100))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    observed_at: Mapped[str] = mapped_column(String(40))
    radius_m: Mapped[float] = mapped_column(Float, default=550)
    description: Mapped[str] = mapped_column(Text, default='')
    source: Mapped[str] = mapped_column(String(60), default='manual')

class DriveClip(Base):
    __tablename__ = 'drive_clips'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    code: Mapped[str] = mapped_column(String(40))
    trip_id: Mapped[str] = mapped_column(String(60))
    start_at: Mapped[str] = mapped_column(String(40))
    end_at: Mapped[str] = mapped_column(String(40))
    video_path: Mapped[str] = mapped_column(String(400), default='')
    source: Mapped[str] = mapped_column(String(60), default='synthetic')

class GpsPoint(Base):
    __tablename__ = 'gps_points'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clip_id: Mapped[int] = mapped_column(ForeignKey('drive_clips.id'), index=True)
    sampled_at: Mapped[str] = mapped_column(String(40))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)

class MatchRun(Base):
    __tablename__ = 'match_runs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    change_id: Mapped[int] = mapped_column(ForeignKey('road_changes.id'))
    radius_m: Mapped[float] = mapped_column(Float)
    window_days: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String(40))

class Candidate(Base):
    __tablename__ = 'candidates'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('match_runs.id'), index=True)
    clip_id: Mapped[int] = mapped_column(ForeignKey('drive_clips.id'))
    change_id: Mapped[int] = mapped_column(ForeignKey('road_changes.id'))
    matched_at: Mapped[str] = mapped_column(String(40))
    distance_m: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    is_duplicate: Mapped[bool] = mapped_column(default=False)
    review_status: Mapped[str] = mapped_column(String(24), default='pending')
    review_note: Mapped[str] = mapped_column(Text, default='')
    reviewed_at: Mapped[str] = mapped_column(String(40), default='')

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[str] = mapped_column(Text)
    at: Mapped[str] = mapped_column(String(40))

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def init_db():
    ROOT.joinpath('data').mkdir(parents=True,exist_ok=True)
    Base.metadata.create_all(engine)
