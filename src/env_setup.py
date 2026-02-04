import subprocess
import sys
import importlib.util

def run_command(command, description):
    """내부 헬퍼 함수: 명령어 실행 및 로그 출력"""
    print(f"📦 {description} 진행 중...")
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"✅ {description} 완료.")
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} 실패: {e.stderr}")

def check_and_install_demucs():
    """Demucs 설치 확인 및 설치"""
    if importlib.util.find_spec("demucs") is None:
        print("⚠️ Demucs가 감지되지 않아 설치합니다.")
        run_command(['pip', 'install', 'demucs'], "Demucs 라이브러리 설치")
    else:
        print("✅ Demucs가 이미 설치되어 있습니다.")

def init_colab_env():
    """
    [통합 환경 설정]
    1. FFmpeg 시스템 설치
    2. Audio 라이브러리 충돌 해결 (torchaudio/torchcodec)
    3. Demucs 라이브러리 설치
    """
    print("\n🔧 [System] 오디오 처리 환경 점검 및 초기화...\n")
    
    # 1. FFmpeg 점검
    ffmpeg_check = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True)
    if ffmpeg_check.returncode != 0:
        run_command(['apt-get', 'update', '-qq'], "시스템 패키지 업데이트")
        run_command(['apt-get', 'install', '-y', 'ffmpeg'], "FFmpeg 설치")
    else:
        print("✅ FFmpeg가 이미 설치되어 있습니다.")

    # 2. Demucs 설치
    check_and_install_demucs()

    # 3. 라이브러리 호환성 점검 (가장 마지막에 수행)
    try:
        import torchcodec
        import torchaudio
        print("✅ 오디오 코덱 라이브러리(torchaudio, torchcodec) 정상 작동.")
    except (ImportError, RuntimeError, OSError):
        print("⚠️ 라이브러리 버전 충돌 감지! 재설치 루틴 실행 (약 1분 소요)...")
        run_command(['pip', 'uninstall', '-y', 'torchcodec', 'torchaudio'], "충돌 패키지 제거")
        run_command(['pip', 'install', 'torchaudio', 'soundfile'], "torchaudio 재설치")
        run_command(['pip', 'install', 'torchcodec'], "torchcodec 재설치")
        print("\n🔄 [완료] 라이브러리 복구됨.")

    print("\n🎉 모든 환경 설정이 준비되었습니다!")
