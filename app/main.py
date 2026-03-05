# app/main.py
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
import shutil

from app.services.separator import run_demucs
# Phase 2-4: 우리가 이전 단계에서 수정한 파이프라인 모듈 호출
from src.main import run_transcription_pipeline 

app = FastAPI(
    title="Bass Transcription API",
    description="업로드된 오디오에서 베이스를 분리하고, 타브 악보/MIDI 데이터를 반환합니다."
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "temp_uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "temp_outputs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def cleanup_files(*file_paths: str):
    """[Fix 2] Storage Leak 방지: 백그라운드 파일 삭제"""
    for path in file_paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
                print(f"✅ 임시 파일 삭제 완료: {path}")
        except Exception as e:
            print(f"❌ 임시 파일 삭제 실패: {path} - {e}")

# [Fix 1] 'async def' 제거 -> 'def' 사용으로 스레드풀 분리 (Event Loop Blocking 방지)
@app.post("/api/v1/transcribe")
def transcribe_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    temp_file_path = os.path.join(UPLOAD_DIR, file.filename)
    
    # 1. 파일 저장 (동기 I/O 블로킹 최소화를 위해 shutil 사용)
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        # 2. Phase 1: Demucs 분리 실행 (CPU/GPU Bound)
        separated_bass_path = run_demucs(temp_file_path, OUTPUT_DIR)
        
        if not separated_bass_path or not os.path.exists(separated_bass_path):
            raise HTTPException(status_code=500, detail="Phase 1: Audio separation failed.")
            
        # 3. [Fix 3] Phase 2~4: Transcription & Quantization (E2E 파이프라인 통합)
        # TODO: 현재 콘솔 출력 방식의 run_transcription_pipeline을 JSON/문자열 반환으로 리팩토링해야 함.
        # result_tab = run_transcription_pipeline(separated_bass_path)
        
        # 임시 조치: 현재는 분리된 파일만 반환
        result_response = FileResponse(
            path=separated_bass_path, 
            filename=f"bass_{file.filename}", 
            media_type="audio/wav"
        )
        
        # 4. 백그라운드 태스크 등록 (응답 완료 직후 실행됨)
        background_tasks.add_task(cleanup_files, temp_file_path, separated_bass_path)
        
        return result_response

    except Exception as e:
        # 에러 발생 시에도 원본 파일은 반드시 삭제해야 함
        cleanup_files(temp_file_path)
        raise HTTPException(status_code=500, detail=str(e))
