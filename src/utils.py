import os
import shutil

def load_data_from_drive(drive_path, local_path="./dataset", force_update=False):
    """
    구글 드라이브(또는 외부 경로)의 데이터셋을 로컬 환경(Colab)으로 복사합니다.
    
    Args:
        drive_path (str): 구글 드라이브 내 데이터셋 원본 경로
        local_path (str): 복사할 목적지 경로 (기본값: ./dataset)
        force_update (bool): 이미 데이터가 있어도 강제로 덮어쓸지 여부 (기본값: False)
    """
    
    # 1. 원본 경로가 실제로 존재하는지 확인 (안전장치)
    if not os.path.exists(drive_path):
        print(f"❌ [Error] 원본 경로를 찾을 수 없습니다: {drive_path}")
        print("   구글 드라이브가 마운트되었는지, 경로 오타는 없는지 확인해주세요.")
        return

    # 2. 로컬에 이미 데이터가 있는지 확인
    if os.path.exists(local_path):
        if force_update:
            print(f"♻️ 기존 데이터 삭제 후 재복사 모드 (--force)")
            shutil.rmtree(local_path)
        else:
            print(f"✅ 데이터가 이미 준비되어 있습니다: {local_path}")
            print(f"   (업데이트하려면 force_update=True 옵션을 사용하세요)")
            return

    # 3. 데이터 복사 실행
    print(f"🚀 데이터 복사 시작...")
    print(f"   📂 Source: {drive_path}")
    print(f"   📂 Dest  : {local_path}")
    
    try:
        shutil.copytree(drive_path, local_path)
        
        # 파일 개수 확인 (검증)
        num_files = sum([len(files) for r, d, files in os.walk(local_path)])
        print(f"🎉 데이터 준비 완료! (총 {num_files}개 파일 복사됨)")
        
    except Exception as e:
        print(f"❌ 데이터 복사 중 오류 발생: {e}")
