import os
import time
import uuid
import shutil
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

# 윈도우 환경 DLL 충돌 방지
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# 🔴 DB 의존성 및 ORM 모델 임포트
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.core import get_db, AsyncSessionLocal
from app.database.models import TranscriptionTask, TaskStatus

# 내부 모듈 임포트
from app.schemas.response import TranscriptionResponse, TranscriptionMetadata, BassNoteEvent
from src.renderers.midi_renderer import MidiRenderer
from src.core.demucs_runner import separate_and_generate_stems
from src.core.pipeline import run_transcription_pipeline

# 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "temp_uploads")
RESULT_DIR = "outputs"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🧹 [Startup] 이전 세션의 고아(Orphan) 태스크 디렉토리를 스캔합니다...")
    now = time.time()
    if os.path.exists(RESULT_DIR):
        for item in os.listdir(RESULT_DIR):
            item_path = os.path.join(RESULT_DIR, item)
            if os.path.isdir(item_path):
                # 생성된 지 1시간(3600초)이 지난 폴더 강제 삭제
                if now - os.path.getmtime(item_path) > 3600:
                    shutil.rmtree(item_path, ignore_errors=True)
                    print(f"🗑️ [Startup] 만료된 태스크 삭제 완료: {item}")
    yield

app = FastAPI(
    title="Bass Transcription API",
    description="Bass separation and E2E transcription with async database state management.",
    lifespan=lifespan
)

# 정적 파일 서빙: outputs 폴더 전체를 라우팅
app.mount("/api/v1/downloads", StaticFiles(directory="outputs"), name="downloads")

# GPU OOM 방어: 동시 추론 실행을 1개로 제한하는 세마포어
gpu_semaphore = asyncio.Semaphore(1)

def cleanup_files(*file_paths: str):
    """임시 업로드 파일 삭제"""
    for path in file_paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"⚠️ 파일 삭제 실패: {path} - {e}")

async def ttl_cleanup(task_dir: Path, delay_sec: int = 3600):
    """지정된 시간(TTL) 경과 후 태스크 샌드박스를 강제 삭제하여 스토리지를 확보합니다."""
    await asyncio.sleep(delay_sec)
    if task_dir.exists():
        shutil.rmtree(task_dir, ignore_errors=True)
        print(f"🧹 [TTL 클린업] 스토리지 최적화: 만료된 태스크 삭제 완료 ({task_dir})")

async def run_pipeline_task(task_id: str, temp_file_path: str):
    # [Task 격리] 요청별 전용 샌드박스 디렉토리 생성
    task_out_dir = Path(RESULT_DIR) / task_id
    task_out_dir.mkdir(parents=True, exist_ok=True)

    bass_path = None
    bassless_path = None
    
    # [DB Update 1] 상태: PROCESSING (세션 즉시 종료하여 커넥션 반환)
    async with AsyncSessionLocal() as db:
        task = await db.get(TranscriptionTask, task_id)
        if task:
            task.status = TaskStatus.PROCESSING
            await db.commit()

    try:
        async with gpu_semaphore:
            # 1. 4-Stem 분리 및 MR 병합 로직 호출
            raw_bass_path, raw_bassless_path = await separate_and_generate_stems(
                temp_file_path, 
                output_dir=str(task_out_dir)
            )
            
            # [Cleanup & Isolation] 핵심 파일만 샌드박스 루트로 이동
            new_bass_path = task_out_dir / "bass.wav"
            new_bassless_path = task_out_dir / "bassless_backing.wav"
            
            shutil.move(str(raw_bass_path), str(new_bass_path))
            if raw_bassless_path and os.path.exists(raw_bassless_path):
                shutil.move(str(raw_bassless_path), str(new_bassless_path))
                bassless_path = str(new_bassless_path)
            
            bass_path = str(new_bass_path)

            htdemucs_dir = task_out_dir / "htdemucs"
            if htdemucs_dir.exists():
                shutil.rmtree(htdemucs_dir, ignore_errors=True)

            loop = asyncio.get_running_loop()
            start_time_perf = time.perf_counter()
            
            # 2. 추출된 베이스 및 MR 경로를 채보 파이프라인으로 전달 (DB 무관)
            ascii_tab, bpm, fingered_events, quantized_events = await loop.run_in_executor(
                None, run_transcription_pipeline, bass_path, bassless_path
            )

            # 3. 빈 노트 예외 처리 방어 로직 (MIDI 렌더링 우회)
            midi_filename = f"{task_id}.mid"
            midi_output_path = task_out_dir / midi_filename
            
            if fingered_events:
                MidiRenderer.render_midi(fingered_events, bpm, str(midi_output_path))
            else:
                print(f"⚠️ [{task_id}] 베이스 노트가 감지되지 않아 MIDI 생성을 건너뜁니다.")
                ascii_tab = "⚠️ 감지된 베이스 노트가 없습니다."

            note_dtos = [
                BassNoteEvent(
                    start_time=e.time, 
                    duration=getattr(e, 'duration', 0.0),
                    midi_note=e.midi_note,
                    string_idx=e.string_idx, 
                    fret=e.fret, 
                    confidence=getattr(e, 'confidence', 1.0)
                ) for e in quantized_events
            ]

            processing_time_ms = (time.perf_counter() - start_time_perf) * 1000
            
            response_data = TranscriptionResponse(
                bpm=bpm,
                ascii_tab=ascii_tab,
                metadata=TranscriptionMetadata(
                    task_id=task_id, 
                    processing_time_ms=processing_time_ms,
                    bass_audio_url=f"/api/v1/downloads/{task_id}/bass.wav",
                    bassless_audio_url=f"/api/v1/downloads/{task_id}/bassless_backing.wav",
                    midi_url=f"/api/v1/downloads/{task_id}/{midi_filename}" 
                ),
                events=note_dtos
            )

        # [DB Update 2] 상태: SUCCESS 및 결과 영구 저장
        async with AsyncSessionLocal() as db:
            task = await db.get(TranscriptionTask, task_id)
            if task:
                task.status = TaskStatus.SUCCESS
                task.result_metadata = response_data.model_dump()
                await db.commit()
                print(f"💾 [{task_id}] DB 상태 업데이트 완료: SUCCESS")
                
    except Exception as e:
        print(f"❌ 파이프라인 에러 [{task_id}]: {repr(e)}")
        # [DB Update 3] 상태: FAILED 및 예외 로그 저장
        async with AsyncSessionLocal() as db:
            task = await db.get(TranscriptionTask, task_id)
            if task:
                task.status = TaskStatus.FAILED
                task.error_log = repr(e)
                await db.commit()
                
    finally:
        cleanup_files(temp_file_path)
        # 세마포어 통과 및 처리가 모두 종료된 후 안전하게 TTL 타이머 가동
        asyncio.create_task(ttl_cleanup(task_out_dir, 3600))

@app.post("/api/v1/transcribe")
async def transcribe_audio(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    MAX_SIZE = 50 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File too large (Max 50MB)")
    await file.seek(0)

    task_id = str(uuid.uuid4())
    temp_file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")

    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 🔴 [DB Insert] 작업 수락 시 즉각 PENDING 레코드 생성
    new_task = TranscriptionTask(id=task_id, status=TaskStatus.PENDING)
    db.add(new_task)
    await db.commit()

    background_tasks.add_task(run_pipeline_task, task_id, temp_file_path)

    return JSONResponse(
        status_code=202,
        content={"status": TaskStatus.PENDING.value, "task_id": task_id, "message": "Inference started in background."}
    )

@app.get("/api/v1/tasks/{task_id}")
async def get_status(task_id: str, db: AsyncSession = Depends(get_db)):
    # 🔴 [DB Select] 파일 시스템 접근 없이 PK(id) 기반 초고속 데이터베이스 조회
    task = await db.get(TranscriptionTask, task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    response = {"status": task.status.value, "task_id": task_id}
    
    if task.status == TaskStatus.SUCCESS and task.result_metadata:
        # Pydantic DTO가 dict로 직렬화되어 있으므로 곧바로 병합(Merge)하여 반환
        response.update(task.result_metadata)
    elif task.status == TaskStatus.FAILED and task.error_log:
        response["error"] = task.error_log
        
    return response
