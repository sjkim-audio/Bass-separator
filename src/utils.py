import os
import shutil
import json
import numpy as np

def load_data_from_drive(drive_path, local_path="./dataset", force_update=False):
    """
    Copies a dataset from a source path (e.g., Google Drive) to the local environment.
    This is essential for faster I/O in environments like Google Colab.

    Args:
        drive_path (str): The source path of the dataset (e.g., '/content/drive/MyDrive/...').
        local_path (str): The destination path in the local environment. Defaults to "./dataset".
        force_update (bool): If True, deletes the existing local dataset and recopies it. Defaults to False.
    """
    # 1. Validation: Check if the source path exists
    if not os.path.exists(drive_path):
        print(f"❌ [Error] 원본 경로를 찾을 수 없습니다: {drive_path}")
        print("   구글 드라이브가 마운트되었는지, 경로 오타는 없는지 확인해주세요.")

    # 2. Check for existing local data
    if os.path.exists(local_path):
        if force_update:
            print(f"♻️ 기존 데이터 삭제 후 재복사 모드 (--force)")
            try:
                shutil.rmtree(local_path)
            except OSError as e:
                print(f"⚠️ 기존 폴더 삭제 실패: {e}")
        else:
            print(f"✅ 데이터가 이미 준비되어 있습니다: {local_path}")
            print(f"   (업데이트하려면 force_update=True 옵션을 사용하세요)")
            return

    # 3. Execution: Copy data
    print(f"🚀 데이터 복사 시작...")
    print(f"   📂 Source: {drive_path}")
    print(f"   📂 Dest  : {local_path}")
    
    try:
        # Copy the directory tree
        shutil.copytree(drive_path, local_path, dirs_exist_ok=True)
        
        
        # Verification: Count total files copied
        num_files = sum([len(files) for r, d, files in os.walk(local_path)])
        print(f"🎉 데이터 준비 완료! (총 {num_files}개 파일 복사됨)")
        
        
    except Exception as e:
        print(f"❌ 데이터 복사 중 오류 발생: {e}")


def save_experiment_results(metrics, exp_id, base_dir="/content/drive/MyDrive/Bass_separator"):
    """
    실험 결과(수치 데이터)를 JSON으로 저장하고, 
    시각화 이미지를 저장할 경로를 반환합니다.
    """
    # 1. 저장할 폴더 경로 설정 및 생성
    assets_dir = os.path.join(base_dir, "assets")
    results_dir = os.path.join(base_dir, "results")
    
    os.makedirs(assets_dir, exist_ok=True)
    os.makedirs(results_dir, exist_ok=True)
    
    # 2. Numpy 배열을 JSON 저장이 가능한 형태로 변환
    serializable_metrics = {}
    for key, value in metrics.items():
        if isinstance(value, np.ndarray):
            serializable_metrics[key] = value.tolist()
        else:
            serializable_metrics[key] = value
            
    # 중앙값(Median) 요약 데이터도 JSON에 함께 기록
    summary = {
        "SDR_median": float(np.nanmedian(metrics.get('SDR', [0]))),
        "SIR_median": float(np.nanmedian(metrics.get('SIR', [0]))),
        "SAR_median": float(np.nanmedian(metrics.get('SAR', [0])))
    }
    serializable_metrics["summary_statistics"] = summary
    
    # 3. JSON 파일로 저장 (.csv 대신 구조적 데이터 관리에 용이)
    json_path = os.path.join(results_dir, f"{exp_id}_metrics.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(serializable_metrics, f, indent=4)
        
    print(f"Info: 수치 데이터 저장 완료 -> {json_path}")
    
    # 4. 시각화 함수에 전달할 이미지 저장 경로 반환
    img_save_path = os.path.join(assets_dir, f"{exp_id}_plot.png")
    return img_save_path

