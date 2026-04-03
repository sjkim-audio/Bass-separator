# app/main.py 
import os
import time
import uuid
import shutil
import asyncio
import json
from pathlib import Path

# 윈도우 환경 DLL 충돌 방지
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import Dict

# 내부 모듈 임포트
from app.schemas.response import TranscriptionResponse, TranscriptionMetadata, BassNoteEvent
from src.renderers.midi_renderer import MidiRenderer
from src.core.demucs_runner import separate_and_generate_stems
from src.core.pipeline import run_transcription_pipeline

app = FastAPI(
    title="Bass Transcription API",
    description="Bass separation and E2E transcription with concurrency control."
)
app.mount("/api/v1/downloads", StaticFiles(directory="outputs"), name="downloads")

# 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "temp_uploads")
RESULT_DIR = "outputs"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

# GPU OOM 방어: 동시 추론 실행을 1개로 제한하는 세마포어
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
    """상태 저장소: 추론 결과를 JSON으로 직렬화하여 디스크에 보존"""
    result_path = os.path.join(RESULT_DIR, f"{task_id}.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(data.model_dump(), f, indent=4, ensure_ascii=False)
    print(f"💾 결과 저장 완료: {result_path}")


async def run_pipeline_task(task_id: str, temp_file_path: str):
    os.makedirs("outputs", exist_ok=True)

    bass_path = None
    bassless_path = None
    
    async with gpu_semaphore:
        try:
            # 1. 4-Stem 분리 및 MR 병합 로직 호출
            bass_path, bassless_path = await separate_and_generate_stems(temp_file_path)
            loop = asyncio.get_running_loop()
            start_time_perf = time.perf_counter()
            
            # 2. 추출된 베이스 및 MR 경로를 채보 파이프라인으로 전달 (bassless_path 추가)
            ascii_tab, bpm, quantized_events = await loop.run_in_executor(
                None, run_transcription_pipeline, bass_path, bassless_path
            )

            # 3. 빈 노트 예외 처리 방어 로직 (MIDI 렌더링 우회)
            midi_output_path = f"outputs/{task_id}.mid"
            if quantized_events:
                MidiRenderer.render_midi(quantized_events, bpm, midi_output_path)
            else:
                print(f"⚠️ [{task_id}] 베이스 노트가 감지되지 않아 MIDI 생성을 건너뜁니다.")
                ascii_tab = "⚠️ 감지된 베이스 노트가 없습니다. (오디오 볼륨이 너무 작거나 베이스가 없는 구간일 수 있습니다.)"

            note_dtos = [
                BassNoteEvent(
                    start_time=e.time, midi_note=e.midi_note,
                    string_idx=e.string_idx, fret=e.fret, confidence=getattr(e, 'confidence', 1.0)
                ) for e in quantized_events
            ]

            processing_time_ms = (time.perf_counter() - start_time_perf) * 1000
            
            response_data = TranscriptionResponse(
                bpm=bpm,
                ascii_tab=ascii_tab,
                metadata=TranscriptionMetadata(
                    task_id=task_id, 
                    processing_time_ms=processing_time_ms,
                    bass_audio_url=f"/api/v1/downloads/{task_id}/bass",
                    bassless_audio_url=f"/api/v1/downloads/{task_id}/bassless",
                    midi_url=f"/api/v1/downloads/{task_id}.mid" 
                ),
                events=note_dtos
            )

            save_result_to_disk(task_id, response_data)
            
        except Exception as e:
            print(f"❌ 파이프라인 에러 [{task_id}]: {repr(e)}")
            error_payload = {"status": "failed", "error": repr(e), "task_id": task_id}
            
            with open(f"outputs/{task_id}.json", "w", encoding="utf-8") as f:
                json.dump(error_payload, f)
                
        finally:
            files_to_delete = [temp_file_path]
            
            if bass_path is not None:
                demucs_out_dir = Path(bass_path).parent
                
                drums_path = demucs_out_dir / "drums.wav"
                vocals_path = demucs_out_dir / "vocals.wav"
                other_path = demucs_out_dir / "other.wav"
                
                for p in [drums_path, vocals_path, other_path]:
                    if p.exists():
                        files_to_delete.append(str(p))
            
            try:
                cleanup_files(*files_to_delete)
            except Exception as cleanup_error:
                print(f"⚠ [경고] 임시 파일 정리 중 에러 발생: {cleanup_error}")

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

    background_tasks.add_task(run_pipeline_task, task_id, temp_file_path)

    return JSONResponse(
        status_code=202,
        content={"status": "ACCEPTED", "task_id": task_id, "message": "Inference started in background."}
    )

@app.get("/api/v1/tasks/{task_id}")
async def get_status(task_id: str):
    result_path = os.path.join(RESULT_DIR, f"{task_id}.json")
    
    if os.path.exists(result_path):
        with open(result_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        data["status"] = "SUCCESS"
        return data
    
    return {"status": "PROCESSING", "task_id": task_id}