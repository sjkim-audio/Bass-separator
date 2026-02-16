from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
import shutil
import os
from app.services.separator import run_demucs  # 방금 만든 모듈 import

app = FastAPI(
    title="Bass Separator API",
    description="업로드된 오디오에서 베이스 트랙을 분리하여 반환합니다."
)

# 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "temp_uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "temp_outputs")

# 디렉토리 자동 생성
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.post("/api/v1/separate")
async def separate_audio(file: UploadFile = File(...)):
    # 1. 파일 저장
    temp_file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 2. Demucs 분리 실행 (오래 걸릴 수 있음)
    separated_bass_path = run_demucs(temp_file_path, OUTPUT_DIR)
    
    if separated_bass_path and os.path.exists(separated_bass_path):
        # 3. 분리된 파일(bass.wav)을 클라이언트에게 전송
        return FileResponse(
            path=separated_bass_path, 
            filename=f"bass_{file.filename}", # 다운로드될 때 파일명
            media_type="audio/wav"
        )
    else:
        raise HTTPException(status_code=500, detail="Audio separation failed.")
