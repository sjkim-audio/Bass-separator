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
    
    loop = asyncio.get_running_loop()
    
    def run_demucs_sync():
        return subprocess.run(command, capture_output=True, text=True, errors='ignore')
    
    process_result = await loop.run_in_executor(None, run_demucs_sync)
    
    if process_result.returncode != 0:
        raise RuntimeError(f"Demucs 분리 실패 (Exit Code {process_result.returncode}):\n{process_result.stderr}")
    
    model_out_dir = Path(output_dir) / "htdemucs" / input_path.stem
    bass_path = model_out_dir / "bass.wav"
    drums_path = model_out_dir / "drums.wav"
    vocals_path = model_out_dir / "vocals.wav"
    other_path = model_out_dir / "other.wav"
    
    for p in [bass_path, drums_path, vocals_path, other_path]:
        if not p.exists():
            raise FileNotFoundError(f"분리된 트랙이 누락되었습니다: {p}")

    print("🔄 [DSP] 백킹 트랙(MR) 생성을 위한 Numpy 텐서 병합 시작...")
    
    drums, sr = sf.read(str(drums_path))
    vocals, _ = sf.read(str(vocals_path))
    other, _ = sf.read(str(other_path))
    
    bassless_array = drums + vocals + other
    
    max_val = np.max(np.abs(bassless_array))
    if max_val > 1.0:
        print(f"⚠ [경고] 오디오 피크 초과 ({max_val:.2f}). 하드 클리핑을 방지하기 위해 정규화(Normalize)를 수행합니다.")
        bassless_array = bassless_array / max_val
        
    bassless_path = model_out_dir / "bassless_backing.wav"
    sf.write(str(bassless_path), bassless_array, sr)
    
    print(f"✔ [완료] 트랙 추출 및 MR 생성 완료\n - Bass: {bass_path}\n - MR: {bassless_path}")
    
    # [계약 확인] Bass 트랙과 템포 추출용 Bassless MR 트랙을 동시 반환
    return str(bass_path), str(bassless_path)
