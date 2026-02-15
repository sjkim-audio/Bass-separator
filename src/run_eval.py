import argparse
import os
from evaluation import calculate_metrics
from visualization import visualize_metrics
from utils import save_experiment_results

def main():
    # 1. argparse 객체 생성 및 인자 정의
    parser = argparse.ArgumentParser(description="오디오 소스 분리 성능 평가 파이프라인")
    
    parser.add_argument("--ref", type=str, required=True, help="원본(Reference) 오디오 파일 경로")
    parser.add_argument("--est", type=str, required=True, help="분리된(Estimated) 오디오 파일 경로")
    parser.add_argument("--exp_id", type=str, default="Exp_Test", help="실험 ID (결과 저장 시 파일명으로 사용됨)")
    parser.add_argument("--save", action="store_true", help="이 옵션을 추가하면 결과를 드라이브에 저장함")
    
    # 터미널에서 입력받은 인자 파싱
    args = parser.parse_args()
    
    print(f"[{args.exp_id}] 평가를 시작합니다...")
    
    # 2. 지표 계산 모듈 호출
    try:
        metrics = calculate_metrics(args.ref, args.est)
    except Exception as e:
        print(f"지표 계산 중 오류 발생: {e}")
        return

    # 3. 저장 및 시각화 모듈 호출 제어
    img_save_path = None
    
    if args.save:
        # --save 옵션이 터미널에서 입력된 경우에만 저장 로직 실행
        img_save_path = save_experiment_results(metrics, args.exp_id)
        print("결과 저장이 완료되었습니다.")
        
    # 시각화 실행 (저장 옵션에 따라 img_save_path가 None이거나 실제 경로가 됨)
    visualize_metrics(metrics, title=f"Separation Quality - {args.exp_id}", save_path=img_save_path)

if __name__ == "__main__":
    main()
