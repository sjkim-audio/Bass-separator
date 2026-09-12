import os
import time
import uuid
import shutil
import asyncio
import json
from pathlib import Path
from contextlib import asynccontextmanager

# 윈도우 환경 DLL 충돌 방지
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

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

# 🔴 [핵심 보완 2] 서버 부팅 시 고아 데이터(Zombie) 일괄 정리 로직
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
    # Shutdown 시 동작 로직 (현재는 불필요)

app = FastAPI(
    title="Bass Transcription API",
    description="Bass separation and E2E transcription with concurrency control.",
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

def save_result_to_disk(save_path: Path, data: dict):
    """상태 저장소: 추론 결과를 JSON으로 직렬화하여 샌드박스에 보존"""
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"💾 결과 저장 완료: {save_path}")

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
    
    async with gpu_semaphore:
        try:
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
            
            # 2. 추출된 베이스 및 MR 경로를 채보 파이프라인으로 전달
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

            save_result_to_disk(task_out_dir / f"{task_id}.json", response_data.model_dump())
            
        except Exception as e:
            print(f"❌ 파이프라인 에러 [{task_id}]: {repr(e)}")
            error_payload = {"status": "FAILED", "error": repr(e), "task_id": task_id}
            save_result_to_disk(task_out_dir / f"{task_id}.json", error_payload)
            
        finally:
            cleanup_files(temp_file_path)
            # 🔴 [핵심 보완 1] 세마포어 대기열(Queue)을 모두 통과하고 처리가 끝난 직후에 타이머 가동
            asyncio.create_task(ttl_cleanup(task_out_dir, 3600))

@app.post("/api/v1/transcribe")
async def transcribe_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    MAX_SIZE = 50 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File too large (Max 50MB)")
    await file.seek(0)

    task_id = str(uuid.uuid4())
    temp_file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")

    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 태스크 큐에 작업만 할당 (TTL 타이머는 여기서 가동하지 않음)
    background_tasks.add_task(run_pipeline_task, task_id, temp_file_path)

    return JSONResponse(
        status_code=202,
        content={"status": "ACCEPTED", "task_id": task_id, "message": "Inference started in background."}
    )

@app.get("/api/v1/tasks/{task_id}")
async def get_status(task_id: str):
    result_path = Path(RESULT_DIR) / task_id / f"{task_id}.json"
    
    if result_path.exists():
        with open(result_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if data.get("status") != "FAILED":
            data["status"] = "SUCCESS"
        return data
    
    return {"status": "PROCESSING", "task_id": task_id}
