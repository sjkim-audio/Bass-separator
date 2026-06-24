import os
import yaml
import shutil
import subprocess
from pathlib import Path
from tqdm.auto import tqdm
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
import sys

# [설정] PC방 또는 로컬 PC 환경에 맞게 경로 지정
RAW_DATA_DIR = Path(r"C:\Users\user\Desktop\Slakh_Work\slakh2100_flac_redux")
OUTPUT_DIR = Path(r"C:\Users\user\Desktop\Slakh_Work\slakh_test")
FFMPEG_EXE = Path(__file__).parent / "ffmpeg.exe"

def process_slakh_track(track_dir: Path, output_base_dir: Path):
    meta_path = track_dir / "metadata.yaml"
    if not meta_path.exists(): 
        return False, "metadata.yaml 누락"

    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = yaml.safe_load(f)

    # [안전 로직 1] 오디오가 정상 렌더링된 Bass 스템만 수집
    bass_stems = []
    for stem_key, stem_info in meta['stems'].items():
        if stem_info.get('inst_class') == 'Bass' and stem_info.get('audio_rendered', False):
            bass_stems.append(stem_key)

    # [안전 로직 2] 베이스 트랙 누락 및 중복(Multi-bass) 배제
    if not bass_stems: return False, "유효한 베이스 트랙 없음"
    if len(bass_stems) > 1: return False, "베이스 트랙 중복 (평가 모호성)"
    
    bass_stem_key = bass_stems[0]
    out_track_dir = output_base_dir / track_dir.name
    out_track_dir.mkdir(parents=True, exist_ok=True)

    try:
        # [최적화] 무거운 Numpy 연산 대신 FFmpeg 다이렉트 변환으로 RAM/CPU 부하 최소화
        mix_flac = track_dir / "mix.flac"
        bass_flac = track_dir / "stems" / f"{bass_stem_key}.flac"
        
        # 1. Mix Audio 변환
        if mix_flac.exists():
            subprocess.run([str(FFMPEG_EXE), '-y', '-i', str(mix_flac), str(out_track_dir / 'mix.wav')], capture_output=True, check=True)
            
        # 2. Bass GT 변환
        subprocess.run([str(FFMPEG_EXE), '-y', '-i', str(bass_flac), str(out_track_dir / 'bass_gt.wav')], capture_output=True, check=True)
        
        # 3. 정답 MIDI 복사
        shutil.copy2(str(track_dir / "MIDI" / f"{bass_stem_key}.mid"), str(out_track_dir / 'bass_gt.mid'))

        return True, "성공"
    except Exception as e:
        # 실패 시 오염된 폴더 삭제
        shutil.rmtree(out_track_dir, ignore_errors=True)
        return False, f"변환 에러: {e}"

def main():
    if not FFMPEG_EXE.exists():
        print(f"❌ 오류: {FFMPEG_EXE} 를 찾을 수 없습니다.")
        sys.exit(1)

    test_dir = RAW_DATA_DIR / "test"
    if not test_dir.exists():
        print(f"❌ 원본 폴더를 찾을 수 없습니다: {test_dir}")
        print("경로가 올바른지, 압축이 정상적으로 해제되었는지 확인하십시오.")
        sys.exit(1)
        
    track_dirs = [d for d in test_dir.iterdir() if d.is_dir() and d.name.startswith("Track")]
    print(f"\n🔍 총 {len(track_dirs)}개의 Test 트랙 전처리를 시작합니다 (멀티코어 가동)...")
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    success_count = 0
    num_cores = max(1, multiprocessing.cpu_count() - 2) # OS 여유를 위해 2코어 제외

    with ProcessPoolExecutor(max_workers=num_cores) as executor:
        futures = {executor.submit(process_slakh_track, track, OUTPUT_DIR): track for track in track_dirs}
        
        for future in tqdm(as_completed(futures), total=len(futures), desc="전처리 진행률"):
            is_success, msg = future.result()
            if is_success:
                success_count += 1

    print(f"\n🎉 Test 전처리 완료! 총 {success_count}개의 유효 트랙이 생성되었습니다.")

    # 5GB 폴더 단일 Zip 압축 (Colab 업로드용)
    print("\n🗜️ slakh_test.zip 압축을 시작합니다...")
    zip_output_path = OUTPUT_DIR.parent / "slakh_test" 
    shutil.make_archive(str(zip_output_path), 'zip', root_dir=str(OUTPUT_DIR))
            
    print(f"✅ 모든 작업 완료! 구글 드라이브 업로드용 파일: {zip_output_path}.zip")

if __name__ == "__main__":
    main()
