import subprocess
import sys
import os

def run_demucs(file_path: str, output_dir: str):
    """
    서브프로세스를 통해 Demucs를 실행합니다.
    경로 인식 에러(WinError 2) 방지를 위해 파이썬 모듈 방식으로 호출합니다.
    """
    try:
        # sys.executable은 현재 실행 중인 파이썬(아나콘다)의 절대 경로를 보장합니다.
        command = [
            sys.executable,
            "-m", "demucs.separate",
            "-n", "htdemucs", 
            "--two-stems=bass",
            "-o", output_dir,
            file_path
        ]
        
        print(f"Demucs 분리 시작: {file_path}")
        subprocess.run(command, check=True)
        print("Demucs 분리 완료!")
        
        filename = os.path.splitext(os.path.basename(file_path))[0]
        bass_path = os.path.join(output_dir, "htdemucs", filename, "bass.wav")
        
        return bass_path

    except subprocess.CalledProcessError as e:
        print(f"Demucs 실행 중 에러 발생: {e}")
        return None
    except Exception as e:
        print(f"알 수 없는 에러 발생: {e}")
        return None
