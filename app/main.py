import os
import time
import uuid
import shutil
import asyncio
import json
from src.core.pipeline import run_transcription_pipeline

# 윈도우 환경 DLL 충돌 방지
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict

# 내부 모듈 임포트
from app.schemas.response import TranscriptionResponse, TranscriptionMetadata, BassNoteEvent
from app.services.separator import run_demucs
from src.main import run_transcription_pipeline

app = FastAPI(
    title="Bass Transcription API",
    description="Bass separation and E2E transcription with concurrency control."
)

# 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "temp_uploads")
# [ADR-003] 상태 저장소: 결과 JSON 및 MIDI 보관 경로
RESULT_DIR = os.path.join(BASE_DIR, "outputs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

# [Fix] GPU OOM 방어: 동시 추론 실행을 1개로 제한하는 세마포어
gpu_semaphore = asyncio.Semaphore(1)

def cleanup_files(*file_paths: str):
    """임시 업로드 파일 삭제 (결과물인 outputs/ 내부 파일은 보존)"""
    for path in file_paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"⚠️ 파일 삭제 실패: {path} - {e}")

def save_result_to_disk(task_id: str, data: TranscriptionResponse):
    """[Phase 3] 상태 저장소: 추론 결과를 JSON으로 직렬화하여 디스크에 보존"""
    result_path = os.path.join(RESULT_DIR, f"{task_id}.json")
    with open(result_path, "w", encoding="utf-8") as f:
        # Pydantic 모델을 dict로 변환 후 JSON 저장
        json.dump(data.model_dump(), f, indent=4, ensure_ascii=False)
    print(f"💾 결과 저장 완료: {result_path}")

async def run_pipeline_task(task_id: str, temp_file_path: str):
    async with gpu_semaphore:
        # ...
        try:
            # ...
            ascii_tab, bpm, raw_events = await loop.run_in_executor(None, run_transcription_pipeline, separated_bass_path)

            note_dtos = [
                BassNoteEvent(
                    start_time=e.time, midi_note=e.midi_note,
                    string_idx=e.string_idx, fret=e.fret, confidence=getattr(e, 'confidence', 1.0)
                ) for e in raw_events
            ]

            processing_time_ms = (time.perf_counter() - start_time_perf) * 1000
            
            # [Fix] 누락되었던 bpm과 ascii_tab 추가 반환
            response_data = TranscriptionResponse(
                bpm=bpm,
                ascii_tab=ascii_tab,
                metadata=TranscriptionMetadata(task_id=task_id, processing_time_ms=processing_time_ms),
                events=note_dtos
            )

            save_result_to_disk(task_id, response_data)
            
        except Exception as e:
            print(f"❌ 파이프라인 에러 [{task_id}]: {e}")
        finally:
            cleanup_files(temp_file_path, separated_bass_path)

@app.post("/api/v1/transcribe")
async def transcribe_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    [Main Endpoint] 
    10MB 제한 및 비동기 수락(202 Accepted)을 처리한다.
    """
    # [Security] 파일 크기 제한 (10MB)
    MAX_SIZE = 10 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File too large (Max 10MB)")
    await file.seek(0)

    task_id = str(uuid.uuid4())
    temp_file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")

    # 파일 임시 저장
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # [Async Workflow] 백그라운드 태스크로 연산 위임
    background_tasks.add_task(run_pipeline_task, task_id, temp_file_path)

    # 202 Accepted 반환 (클라이언트는 task_id로 Polling 시작)
    return JSONResponse(
        status_code=202,
        content={"status": "ACCEPTED", "task_id": task_id, "message": "Inference started in background."}
    )

@app.get("/api/v1/status/{task_id}")
async def get_status(task_id: str):
    """[Polling Endpoint] 결과 파일이 생성되었는지 확인하여 반환"""
    result_path = os.path.join(RESULT_DIR, f"{task_id}.json")
    
    if os.path.exists(result_path):
        with open(result_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"status": "SUCCESS", "data": data}
    
    return {"status": "PROCESSING", "task_id": task_id}
