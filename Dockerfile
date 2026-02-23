# 1. 파이썬 3.10 슬림 버전 이미지 사용
FROM python:3.10-slim

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. 오디오 처리(librosa, demucs)에 필요한 리눅스 시스템 필수 패키지 설치
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# 4. 파이썬 라이브러리 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 소스 코드 복사 (docker-compose의 volume 덮어쓰기 전 기본 구조)
COPY . .

# 6. FastAPI 포트 개방
EXPOSE 8000