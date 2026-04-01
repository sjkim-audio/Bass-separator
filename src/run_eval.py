import argparse
import os
from evaluation import run_separation_evaluation, run_transcription_evaluation
from visualization import visualize_metrics
from utils import save_experiment_results

def main():
    parser = argparse.ArgumentParser(description="베이스 채보 파이프라인 다목적 성능 평가 CLI")
    parser.add_argument("--mode", type=str, choices=["sep", "trans"], required=True, 
                        help="평가 모드 선택 (sep: 소스 분리 평가, trans: 채보 알고리즘 평가)")
    parser.add_argument("--ref", type=str, required=True, 
                        help="정답 파일 경로 (sep: 원본 WAV, trans: 정답 MIDI)")
    parser.add_argument("--est", type=str, required=True, 
                        help="추정 파일/입력 경로 (sep: 분리된 WAV, trans: 분석할 오디오 WAV)")
    parser.add_argument("--exp_id", type=str, default="Exp_Test", help="실험 ID")
    parser.add_argument("--save", action="store_true", help="결과 저장 플래그")
    
    args = parser.parse_args()
    print(f"[{args.exp_id}] {args.mode.upper()} 모드 평가를 시작합니다...")
    
    metrics = {}
    
    if args.mode == "sep":
        metrics = run_separation_evaluation(args.ref, args.est, align=True)
    elif args.mode == "trans":
        metrics = run_transcription_evaluation(args.ref, args.est)
    
    if not metrics:
        print("❌ 유효한 평가 지표가 산출되지 않아 프로세스를 종료합니다.")
        return

    # [주의] 채보 평가의 경우 기존 BSSEval 용 visualization 함수와 호환되지 않을 수 있음
    if args.save:
        save_experiment_results(metrics, args.exp_id) # utils.py에 F1-Score 포맷팅 추가 필요
        print("✅ 수치 데이터 저장이 완료되었습니다.")
        
        if args.mode == "sep":
            visualize_metrics(metrics, title=f"Separation Quality - {args.exp_id}")

if __name__ == "__main__":
    main()
