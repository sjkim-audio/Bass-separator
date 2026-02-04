# 파일 위치: src/env_setup.py
import subprocess
import sys

def run_command(command, description):
    """내부 헬퍼 함수: 명령어 실행 및 로그 출력"""
    print(f"📦 {description}...")
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"✅ {description} 완료.")
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} 실패: {e.stderr}")

def init_colab_env():
    """
    Colab 환경 초기화 함수
    FFmpeg 및 오디오 라이브러리 충돌을 자동으로 감지하고 해결합니다.
    """
    print("🔧 [System] 오디오 처리 환경 점검 중...\n")
    
    # 1. FFmpeg 점검
    ffmpeg_check = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True)
    if ffmpeg_check.returncode != 0:
        print("⚠️ FFmpeg가 감지되지 않아 설치합니다.")
        run_command(['apt-get', 'update', '-qq'], "시스템 패키지 업데이트")
        run_command(['apt-get', 'install', '-y', 'ffmpeg'], "FFmpeg 설치")
    else:
        print("✅ FFmpeg가 이미 설치되어 있습니다.")

    # 2. torchcodec 호환성 점검
    try:
        import torchcodec
        import torchaudio
        print("✅ 오디오 라이브러리(torchaudio, torchcodec) 정상 작동.")
    except (ImportError, RuntimeError, OSError):
        print("⚠️ 라이브러리 충돌 감지! 재설치 루틴을 실행합니다 (약 1분 소요)...")
        run_command(['pip', 'uninstall', '-y', 'torchcodec', 'torchaudio'], "충돌 패키지 제거")
        run_command(['pip', 'install', 'torchaudio', 'soundfile'], "torchaudio 재설치")
        run_command(['pip', 'install', 'torchcodec'], "torchcodec 재설치")
        print("\n🔄 [중요] 라이브러리 교체 완료. 변경 사항 적용을 위해 런타임을 재시작해주세요.")

    print("\n🎉 환경 설정 완료!")
