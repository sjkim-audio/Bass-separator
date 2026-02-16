import subprocess
import os

def run_demucs(file_path: str, output_dir: str):
    """
    서브프로세스(터미널 명령)를 통해 Demucs를 실행합니다.
    """
    try:
        # Demucs 실행 명령어 구성 (터미널에서 치던 것과 동일)
        # -n htdemucs_ft: 파인튜닝된 모델(또는 기본 모델) 이름
        # --two-stems=bass: 베이스와 나머지로만 분리
        # -o: 결과물 저장 경로 지정
        command = [
            "demucs",
            "-n", "htdemucs", 
            "--two-stems=bass",
            "-o", output_dir,
            file_path
        ]
        
        # 명령어 실행 (동기 처리)
        print(f"Demucs 분리 시작: {file_path}")
        subprocess.run(command, check=True)
        print("Demucs 분리 완료!")
        
        # 분리된 파일의 예상 경로 반환
        # 구조: output_dir / htdemucs / 원본파일명 / bass.wav
        filename = os.path.splitext(os.path.basename(file_path))[0]
        bass_path = os.path.join(output_dir, "htdemucs", filename, "bass.wav")
        
        return bass_path

    except subprocess.CalledProcessError as e:
        print(f"Demucs 실행 중 에러 발생: {e}")
        return None
