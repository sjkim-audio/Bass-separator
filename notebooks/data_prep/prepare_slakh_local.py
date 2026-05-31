# prepare_slakh_test_only.py
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

RAW_DATA_DIR = "./slakh_raw"      
OUTPUT_DIR = "./slakh_processed"  

def run_redux_split():
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
    if len(bass_keys) > 1: return False, "베이스 트랙 중복"
    
    bass_key = bass_keys[0]
    out_track_dir = output_base_dir / track_dir.parent.name / track_dir.name
    out_track_dir.mkdir(parents=True, exist_ok=True)

    try:
        bass_flac = track_dir / "stems" / f"{bass_key}.flac"
        bass_audio, sr = sf.read(str(bass_flac))
        if len(bass_audio.shape) > 1: bass_audio = bass_audio.mean(axis=1)
            
        mix_audio = np.zeros_like(bass_audio)
        for stem in other_keys:
            stem_path = track_dir / "stems" / f"{stem}.flac"
            if stem_path.exists():
                audio, _ = sf.read(str(stem_path))
                if len(audio.shape) > 1: audio = audio.mean(axis=1)
                min_len = min(len(mix_audio), len(audio))
                mix_audio[:min_len] += audio[:min_len]

        bass_audio *= overall_gain
        mix_audio *= overall_gain
        sf.write(str(out_track_dir / "bass_gt.wav"), bass_audio, sr, subtype='PCM_16')
        sf.write(str(out_track_dir / "bassless_mr.wav"), mix_audio, sr, subtype='PCM_16')
        shutil.copy2(str(track_dir / "MIDI" / f"{bass_key}.mid"), str(out_track_dir / "bass_gt.mid"))

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
    
    # 수정: 'test' 스플릿만 타겟팅
    test_dir = source_base / "test"
    if not test_dir.exists():
        print("❌ test 폴더를 찾을 수 없습니다.")
        return
        
    all_tracks = [d for d in test_dir.iterdir() if d.is_dir() and d.name.startswith("Track")]

    print(f"\n🔍 총 {len(all_tracks)}개의 Test 트랙 전처리를 시작합니다...")
    success_count = 0
    num_cores = max(1, multiprocessing.cpu_count() - 1) 

    with ProcessPoolExecutor(max_workers=num_cores) as executor:
        futures = {executor.submit(process_slakh_track, track, out_base): track for track in all_tracks}
        for future in tqdm(as_completed(futures), total=len(futures)):
            if future.result()[0]: success_count += 1

    print(f"\n🎉 Test 전처리 완료! 총 {success_count}개의 유효 트랙이 생성되었습니다.")

    # Test 폴더 단일 압축
    print("\n🗜️ slakh_test.zip 압축을 시작합니다...")
    zip_path = str(out_base / "slakh_test")
    split_out_dir = out_base / "test"
    shutil.make_archive(zip_path, 'zip', root_dir=str(split_out_dir))
            
    print(f"✅ 완료! 파일 위치: {zip_path}.zip")

if __name__ == "__main__":
    main()
