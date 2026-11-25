# src/evaluation/run_eval.py
import argparse
import asyncio
from src.evaluation.evaluator import run_separation_evaluation, run_transcription_evaluation
from src.evaluation.visualization import visualize_metrics
from src.utils import save_experiment_results


def main():
    parser = argparse.ArgumentParser(description="베이스 채보 파이프라인 다목적 성능 평가 CLI")
    parser.add_argument("--mode", type=str, choices=["sep", "trans"], required=True,
                        help="평가 모드 선택 (sep: 소스 분리 평가, trans: 채보 알고리즘 평가)")
    parser.add_argument("--ref", type=str, required=True,
                        help="정답 파일 경로 (sep: 원본 베이스 WAV, trans: 정답 MIDI)")
    parser.add_argument("--est", type=str, required=True,
                        help="추정 파일/입력 경로 (sep: 추정 베이스 WAV, trans: 분석할 오디오 WAV)")

    parser.add_argument("--mix", type=str, default=None,
                        help="[sep 모드 선택 인자] 원본 믹스 오디오 WAV 경로 (미제공 시 단일 채널 모드로 평가, SIR=inf)")
    parser.add_argument("--ref_audio", type=str, default=None,
                        help="[trans 모드 E2E 평가용] 정답 베이스 오디오 WAV 경로 (Demucs 지연 보정용)")

    parser.add_argument("--isolated", action="store_true",
                        help="[trans 모드 전용] 입력된 오디오가 믹스가 아닌 단일 베이스 트랙(DI)일 경우 Demucs를 생략합니다.")
    parser.add_argument("--onset_tolerance", type=float, default=0.1,
                        help="Onset 일치 허용 오차 (초 단위, 기본값 0.1s = 100ms)")
    parser.add_argument("--exp_id", type=str, default="Exp_Test", help="실험 ID")
    parser.add_argument("--save", action="store_true", help="결과 저장 플래그")

    args = parser.parse_args()
    print(f"[{args.exp_id}] {args.mode.upper()} 모드 평가를 시작합니다...")

    metrics = {}

    if args.mode == "sep":
        metrics = run_separation_evaluation(
            ref_path=args.ref,
            est_path=args.est,
            mix_path=args.mix,
            align=True,
        )
    elif args.mode == "trans":
        metrics = asyncio.run(run_transcription_evaluation(
            args.ref,
            args.est,
            is_isolated=args.isolated,
            onset_tolerance=args.onset_tolerance,
            ref_audio_path=args.ref_audio
        ))

    if not metrics:
        print("❌ 유효한 평가 지표가 산출되지 않아 프로세스를 종료합니다.")
        return

    if args.save:
        save_experiment_results(metrics, args.exp_id)
        print("✅ 수치 데이터 저장이 완료되었습니다.")

        if args.mode == "sep":
            if "hop_sec" in metrics:
                visualize_metrics(metrics, title=f"Separation Quality - {args.exp_id}")
            else:
                print("ℹ️ mir_eval 트랙 단위 스칼라 결과이므로 시계열 그래프 시각화를 생략합니다.")


if __name__ == "__main__":
    main()
