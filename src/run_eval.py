import argparse
import os
import asyncio
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
                        help="추정 파일/입력 경로 (sep: 추정 WAV, trans: 분석할 오디오 WAV)")
    # [신설] 단일 베이스 트랙 처리용 플래그
    parser.add_argument("--isolated", action="store_true", 
                        help="[trans 모드 전용] 입력된 오디오가 믹스가 아닌 단일 베이스 트랙(DI)일 경우 Demucs를 생략합니다.")
    parser.add_argument("--exp_id", type=str, default="Exp_Test", help="실험 ID")
    parser.add_argument("--save", action="store_true", help="결과 저장 플래그")
    
    args = parser.parse_args()
    print(f"[{args.exp_id}] {args.mode.upper()} 모드 평가를 시작합니다...")
    
    metrics = {}
    
    if args.mode == "sep":
        metrics = run_separation_evaluation(args.ref, args.est, align=True)
    elif args.mode == "trans":
        # 비동기 Demucs 처리를 위해 asyncio 루프 실행
        metrics = asyncio.run(run_transcription_evaluation(args.ref, args.est, is_isolated=args.isolated))
    
    if not metrics:
        print("❌ 유효한 평가 지표가 산출되지 않아 프로세스를 종료합니다.")
        return

    if args.save:
        save_experiment_results(metrics, args.exp_id)
        print("✅ 수치 데이터 저장이 완료되었습니다.")
        
        if args.mode == "sep":
            visualize_metrics(metrics, title=f"Separation Quality - {args.exp_id}")

if __name__ == "__main__":
    main()
