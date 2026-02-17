import os
from demucs.separate import main as demucs_main

def run_demucs(file_path: str, output_dir: str):
    """
    서브프로세스를 사용하지 않고, Demucs의 파이썬 내부 API를 직접 호출합니다.
    이를 통해 윈도우 환경의 고질적인 DLL 로드 에러(WinError 1114)를 원천 차단합니다.
    """
    try:
        print(f"Demucs 분리 시작 (내부 모듈 직접 실행): {file_path}")
        
        # 터미널에서 입력하던 명령어들을 리스트 형태로 구성합니다.
        args = [
            "-n", "htdemucs", 
            "--two-stems=bass",
            "-o", output_dir,
            file_path
        ]
        
        # 외부 프로세스를 띄우지 않고, 현재 서버 프로세스 내에서 Demucs 코드를 바로 실행합니다.
        demucs_main(args)
        
        print("Demucs 분리 완료!")
        
        # 결과물 경로 반환
        filename = os.path.splitext(os.path.basename(file_path))[0]
        bass_path = os.path.join(output_dir, "htdemucs", filename, "bass.wav")
        
        return bass_path

    except Exception as e:
        print(f"Demucs 실행 중 에러 발생: {e}")
        return None