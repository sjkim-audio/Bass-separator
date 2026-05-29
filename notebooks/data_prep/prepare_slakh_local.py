# prepare_slakh_local.py
# pip install soundfile pyyaml tqdm numpy
import os
import yaml
import shutil
import subprocess
import numpy as np
import soundfile as sf
from pathlib import Path
from tqdm.auto import tqdm
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed

# ==================================================================
# [설정] 본인의 로컬 PC 경로에 맞게 반드시 수정하세요.
# ==================================================================
RAW_DATA_DIR = "./slakh_raw"      # 원본 압축을 푼 폴더 (내부에 Slakh2100 폴더가 있어야 함)
OUTPUT_DIR = "./slakh_processed"  # 전처리 결과물이 저장될 폴더
# ==================================================================

def run_redux_split():
    """데이터 누수 방지를 위한 공식 slakh-utils 기반 재분할"""
    print("🛠️ Redux 버전 재분할을 시작합니다...")
    if not os.path.exists("slakh-utils"):
        subprocess.run(["git", "clone", "https://github.com/ethman/slakh-utils.git"], check=True)

    split_script = "slakh-utils/splits/resplit_slakh.py"
    split_json = "slakh-utils/splits/redux.json"
    slakh_base = os.path.join(RAW_DATA_DIR, "Slakh2100")

    if os.path.exists(slakh_base):
        subprocess.run(["python", split_script, "-d", slakh_base, "-s", split_json], check=True)
        print("✅ Redux 분할 완료.")
    else:
        print(f"❌ 원본 폴더를 찾을 수 없습니다: {slakh_base}")
        exit(1)

def process_slakh_track(track_dir: Path, output_base_dir: Path):
    """단일 트랙 전처리 코어 로직"""
    meta_path = track_dir / "metadata.yaml"
    if not meta_path.exists(): 
        return False, "metadata.yaml 누락"

    with open(meta_path, 'r', encoding='utf-8') as f:
        metadata = yaml.safe_load(f)

    overall_gain = metadata.get('overall_gain', 1.0)
    bass_keys, other_keys = [], []

    for stem_name, stem_info in metadata['stems'].items():
        prog = stem_info.get('program_num', 0)
        is_drum = stem_info.get('is_drum', False)
        if not is_drum and ((32 <= prog <= 39) or prog == 43):
            bass_keys.append(stem_name)
        else:
            other_keys.append(stem_name)

    if len(bass_keys) == 0: return False, "베이스 트랙 없음"
    if len(bass_keys) > 1: return False, "베이스 트랙 중복 (변인 통제 불가)"
    
    bass_key = bass_keys[0]
    out_track_dir = output_base_dir / track_dir.parent.name / track_dir.name
    out_track_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Bass 정답 변환 (Mono)
        bass_flac = track_dir / "stems" / f"{bass_key}.flac"
        bass_audio, sr = sf.read(str(bass_flac))
        if len(bass_audio.shape) > 1: bass_audio = bass_audio.mean(axis=1)
            
        # 2. Bassless MR 믹스다운
        mix_audio = np.zeros_like(bass_audio)
        for stem in other_keys:
            stem_path = track_dir / "stems" / f"{stem}.flac"
            if stem_path.exists():
                audio, _ = sf.read(str(stem_path))
                if len(audio.shape) > 1: audio = audio.mean(axis=1)
                min_len = min(len(mix_audio), len(audio))
                mix_audio[:min_len] += audio[:min_len]

        # 3. Gain 적용 및 저장
        bass_audio *= overall_gain
        mix_audio *= overall_gain
        sf.write(str(out_track_dir / "bass_gt.wav"), bass_audio, sr, subtype='PCM_16')
        sf.write(str(out_track_dir / "bassless_mr.wav"), mix_audio, sr, subtype='PCM_16')
        shutil.copy2(str(track_dir / "MIDI" / f"{bass_key}.mid"), str(out_track_dir / "bass_gt.mid"))

        # 4. E2E 평가용 원본 mix 변환
        mix_flac_path = track_dir / "mix.flac"
        if mix_flac_path.exists():
            full_mix, _ = sf.read(str(mix_flac_path))
            sf.write(str(out_track_dir / "mix.wav"), full_mix, sr, subtype='PCM_16')

        return True, "성공"
    except Exception as e:
        return False, f"런타임 에러: {e}"

def main():
    run_redux_split()

    source_base = Path(RAW_DATA_DIR) / "Slakh2100"
    out_base = Path(OUTPUT_DIR)
    
    all_tracks = []
    splits = ['train', 'validation', 'test']
    for split in splits:
        split_dir = source_base / split
        if split_dir.exists():
            all_tracks.extend([d for d in split_dir.iterdir() if d.is_dir() and d.name.startswith("Track")])

    print(f"\n🔍 총 {len(all_tracks)}개의 트랙 전처리를 시작합니다 (멀티프로세싱 가동)...")
    success_count = 0
    num_cores = max(1, multiprocessing.cpu_count() - 1) # 안정성을 위해 1코어 여유

    with ProcessPoolExecutor(max_workers=num_cores) as executor:
        futures = {executor.submit(process_slakh_track, track, out_base): track for track in all_tracks}
        for future in tqdm(as_completed(futures), total=len(futures)):
            if future.result()[0]: success_count += 1

    print(f"\n🎉 전처리 완료! 총 {success_count}개의 유효 트랙이 생성되었습니다.")

    # ---------------------------------------------------------
    # Split 단위별 개별 압축 (Train, Valid, Test 분리)
    # ---------------------------------------------------------
    print("\n🗜️ Split 단위별 압축을 시작합니다...")
    for split in splits:
        split_dir = out_base / split
        if split_dir.exists():
            zip_path = str(out_base / f"slakh_{split}")
            print(f"[{split.upper()}] 압축 중: {zip_path}.zip")
            shutil.make_archive(zip_path, 'zip', root_dir=str(split_dir))
            
    print("\n✅ 모든 작업이 완료되었습니다!")
    print(f"결과물 확인: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
