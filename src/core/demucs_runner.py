import sys
import os
import asyncio
import subprocess
import numpy as np
import soundfile as sf
from pathlib import Path
from typing import Tuple

async def separate_and_generate_stems(input_audio_path: str, output_dir: str = "outputs/demucs") -> Tuple[str, str]:
    input_path = Path(input_audio_path)
    if not input_path.exists():
        raise FileNotFoundError(f"원본 오디오 파일을 찾을 수 없습니다: {input_path}")

    os.makedirs(output_dir, exist_ok=True)
    
    command = [
        sys.executable, 
        "-m", "demucs.separate",
        "-n", "htdemucs", 
        "-o", output_dir, 
        str(input_path)
    ]
    
    print(f"🎵 [Demucs] 4-Stem 음원 분리 시작 (Thread Pool 위임): {' '.join(command)}")
    
    # [Fix] Windows 이벤트 루프 충돌을 우회하기 위해 표준 동기 subprocess를 스레드 풀에서 실행
    loop = asyncio.get_running_loop()
    
    def run_demucs_sync():
        # 서브프로세스를 동기적으로 실행하고 결과를 캡처
        return subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
    
    # 메인 루프 블로킹 없이 백그라운드 스레드에서 Demucs 실행
    process_result = await loop.run_in_executor(None, run_demucs_sync)
    
    if process_result.returncode != 0:
        raise RuntimeError(f"Demucs 분리 실패 (Exit Code {process_result.returncode}):\n{process_result.stderr}")
    
    # 2. 결과물 디렉토리 매핑
    model_out_dir = Path(output_dir) / "htdemucs" / input_path.stem
    bass_path = model_out_dir / "bass.wav"
    drums_path = model_out_dir / "drums.wav"
    vocals_path = model_out_dir / "vocals.wav"
    other_path = model_out_dir / "other.wav"
    
    for p in [bass_path, drums_path, vocals_path, other_path]:
        if not p.exists():
            raise FileNotFoundError(f"분리된 트랙이 누락되었습니다: {p}")

    # 3. CPU RAM 단에서의 프로그래매틱 트랙 합산 (Numpy Post-processing)
    print("🔄 [DSP] 백킹 트랙(MR) 생성을 위한 Numpy 텐서 병합 시작...")
    
    # soundfile을 통한 스테레오 무손실 로드
    drums, sr = sf.read(str(drums_path))
    vocals, _ = sf.read(str(vocals_path))
    other, _ = sf.read(str(other_path))
    
    # 배열 합산 (Broadcasting 불필요, Demucs 출력은 항상 동일한 Shape 보장)
    bassless_array = drums + vocals + other
    
    # 4. 디지털 클리핑(Clipping) 방어 
    # 합산 시 원본 믹스다운의 마스터링 리미터를 초과하여 1.0 (0dBFS)을 넘을 수 있음
    max_val = np.max(np.abs(bassless_array))
    if max_val > 1.0:
        print(f"⚠ [경고] 오디오 피크 초과 ({max_val:.2f}). 하드 클리핑을 방지하기 위해 정규화(Normalize)를 수행합니다.")
        bassless_array = bassless_array / max_val
        
    bassless_path = model_out_dir / "bassless_backing.wav"
    sf.write(str(bassless_path), bassless_array, sr)
    
    print(f"✔ [완료] 트랙 추출 및 MR 생성 완료\n - Bass: {bass_path}\n - MR: {bassless_path}")
    
    return str(bass_path), str(bassless_path)