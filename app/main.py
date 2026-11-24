import os
import time
import uuid
import shutil
from pathlib import Path
from contextlib import asynccontextmanager

# 윈도우 환경 DLL 충돌 방지
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# DB 의존성 및 ORM 모델 임포트
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.core import get_db, AsyncSessionLocal
from app.database.models import TranscriptionTask, TaskStatus

# 내부 스키마 임포트
from app.schemas.response import TranscriptionResponse, TranscriptionMetadata, BassNoteEvent

# Celery 비동기 워커 태스크 임포트
from app.worker import run_pipeline_celery_task

# 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "temp_uploads")
RESULT_DIR = "outputs"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 자가 치유 (Self-healing): 서버 기동 시 PROCESSING 상태로 방치된 고아 태스크를 FAILED로 정산
    print("🔄 [Lifespan] 자가 치유(Self-healing) 정산 시작: 고아 태스크(PROCESSING) 스캔 중...")
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TranscriptionTask).where(TranscriptionTask.status == TaskStatus.PROCESSING)
        )
        orphan_tasks = result.scalars().all()
        if orphan_tasks:
            for task in orphan_tasks:
                task.status = TaskStatus.FAILED
                task.error_log = "Orphaned task: Server restarted or worker died during processing."
            await db.commit()
            print(f"⚠️ [Lifespan] 고아 태스크 총 {len(orphan_tasks)}건을 FAILED 상태로 정산 완료.")
        else:
            print("✅ [Lifespan] 처리 대기 중인 고아 태스크가 없습니다.")

    # 2. 파일 시스템 TTL 스캔 (만료된 샌드박스 폴더 강제 삭제)
    print("🧹 [Lifespan] 만료된 샌드박스 디렉토리 스캔 중...")
    now = time.time()
    if os.path.exists(RESULT_DIR):
        for item in os.listdir(RESULT_DIR):
            item_path = os.path.join(RESULT_DIR, item)
            if os.path.isdir(item_path):
                if now - os.path.getmtime(item_path) > 3600:
                    shutil.rmtree(item_path, ignore_errors=True)
                    print(f"🗑️ [Lifespan] 만료된 샌드박스 삭제 완료: {item}")
    yield

app = FastAPI(
    title="Bass Transcription API",
    description="Distributed bass separation and E2E transcription with Celery and PostgreSQL.",
    lifespan=lifespan
)

# 정적 파일 서빙: outputs 폴더 전체를 라우팅
app.mount("/api/v1/downloads", StaticFiles(directory="outputs"), name="downloads")


@app.post("/api/v1/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    MAX_SIZE = 50 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File too large (Max 50MB)")
    
    task_id = str(uuid.uuid4())
    temp_file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")

    # 메모리에 로드된 바이트 배열을 즉시 디스크에 기록하여 I/O 블로킹 최소화
    with open(temp_file_path, "wb") as f:
        f.write(content)

    # [DB Insert] 작업 수락 시 즉각 PENDING 레코드 생성
    new_task = TranscriptionTask(id=task_id, status=TaskStatus.PENDING)
    db.add(new_task)
    await db.commit()

    # [Celery Dispatch] FastAPI 백그라운드 태스크 및 세마포어를 제거하고 Redis 큐로 작업 위임
    run_pipeline_celery_task.delay(task_id, temp_file_path)

    return JSONResponse(
        status_code=202,
        content={
            "status": TaskStatus.PENDING.value,
            "task_id": task_id,
            "message": "Inference successfully enqueued to Celery worker."
        }
    )


@app.get("/api/v1/tasks/{task_id}")
async def get_status(task_id: str, db: AsyncSession = Depends(get_db)):
    # [DB Select] 파일 시스템 접근 없이 PK(id) 기반 초고속 데이터베이스 조회
    task = await db.get(TranscriptionTask, task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    response = {"status": task.status.value, "task_id": task_id}
    
    if task.status == TaskStatus.SUCCESS and task.result_metadata:
        response.update(task.result_metadata)
    elif task.status == TaskStatus.FAILED and task.error_log:
        response["error"] = task.error_log
        
    return response
