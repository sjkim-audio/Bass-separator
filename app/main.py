from fastapi import FastAPI, File, UploadFile
import shutil
import os

# FastAPI 앱 인스턴스 생성
app = FastAPI(
    title="Bass Separator API",
    description="Demucs 기반 베이스 오디오 소스 분리 API",
    version="1.0.0"
)

# 업로드된 파일을 임시로 저장할 디렉토리 설정
UPLOAD_DIR = "app/temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/")
def read_root():
    """서버가 정상적으로 켜졌는지 확인하는 기본 엔드포인트"""
    return {"message": "Bass Separator API Server is running."}

@app.post("/api/v1/separate")
async def separate_audio(file: UploadFile = File(...)):
    """
    클라이언트로부터 오디오 파일을 업로드받는 엔드포인트
    현재는 파일을 서버에 저장하고 파일명만 반환하는 형태입니다.
    """
    try:
        # 업로드된 파일을 저장할 경로 지정
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        
        # 클라이언트가 보낸 파일을 서버의 디스크에 복사
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # TODO: 이 부분에 Demucs 추론(Inference) 로직이 추가될 예정입니다.
        
        return {
            "status": "success",
            "filename": file.filename,
            "message": "파일이 성공적으로 업로드되었습니다. (분리 로직 추가 예정)",
            "saved_path": file_path
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}
