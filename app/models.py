from datetime import datetime, timezone
from sqlalchemy import create_engine, ForeignKey, String, Integer, Date, DateTime, Text, Boolean, Float, JSON, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, relationship
from .config import DATABASE_URL

def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Video(Base):
    __tablename__ = 'videos'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    youtube_id: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    youtube_url: Mapped[str] = mapped_column(String(300))
    title: Mapped[str] = mapped_column(String(320), default='Video de YouTube')
    medium: Mapped[str] = mapped_column(String(30), default='television')
    stage: Mapped[str] = mapped_column(String(30), default='campana')
    program: Mapped[str] = mapped_column(String(160), default='')
    date: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(32), default='queued')
    source_language: Mapped[str] = mapped_column(String(15), default='es')
    error: Mapped[str] = mapped_column(Text, default='')
    duration_seconds: Mapped[float] = mapped_column(Float, default=0)
    no_mentions: Mapped[bool] = mapped_column(Boolean, default=False)
    no_mentions_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    no_mentions_reviewer: Mapped[str] = mapped_column(String(80), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    segments: Mapped[list['Segment']] = relationship(back_populates='video', cascade='all, delete-orphan')
    mentions: Mapped[list['Mention']] = relationship(back_populates='video', cascade='all, delete-orphan')

class Segment(Base):
    __tablename__ = 'segments'
    __table_args__ = (UniqueConstraint('video_id', 'ordinal'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey('videos.id', ondelete='CASCADE'), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)
    speaker: Mapped[str] = mapped_column(String(100), default='')
    video: Mapped[Video] = relationship(back_populates='segments')

class Mention(Base):
    __tablename__ = 'mentions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey('videos.id', ondelete='CASCADE'), index=True)
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    speaker: Mapped[str] = mapped_column(String(200), default='No identificado')
    subject: Mapped[str] = mapped_column(String(240), default='No identificado')
    quote: Mapped[str] = mapped_column(Text, default='')
    context: Mapped[str] = mapped_column(Text, default='')
    genre: Mapped[str] = mapped_column(String(100), default='sin_clasificar')
    topic: Mapped[str] = mapped_column(String(140), default='otros')
    tone: Mapped[str] = mapped_column(String(24), default='neutra')
    findings: Mapped[list] = mapped_column(JSON, default=list)
    extra_data: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_segments: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(24), default='pending', index=True)
    review_note: Mapped[str] = mapped_column(Text, default='')
    reviewer: Mapped[str] = mapped_column(String(80), default='')
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ai_model: Mapped[str] = mapped_column(String(60), default='')
    ai_raw: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    video: Mapped[Video] = relationship(back_populates='mentions')

class Job(Base):
    __tablename__ = 'jobs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey('videos.id', ondelete='CASCADE'), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(20), default='queued', index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default='')
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Audit(Base):
    __tablename__ = 'audit_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(50))
    entity: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[int] = mapped_column(Integer)
    old_values: Mapped[dict] = mapped_column(JSON, default=dict)
    new_values: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

def init_db():
    Base.metadata.create_all(bind=engine)
