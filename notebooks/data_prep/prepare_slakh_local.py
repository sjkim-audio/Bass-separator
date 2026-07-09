import os
import yaml
import shutil
import subprocess
import tarfile
import re
import time
import stat
from pathlib import Path
from tqdm.auto import tqdm
import sys

# 1. FFmpeg 시스템 경로 확인
system_ffmpeg = shutil.which("ffmpeg")
if system_ffmpeg is None:
    print("❌ 오류: 시스템 PATH에 FFmpeg가 설치되어 있지 않습니다. OS에 맞게 FFmpeg를 설치해주세요.")
    sys.exit(1)
    
FFMPEG_EXE = Path(system_ffmpeg)

# [설정] 본인의 PC/로컬 환경에 맞게 경로 지정
TAR_PATH = Path(r"G:\Bass_separator_dataset\slakh2100_flac_redux.tar.gz")
OUTPUT_DIR = Path(r"G:\Bass_separator_dataset\slakh_test")
TEMP_SANDBOX = Path(r"G:\Bass_separator_dataset\_temp_extraction")

# ---------------------------------------------------------
# 윈도우 환경 파일 락 방어 로직 (읽기 전용 강제 해제 및 재시도)
# ---------------------------------------------------------
def robust_rmtree(path, max_retries=3):
    def on_error(func, p, exc_info):
        try:
            os.chmod(p, stat.S_IWRITE)  # 읽기 전용 속성 강제 해제
            func(p)
        except Exception:
            pass

    for i in range(max_retries):
        try:
            if Path(path).exists():
                shutil.rmtree(path, onerror=on_error)
            break
        except Exception as e:
            if i < max_retries - 1:
                time.sleep(1)  # 백그라운드 프로세스가 파일을 놓아주기를 기다림
            else:
                print(f"\n⚠️ 경고: '{path}' 폴더 삭제 실패. 일부 임시 파일이 남아있을 수 있습니다: {e}")

def main():
    if not FFMPEG_EXE.exists():
        print(f"❌ 오류: {FFMPEG_EXE} 를 찾을 수 없습니다.")
        sys.exit(1)
    if not TAR_PATH.exists():
        print(f"❌ 원본 파일을 찾을 수 없습니다: {TAR_PATH}")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_SANDBOX.mkdir(parents=True, exist_ok=True)

    valid_tracks = {}
    
    # 정규표현식: 'Track' 뒤에 숫자 5자리가 오는 패턴을 정확히 탐색
    track_pattern = re.compile(r'(Track\d{5})')
    
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
                
                # 정규표현식으로 트랙 이름 안전하게 추출
                match = track_pattern.search(member.name)
                if not match: continue
                track_name = match.group(1)
                
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
            if "test/Track" not in member.name: continue
            
            match = track_pattern.search(member.name)
            if not match: continue
            track_name = match.group(1)
            
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
    
    # test 폴더를 찾는 방식을 조금 더 유연하게 변경
    temp_test_dir = None
    for p in TEMP_SANDBOX.rglob("test"):
        if p.is_dir():
            temp_test_dir = p
            break
    
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
            subprocess.run([str(FFMPEG_EXE), '-y', '-loglevel', 'error', '-i', str(mix_flac), str(out_track_dir / 'mix.wav')], capture_output=True, check=True)
            subprocess.run([str(FFMPEG_EXE), '-y', '-loglevel', 'error', '-i', str(bass_flac), str(out_track_dir / 'bass_gt.wav')], capture_output=True, check=True)
            
            if bass_mid.exists():
                shutil.copy2(str(bass_mid), str(out_track_dir / 'bass_gt.mid'))
                
        except Exception as e:
            print(f"\n⚠️ [{track_name}] 변환 실패: {e}")
            robust_rmtree(str(out_track_dir))  # 실패한 트랙의 잔여물 안전하게 삭제

    # 샌드박스 전체 삭제로 공간 반환
    print("\n🧹 임시 샌드박스 파일 정리 중...")
    robust_rmtree(str(TEMP_SANDBOX))

    # 압축 로직
    print("🗜️ slakh_test.zip 압축을 시작합니다...")
    zip_output_path = OUTPUT_DIR.parent / "slakh_test" 
    shutil.make_archive(str(zip_output_path), 'zip', root_dir=str(OUTPUT_DIR))
            
    print(f"✅ 완료! '{zip_output_path}.zip' 파일(약 5GB 예상)만 구글 드라이브에 업로드하십시오.")

# =========================================================
# 파이썬 실행 트리거 (반드시 이 부분이 파일 맨 아래에 있어야 합니다)
# =========================================================
if __name__ == "__main__":
    main()