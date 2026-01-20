# 구글드라이브 데이터셋 복사

import os
import shutil
from google.colab import drive

def load_data_from_drive(drive_path, local_path="./dataset"):
    
    drive.mount('/content/drive')
  
    if not os.path.exists(local_path):
        print(f"🚀 데이터 복사 시작: {drive_path} -> {local_path}")
        try:
            shutil.copytree(drive_path, local_path)
            print("데이터 준비 완료! 로컬 경로('./dataset')를 사용하세요.")
        except Exception as e:
            print(f"오류 발생: {e}")
    else:
        print("데이터가 이미 준비되어 있습니다.")
