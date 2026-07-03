import os
import yaml
import shutil
import subprocess
import tarfile
from pathlib import Path
from tqdm.auto import tqdm
import sys

# [설정] 본인의 PC방/로컬 환경에 맞게 경로 지정
TAR_PATH = Path(r"C:\Users\user\Desktop\Slakh_Work\slakh2100_flac_redux.tar.gz")
OUTPUT_DIR = Path(r"C:\Users\user\Desktop\Slakh_Work\slakh_test")
TEMP_SANDBOX = Path(r"C:\Users\user\Desktop\Slakh_Work\_temp_extraction")
FFMPEG_EXE = Path(__file__).parent / "ffmpeg.exe"

def main():
    if not FFMPEG_EXE.exists():
        print(f"❌ 오류: {FFMPEG_EXE} 를 찾을 수 없습니다.")
        sys.exit(1)
    if not TAR_PATH.exists():
        print(f"❌ 원본 파일을 찾을 수 없습니다: {TAR_PATH}")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_SANDBOX.mkdir(parents=True, exist_ok=True)

    valid_tracks = {} # { "Track00001": "S02", ... }
    
    # ---------------------------------------------------------
    # Pass 1: 메타데이터 스캔 (메모리 최적화 단방향 스트림)
    # ---------------------------------------------------------
    print("🚀 [1/3] 아카이브 목차 스캔 및 유효 트랙 필터링 중...")
    with tarfile.open(TAR_PATH, "r:gz") as tar:
        for member in tar:
            if "test/Track" in member.name and member.name.endswith("metadata.yaml"):
                f = tar.extractfile(member)
                if f is None: continue
                
                meta = yaml.safe_load(f.read().decode("utf-8"))
                track_name = Path(member.name).parent.name
                
                bass_stems = [k for k, v in meta['stems'].items() if v.get('inst_class') == 'Bass' and v.get('audio_rendered', False)]
                if len(bass_stems) == 1:
                    valid_tracks[track_name] = bass_stems[0]

    print(f"🔍 총 {len(valid_tracks)}개의 유효 Test 트랙 식별 완료.")

    # ---------------------------------------------------------
    # Pass 2: 타겟 파일만 선택적 추출 (스트림 재개방)
    # ---------------------------------------------------------
    print("🚀 [2/3] 유효 트랙의 오디오/MIDI 파일 스트리밍 추출 중...")
    extracted_count = 0
    with tarfile.open(TAR_PATH, "r:gz") as tar:
        for member in tar:
            # test 폴더 밖의 파일이거나 유효 트랙이 아니면 빠른 스킵
            if "test/Track" not in member.name: continue
            
            track_name = Path(member.name).parts[-3] if "stems" in member.name or "MIDI" in member.name else Path(member.name).parts[-2]
            if track_name not in valid_tracks: continue

            bass_key = valid_tracks[track_name]
            is_mix = member.name.endswith("mix.flac")
            is_bass_flac = member.name.endswith(f"stems/{bass_key}.flac")
            is_bass_mid = member.name.endswith(f"MIDI/{bass_key}.mid")

            if is_mix or is_bass_flac or is_bass_mid:
                tar.extract(member, path=TEMP_SANDBOX)
                extracted_count += 1
                
    print(f"📦 타겟 파일 {extracted_count}개 임시 추출 완료. (FFmpeg 변환 시작)")

    # ---------------------------------------------------------
    # Pass 3: FFmpeg 변환 및 찌꺼기 삭제
    # ---------------------------------------------------------
    print("🚀 [3/3] WAV 변환 및 최종 데이터셋 빌드 중...")
    # TEMP_SANDBOX 내부 구조: _temp_extraction/slakh2100_flac_redux/test/TrackXXXXX/...
    temp_test_dir = next(TEMP_SANDBOX.rglob("test"), None)
    
    if not temp_test_dir:
        print("❌ 추출된 데이터가 없습니다.")
        sys.exit(1)

    for track_dir in tqdm(list(temp_test_dir.iterdir()), desc="FFmpeg 인코딩"):
        if not track_dir.is_dir(): continue
        
        track_name = track_dir.name
        bass_key = valid_tracks.get(track_name)
        if not bass_key: continue

        out_track_dir = OUTPUT_DIR / track_name
        out_track_dir.mkdir(exist_ok=True)
        
        mix_flac = track_dir / "mix.flac"
        bass_flac = track_dir / "stems" / f"{bass_key}.flac"
        bass_mid = track_dir / "MIDI" / f"{bass_key}.mid"

        try:
            subprocess.run([str(FFMPEG_EXE), '-y', '-i', str(mix_flac), str(out_track_dir / 'mix.wav')], capture_output=True, check=True)
            subprocess.run([str(FFMPEG_EXE), '-y', '-i', str(bass_flac), str(out_track_dir / 'bass_gt.wav')], capture_output=True, check=True)
            shutil.copy2(str(bass_mid), str(out_track_dir / 'bass_gt.mid'))
        except Exception as e:
            print(f"\n⚠️ [{track_name}] 변환 실패: {e}")
            shutil.rmtree(out_track_dir, ignore_errors=True)

    # 샌드박스 전체 삭제로 공간 반환
    shutil.rmtree(TEMP_SANDBOX, ignore_errors=True)

    # 압축 로직
    print("\n🗜️ slakh_test.zip 압축을 시작합니다...")
    zip_output_path = OUTPUT_DIR.parent / "slakh_test" 
    shutil.make_archive(str(zip_output_path), 'zip', root_dir=str(OUTPUT_DIR))
            
    print(f"✅ 완료! '{zip_output_path}.zip' 파일(약 5GB)만 구글 드라이브에 업로드하십시오.")

if __name__ == "__main__":
    main()
