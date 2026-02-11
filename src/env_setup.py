import subprocess
import sys
import os
import shutil
import importlib.util

def run_command(command, description):
    """
    Runs a shell command and prints the status.
    """
    print(f"📦 {description} 진행 중...")
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"✅ {description} 완료.")
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} 실패.")
        print(f"   에러 로그: {e.stderr}")

def check_system_dependencies():
    """
    Checks and installs system-level dependencies (e.g., FFmpeg).
    """
    print("\n🔧 [시스템] 필수 도구 확인 중...")
    
    # Check FFmpeg (Crucial for audio processing)
    if shutil.which("ffmpeg") is None:
        print("⚠️ FFmpeg가 없습니다. apt-get으로 설치합니다...")
        run_command(['apt-get', 'update', '-qq'], "패키지 목록 업데이트")
        run_command(['apt-get', 'install', '-y', 'ffmpeg'], "FFmpeg 설치")
    else:
        print("✅ FFmpeg가 이미 설치되어 있습니다.")

def install_python_requirements(req_path="requirements.txt"):
    """
    Installs Python libraries from requirements.txt.
    """
    print("\n🐍 [파이썬] 라이브러리 확인 중...")
    
    if os.path.exists(req_path):
        print(f"📄 {req_path} 파일을 발견했습니다. 의존성 패키지를 설치합니다...")
        # -q: Quiet mode (less logs), --upgrade: Ensure latest versions
        run_command([sys.executable, "-m", "pip", "install", "-r", req_path], "패키지 일괄 설치")
    else:
        print(f"⚠️ 경고: 현재 경로에 {req_path} 파일이 없습니다.")
        print("   일괄 설치를 건너뜁니다. 파일 위치를 확인해주세요.")

def init_colab_env():
    """
    [Main Entry Point]
    Sets up the complete environment for Bass Separation.
    1. Install System Dependencies (FFmpeg)
    2. Install Python Dependencies (requirements.txt)
    3. Perform a final health check
    """
    print("🚀 환경 설정을 시작합니다...")

    # 1. System Setup
    check_system_dependencies()

    # 2. Python Setup
    install_python_requirements()

    # 3. Health Check (Verify critical imports)
    print("\n🏥 설치 무결성 점검 (Health Check)...")
    critical_libs = ["demucs", "torchaudio", "librosa", "museval"]
    missing = []
    
    for lib in critical_libs:
        if importlib.util.find_spec(lib) is None:
            missing.append(lib)
    
    if not missing:
        print("✅ 필수 라이브러리가 모두 정상적으로 준비되었습니다!")
    else:
        print(f"❌ 다음 라이브러리가 누락되었습니다: {', '.join(missing)}")
        print("   '!pip install -r requirements.txt' 명령어를 수동으로 실행해보세요.")

    print("\n🎉 모든 환경 설정이 완료되었습니다!")
