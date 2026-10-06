import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Enum, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

class Base(DeclarativeBase):
    pass

class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class TranscriptionTask(Base):
    __tablename__ = "transcription_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False)
    
    # 시간 추적 (UTC 기준)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    # 실패 시 원인 추적용
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 하이브리드 스토리지 원칙: 악보, BPM, 파일 경로 등의 메타데이터만 저장
    result_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
