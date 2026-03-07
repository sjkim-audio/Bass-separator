# app/main.py
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
import shutil
from app.schemas.response import TranscriptionResponse, NoteDto
from app.services.separator import run_demucs
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

@app.post("/api/v1/transcribe", response_model=TranscriptionResponse)
def transcribe_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    temp_file_path = os.path.join(UPLOAD_DIR, file.filename)
    
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    separated_bass_path = None
    try:
        # Phase 1: Separation
        separated_bass_path = run_demucs(temp_file_path, OUTPUT_DIR)
        if not separated_bass_path or not os.path.exists(separated_bass_path):
            raise ValueError("Phase 1: Audio separation failed.")
            
        # Phase 2~4: Transcription (E2E 파이프라인 연결 완료)
        ascii_tab, bpm, raw_events = run_transcription_pipeline(separated_bass_path)
        
        # Dataclass(NoteEvent) -> Pydantic(NoteDto) 직렬화 매핑
        note_dtos = [
            NoteDto(
                time=e.time,
                midi_note=e.midi_note,
                string_idx=e.string_idx,
                fret=e.fret,
                grid_index=e.grid_index,
                quantized_time=e.quantized_time
            ) for e in raw_events
        ]
        
        # 파일 정리 태스크 예약
        background_tasks.add_task(cleanup_files, temp_file_path, separated_bass_path)
        
        return TranscriptionResponse(
            bpm=bpm,
            ascii_tab=ascii_tab,
            notes=note_dtos
        )

    except Exception as e:
        cleanup_files(temp_file_path, separated_bass_path)
        raise HTTPException(status_code=500, detail=str(e))
