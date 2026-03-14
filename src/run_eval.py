import argparse
import os
# metrics.py에 대한 의존성을 제거하고 evaluation.py로 단일화
from evaluation import run_evaluation
from visualization import visualize_metrics
from utils import save_experiment_results

def main():
    parser = argparse.ArgumentParser(description="오디오 소스 분리 성능 평가 파이프라인")
    parser.add_argument("--ref", type=str, required=True, help="원본(Reference) 오디오 파일 경로")
    parser.add_argument("--est", type=str, required=True, help="분리된(Estimated) 오디오 파일 경로")
    parser.add_argument("--exp_id", type=str, default="Exp_Test", help="실험 ID (결과 저장 시 파일명으로 사용됨)")
    parser.add_argument("--save", action="store_true", help="결과 데이터 및 플롯 저장 플래그")
    
    args = parser.parse_args()
    print(f"[{args.exp_id}] 평가를 시작합니다...")
    
    # 단일화된 평가 모듈 호출
    metrics = run_evaluation(args.ref, args.est, align=True)
    
    if not metrics:
        print("❌ 유효한 평가 지표가 산출되지 않아 프로세스를 종료합니다.")
        return

    img_save_path = None
    if args.save:
        img_save_path = save_experiment_results(metrics, args.exp_id)
        print("✅ 수치 데이터 저장이 완료되었습니다.")
        
    visualize_metrics(metrics, title=f"Separation Quality - {args.exp_id}", save_path=img_save_path)

if __name__ == "__main__":
    main()
